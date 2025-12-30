"""
Server Manager Service
Manages llama.cpp server instances as external processes
"""
import os
import json
import asyncio
import uuid
import threading
import sys
import subprocess
import aiohttp
from collections import deque
from typing import Optional, Dict, AsyncGenerator, List
from datetime import datetime

class ServerManager:
    def __init__(self, config_dir: str = "utils"):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.active_configs: Dict[str, Dict] = {}
        self.logs = deque(maxlen=1000)
        self.lock = threading.Lock()
        
        # Ensure config dir exists
        self.config_dir = config_dir
        os.makedirs(self.config_dir, exist_ok=True)
        self.servers_file = os.path.join(self.config_dir, "servers.json")
        self.servers = self._load_servers()
        
    def _log(self, message: str):
        """Add a log entry"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        print(log_entry)

    def _load_servers(self) -> List[Dict]:
        """Load saved server configurations"""
        try:
            if os.path.exists(self.servers_file):
                with open(self.servers_file, 'r') as f:
                    try:
                        return json.load(f)
                    except json.JSONDecodeError:
                        return []
        except Exception as e:
            self._log(f"Error loading servers: {e}")
        return []

    def _save_servers(self):
        """Save server configurations to file"""
        try:
            with open(self.servers_file, 'w') as f:
                json.dump(self.servers, f, indent=4)
        except Exception as e:
            self._log(f"Error saving servers: {e}")

    def get_servers(self) -> List[Dict]:
        """Get all configured servers"""
        return self.servers

    def create_server(self, config: Dict) -> Dict:
        """Create a new server configuration"""
        server_id = str(uuid.uuid4())
        new_server = {
            "id": server_id,
            "name": config.get("name", "Untitled Server"),
            "model_path": config.get("model_path"),
            "host": config.get("host", "127.0.0.1"),
            "port": int(config.get("port", 8000)),
            "created_at": datetime.now().isoformat(),
            "config": {
                "n_ctx": config.get("n_ctx", 2048),
                "n_gpu_layers": config.get("n_gpu_layers", 0),
                "n_threads": config.get("n_threads"),
                # "temperature", "top_p" etc are runtime params for chat, not server startup usually,
                # but llama.cpp server might accept some. We generally pass them at chat time.
            }
        }
        self.servers.append(new_server)
        self._save_servers()
        self._log(f"Created new server config: {new_server['name']} on port {new_server['port']}")
        return new_server

    def delete_server(self, server_id: str) -> bool:
        """Delete a server configuration"""
        # Stop if running
        if server_id in self.processes:
            asyncio.create_task(self.stop_server(server_id))
            
        initial_len = len(self.servers)
        self.servers = [s for s in self.servers if s["id"] != server_id]
        if len(self.servers) < initial_len:
            self._save_servers()
            self._log(f"Deleted server config: {server_id}")
            return True
        return False

    def update_server_config(self, server_id: str, config: Dict) -> Optional[Dict]:
        """Update an existing server configuration"""
        for i, server in enumerate(self.servers):
            if server["id"] == server_id:
                # Update basic fields
                server["name"] = config.get("name", server["name"])
                server["model_path"] = config.get("model_path", server["model_path"])
                server["port"] = int(config.get("port", server.get("port", 8000)))
                server["host"] = config.get("host", server.get("host", "127.0.0.1"))
                
                # Update inner config
                if "config" not in server:
                    server["config"] = {}
                
                server["config"]["n_ctx"] = config.get("n_ctx", server["config"].get("n_ctx", 2048))
                server["config"]["n_gpu_layers"] = config.get("n_gpu_layers", server["config"].get("n_gpu_layers", 0))
                
                # Runtime params (optional to store)
                if "temperature" in config:
                    server["config"]["temperature"] = config["temperature"]
                if "top_p" in config:
                    server["config"]["top_p"] = config["top_p"]

                self.servers[i] = server
                self._save_servers()
                self._log(f"Updated server config: {server['id']}")
                return server
        return None

    async def start_server(self, server_id: str) -> Dict:
        """Start a specific server configuration by ID as a subprocess"""
        
        # Check if already running
        if server_id in self.processes:
            process = self.processes[server_id]
            if process.poll() is None:
                 return {"status": "running", "config": self.active_configs[server_id]}
            else:
                # Clean up dead process
                del self.processes[server_id]
                del self.active_configs[server_id]

        # Find config
        server_config = next((s for s in self.servers if s["id"] == server_id), None)
        if not server_config:
            raise Exception(f"Server configuration not found: {server_id}")

        model_path = server_config["model_path"]
        host = server_config.get("host", "127.0.0.1")
        port = server_config.get("port", 8000)
        params = server_config["config"]
        
        self._log(f"Starting server '{server_config['name']}' on {host}:{port}")
        
        try:
            # Build command
            cmd = [
                sys.executable, "-m", "llama_cpp.server",
                "--model", model_path,
                "--host", host,
                "--port", str(port),
                "--n_ctx", str(params.get("n_ctx", 2048)),
                "--n_gpu_layers", str(params.get("n_gpu_layers", 0))
            ]
            if params.get("n_threads"):
                 cmd.extend(["--n_threads", str(params["n_threads"])])

            # Start process
            # Use specific creation flags for Windows to allow cleaner termination if needed, 
            # though simple Popen is often enough.
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, # For easier log reading if we were to pipe it
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            
            self.processes[server_id] = process
            self.active_configs[server_id] = server_config
            
            # Wait a moment to ensure it starts (naive check)
            # In a real app we might poll the health endpoint
            await asyncio.sleep(2) 
            
            if process.poll() is not None:
                # It died immediately
                stderr = process.stderr.read() if process.stderr else "Unknown error"
                raise Exception(f"Server process terminated immediately: {stderr}")

            self._log(f"Server '{server_config['name']}' started (PID: {process.pid})")
            
            return {
                "status": "started",
                "config": server_config
            }
            
        except Exception as e:
            self._log(f"Error starting server: {str(e)}")
            if server_id in self.processes:
                del self.processes[server_id]
            if server_id in self.active_configs:
                del self.active_configs[server_id]
            raise Exception(f"Failed to start server: {str(e)}")
    
    async def stop_server(self, server_id: str = None) -> bool:
        """Stop a server. If server_id is None, stop all."""
        if server_id is None:
            # Stop all
            results = []
            for sid in list(self.processes.keys()):
                results.append(await self.stop_server(sid))
            return all(results)
            
        if server_id not in self.processes:
            return False
            
        self._log(f"Stopping server {server_id}...")
        
        try:
            process = self.processes[server_id]
            process.terminate()
            
            # Give it a moment, then force kill if needed
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                
            del self.processes[server_id]
            if server_id in self.active_configs:
                del self.active_configs[server_id]
            
            self._log(f"Server {server_id} stopped")
            return True
            
        except Exception as e:
            self._log(f"Error unloading model: {str(e)}")
            # Even if error, try to clean up state
            if server_id in self.processes:
                del self.processes[server_id]
            if server_id in self.active_configs:
                del self.active_configs[server_id]
            return False
    
    async def chat(
        self,
        server_id: str,
        message: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> Dict:
        """Proxy chat request to the specific server"""
        if server_id not in self.active_configs:
             raise Exception("Server is not running")
        
        config = self.active_configs[server_id]
        host = config.get("host", "127.0.0.1")
        port = config.get("port", 8000)
        url = f"http://{host}:{port}/v1/chat/completions"
        
        payload = {
            "messages": [{"role": "user", "content": message}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }
        
        self._log(f"Proxying chat to {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Server returned {response.status}: {text}")
                
                return await response.json()
    
    async def chat_stream(
        self,
        server_id: str,
        message: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Proxy streaming chat request"""
        if server_id not in self.active_configs:
             yield f"data: {json.dumps({'error': 'Server is not running'})}\n\n"
             return
        
        config = self.active_configs[server_id]
        host = config.get("host", "127.0.0.1")
        port = config.get("port", 8000)
        url = f"http://{host}:{port}/v1/chat/completions"
        
        payload = {
            "messages": [{"role": "user", "content": message}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }
        
        self._log(f"Proxying stream chat to {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        yield f"data: {json.dumps({'error': f'Server error {response.status}'})}\n\n"
                        return

                    async for line in response.content:
                        if line:
                             yield line.decode('utf-8')
                             
        except Exception as e:
            self._log(f"Error in streaming chat: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    def is_running(self, server_id: str = None) -> bool:
        if server_id:
            return server_id in self.processes and self.processes[server_id].poll() is None
        # Check if ANY are running
        return any(p.poll() is None for p in self.processes.values())
    
    def get_status(self) -> Dict:
        """Get status of all running servers"""
        running_servers = []
        for sid, process in self.processes.items():
            if process.poll() is None and sid in self.active_configs:
                running_servers.append(self.active_configs[sid])
        
        return {
            "running_count": len(running_servers),
            "running_servers": running_servers
        }

    def get_logs(self, lines: int = 50) -> list:
        return list(self.logs)[-lines:]

