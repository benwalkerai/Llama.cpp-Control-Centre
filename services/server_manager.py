"""
Server Manager Service
Manages llama.cpp server instances using llama-cpp-python
"""
import os
import uuid
import threading
from collections import deque
from typing import Optional, Dict, AsyncGenerator, List
from datetime import datetime
from llama_cpp import Llama

class ServerManager:
    def __init__(self, config_dir: str = "utils"):
        self.llama_instance: Optional[Llama] = None
        self.is_loaded = False
        self.active_config = {}
        self.active_server_id = None
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
                    return json.load(f)
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
            "created_at": datetime.now().isoformat(),
            "config": {
                "n_ctx": config.get("n_ctx", 2048),
                "n_gpu_layers": config.get("n_gpu_layers", 0),
                "n_threads": config.get("n_threads"),
                "temperature": config.get("temperature", 0.7),
                "top_p": config.get("top_p", 0.9),
                "top_k": config.get("top_k", 40),
                "repeat_penalty": config.get("repeat_penalty", 1.1)
            }
        }
        self.servers.append(new_server)
        self._save_servers()
        self._log(f"Created new server config: {new_server['name']}")
        return new_server

    def delete_server(self, server_id: str) -> bool:
        """Delete a server configuration"""
        initial_len = len(self.servers)
        self.servers = [s for s in self.servers if s["id"] != server_id]
        if len(self.servers) < initial_len:
            self._save_servers()
            self._log(f"Deleted server config: {server_id}")
            return True
        return False

    async def start_server(self, server_id: str) -> Dict:
        """Start a specific server configuration by ID"""
        
        # Find config
        server_config = next((s for s in self.servers if s["id"] == server_id), None)
        if not server_config:
            raise Exception(f"Server configuration not found: {server_id}")

        if self.is_loaded:
            if self.active_server_id == server_id:
                return {"status": "loaded", "config": self.active_config}
            self._log("Stopping existing model before loading new one")
            await self.stop_server()
        
        model_path = server_config["model_path"]
        params = server_config["config"]
        self._log(f"Starting server '{server_config['name']}' with model: {model_path}")
        
        try:
            # Load model in a thread
            loop = asyncio.get_event_loop()
            
            def load_model():
                return Llama(
                    model_path=model_path,
                    n_ctx=params.get("n_ctx", 2048),
                    n_gpu_layers=params.get("n_gpu_layers", 0),
                    n_threads=params.get("n_threads"),
                    verbose=True
                )
            
            self.llama_instance = await loop.run_in_executor(None, load_model)
            
            self.active_config = server_config
            self.active_server_id = server_id
            self.is_loaded = True
            
            self._log(f"Server '{server_config['name']}' started successfully")
            
            return {
                "status": "loaded",
                "config": self.active_config
            }
            
        except Exception as e:
            self._log(f"Error starting server: {str(e)}")
            self.is_loaded = False
            self.active_server_id = None
            raise Exception(f"Failed to start server: {str(e)}")
    
    async def stop_server(self) -> bool:
        """Stop/unload the current model"""
        if not self.is_loaded:
            return False
        
        self._log("Unloading model")
        
        try:
            with self.lock:
                if self.llama_instance:
                    self.llama_instance = None
                
                self.is_loaded = False
                self.active_config = {}
                self.active_server_id = None
            
            self._log("Model unloaded successfully")
            return True
            
        except Exception as e:
            self._log(f"Error unloading model: {str(e)}")
            raise Exception(f"Failed to unload model: {str(e)}")
    
    async def chat(
        self,
        message: str,
        max_tokens: int = 512,
        temperature: Optional[float] = None
    ) -> Dict:
        """Send a chat message"""
        if not self.is_loaded or not self.llama_instance:
            raise Exception("No model is loaded")
        
        # Use runtime temp or config default
        config_params = self.active_config.get("config", {})
        temp = temperature if temperature is not None else config_params.get("temperature", 0.7)
        
        self._log(f"Processing chat message (non-streaming)")
        
        try:
            loop = asyncio.get_event_loop()
            
            def generate():
                return self.llama_instance.create_chat_completion(
                    messages=[{"role": "user", "content": message}],
                    max_tokens=max_tokens,
                    temperature=temp,
                    top_p=config_params.get("top_p", 0.9),
                    top_k=config_params.get("top_k", 40),
                    repeat_penalty=config_params.get("repeat_penalty", 1.1)
                )
            
            response = await loop.run_in_executor(None, generate)
            
            return {
                "message": response["choices"][0]["message"]["content"],
                "usage": response.get("usage", {}),
                "model": response.get("model", "unknown")
            }
            
        except Exception as e:
            self._log(f"Error in chat: {str(e)}")
            raise Exception(f"Chat failed: {str(e)}")
    
    async def chat_stream(
        self,
        message: str,
        max_tokens: int = 512,
        temperature: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        """Send a chat message and stream"""
        if not self.is_loaded or not self.llama_instance:
            raise Exception("No model is loaded")
        
        config_params = self.active_config.get("config", {})
        temp = temperature if temperature is not None else config_params.get("temperature", 0.7)
        
        self._log(f"Processing chat message (streaming)")
        
        try:
            loop = asyncio.get_event_loop()
            queue = asyncio.Queue()
            
            def generate():
                try:
                    stream = self.llama_instance.create_chat_completion(
                        messages=[{"role": "user", "content": message}],
                        max_tokens=max_tokens,
                        temperature=temp,
                        top_p=config_params.get("top_p", 0.9),
                        top_k=config_params.get("top_k", 40),
                        repeat_penalty=config_params.get("repeat_penalty", 1.1),
                        stream=True
                    )
                    
                    for chunk in stream:
                        delta = chunk["choices"][0]["delta"]
                        if "content" in delta:
                            asyncio.run_coroutine_threadsafe(
                                queue.put(delta["content"]),
                                loop
                            )
                    
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                    
                except Exception as e:
                    asyncio.run_coroutine_threadsafe(
                        queue.put(f"Error: {str(e)}"),
                        loop
                    )
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)
            
            thread = threading.Thread(target=generate)
            thread.start()
            
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            thread.join()
            
        except Exception as e:
            self._log(f"Error in streaming chat: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    def is_running(self) -> bool:
        return self.is_loaded and self.llama_instance is not None
    
    def get_status(self) -> Dict:
        """Get current server status"""
        return {
            "is_running": self.is_running(),
            "active_server_id": self.active_server_id if self.is_running() else None,
            "running_config": self.active_config if self.is_running() else {},
            "uptime": self._get_uptime() if self.is_running() else None
        }
    
    def _get_uptime(self) -> Optional[float]:
        # Implementation assumes 'loaded_at' is not in persisted config but could be added to active_config at runtime
        # For now we'll just return None or add loaded_at to active_config when starting
        return None # Simplified for now as datetime logic needs adaptation to new structure

    def get_logs(self, lines: int = 50) -> list:
        return list(self.logs)[-lines:]

