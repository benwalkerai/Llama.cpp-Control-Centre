"""
FastAPI llama.cpp Control Centre
Main application file

Author: Ben Walker (https://github.com/benwalkerai)
"""

# External Module Imports
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn
import asyncio
import json
import traceback
from pathlib import Path

# Internal Module Imports
from services.model_manager import ModelManager
from services.server_manager import ServerManager
from services.hardware_detector import HardwareDetector
from utils.config import ConfigManager
from contextlib import asynccontextmanager

# Initialize services
config_manager = ConfigManager()
model_manager = ModelManager(
    models_dir=config_manager.get("models_dir"),
    hf_token=config_manager.get("hf_token")
)
server_manager = ServerManager()
hardware_detector = HardwareDetector()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    yield
    # Shutdown logic
    print("[Shutdown] Stopping all model servers...")
    await server_manager.stop_server() # stop_server(None) stops all
    print("[Shutdown] Cleanup complete.")

# Initialize FastAPI app
app = FastAPI(
    title="Llama.cpp Control Center",
    description="A modern control center for managing llama.cpp models and servers",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize service
# Services already initialized above

# Pydantic models for request/response
class ModelDownloadRequest(BaseModel):
    repo_id: str = Field(..., description="HuggingFace repo ID (e.g., 'TheBloke/Llama-2-7B-GGUF')")
    filename: str = Field(..., description="Specific GGUF file to download")



class ChatRequest(BaseModel):
    server_id: str = Field(..., description="ID of the server to chat with")
    message: str
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = None
    stream: Optional[bool] = True

class PerformanceTestRequest(BaseModel):
    runs: int = 3
    prompt: Optional[str] = (
        "Write a detailed explanation of how neural networks learn through backpropagation. "
        "Include the mathematical concepts and provide examples."
    )
    max_tokens: Optional[int] = 500
    temperature: Optional[float] = 0.7

class SettingsUpdateRequest(BaseModel):
    models_dir: str
    hf_token: Optional[str] = None

# Settings Endpoints

@app.get("/api/settings")
async def get_settings():
    """Get current settings"""
    try:
        settings = config_manager.get_all()
        # Mask token for security in UI if it exists
        if settings.get("hf_token"):
            token = settings["hf_token"]
            if len(token) > 8:
                settings["hf_token_masked"] = f"{token[:4]}...{token[-4:]}"
            else:
                settings["hf_token_masked"] = "****"
        return {"success": True, "data": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings")
async def update_settings(request: SettingsUpdateRequest):
    """Update settings"""
    try:
        config_manager.update({
            "models_dir": request.models_dir,
            "hf_token": request.hf_token
        })
        
        # Update services with new settings
        model_manager.update_settings(
            models_dir=request.models_dir,
            hf_token=request.hf_token
        )
        
        return {"success": True, "message": "Settings updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Hardware Endpoints

@app.get("/api/hardware/info")
async def get_hardware_info():
    """Get system hardware information"""
    try:
        info = hardware_detector.get_system_info()
        return {"success": True, "data": info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hardware/recommendations")
async def get_parameter_recommendations(model_size_gb: Optional[float] = None):
    """Get parameter recommendations based on hardware"""
    try:
        recommendations = hardware_detector.recommend_parameters(model_size_gb)
        return {"success": True, "data": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Model Management Endpoints
@app.get("/api/models/list")
async def list_models():
    """List all downloaded models"""
    try:
        models = await model_manager.list_models()
        return {"success": True, "data": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/models/download")
async def download_model(request: ModelDownloadRequest):
    """Download a model from HuggingFace in the background"""
    try:
        # Start download in background
        asyncio.create_task(model_manager.download_model(request.repo_id, request.filename))
        return {"success": True, "message": "Download started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/models/delete/{model_name}")
async def delete_model(model_name: str):
    """Delete a model"""
    try:
        result = await model_manager.delete_model(model_name)
        return {"success": True, "message": f"Model {model_name} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/models/download/status")
async def get_download_status():
    """Get current download status"""
    try:
        status = model_manager.get_download_status()
        return {"success": True, "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
class CreateServerRequest(BaseModel):
    name: str = "My Server"
    model_path: str
    port: int = 8000
    host: str = "127.0.0.1"
    n_ctx: Optional[int] = 2048
    n_gpu_layers: Optional[int] = 0
    n_threads: Optional[int] = None
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    top_k: Optional[int] = 40
    repeat_penalty: Optional[float] = 1.1

# Server Management Endpoints

@app.get("/api/servers")
async def list_servers():
    """List all saved server configurations"""
    try:
        servers = server_manager.get_servers()
        return {"success": True, "data": servers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/servers/{server_id}")
async def get_server(server_id: str):
    """Get a single server configuration"""
    try:
        servers = server_manager.get_servers()
        server = next((s for s in servers if s["id"] == server_id), None)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        return {"success": True, "data": server}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/servers")
async def create_server(request: CreateServerRequest):
    """Create a new server configuration"""
    try:
        result = server_manager.create_server(request.dict())
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/servers/{server_id}")
async def delete_server(server_id: str):
    """Delete a server configuration"""
    try:
        success = server_manager.delete_server(server_id)
        if not success:
            raise HTTPException(status_code=404, detail="Server not found")
        return {"success": True, "message": "Server deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/servers/{server_id}")
async def update_server(server_id: str, request: CreateServerRequest):
    """Update a server configuration"""
    try:
        # We reuse CreateServerRequest as it contains all necessary fields
        config = request.dict()
        updated_server = server_manager.update_server_config(server_id, config)
        
        if not updated_server:
            raise HTTPException(status_code=404, detail="Server not found")
            
        return {"success": True, "data": updated_server}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/servers/{server_id}/start")
async def start_server_by_id(server_id: str):
    """Start a saved server configuration"""
    try:
        result = await server_manager.start_server(server_id)
        return {"success": True, "data": result}
    except Exception as e:
        print(f"[Error] Failed to start server: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/server/stop")
async def stop_server(server_id: Optional[str] = None):
    """Stop running Llama.cpp server(s)"""
    try:
        result = await server_manager.stop_server(server_id)
        return {"success": True, "message": "Server processed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/servers/{server_id}/benchmark")
async def run_server_benchmark(server_id: str, request: PerformanceTestRequest):
    """Run performance benchmark against a running server"""
    if not server_manager.is_running(server_id):
        raise HTTPException(status_code=400, detail="Server must be running to run benchmark")

    try:
        data = await server_manager.run_performance_test(
            server_id=server_id,
            runs=request.runs,
            prompt=request.prompt,
            max_tokens=request.max_tokens or 500,
            temperature=request.temperature if request.temperature is not None else 0.7
        )
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/server/status")
async def get_server_status():
    """Get current server status"""
    try:
        status = await server_manager.get_status()
        return {"success": True, "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/server/logs")
async def get_server_logs(lines: int = 50):
    """Get recent server logs"""
    try:
        logs = server_manager.get_logs(lines)
        return {"success": True, "data": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/server/logs/{server_id}")
async def get_specific_server_logs(server_id: str, lines: int = 100):
    """Get logs for a specific server instance"""
    try:
        logs = server_manager.get_server_logs(server_id, lines)
        return {"success": True, "data": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Chat Endpoints

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Send a chat message to the loaded model"""
    # Simply check if target server is running
    if not server_manager.is_running(request.server_id):
        raise HTTPException(status_code=400, detail=f"Server {request.server_id} is not running")
    
    try:
        response = await server_manager.chat(
            server_id=request.server_id,
            message=request.message,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )

        if request.stream:
            async def event_stream():
                content = ""
                try:
                    choices = response.get("choices", [])
                    if choices:
                        choice = choices[0]
                        content = (
                            choice.get("message", {}).get("content") or
                            choice.get("text") or
                            ""
                        )
                    yield f"data: {json.dumps({'content': content})}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        return {"success": True, "data": response}
    except Exception as e:
        print(f"Chat Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/chat/{server_id}")
async def websocket_chat(websocket: WebSocket, server_id: str):
    """WebSocket endpoint for real-time chat"""
    await websocket.accept()
    
    if not server_manager.is_running(server_id):
        await websocket.send_json({
            "error": f"Server {server_id} is not running"
        })
        await websocket.close()
        return
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            async for chunk in server_manager.chat_stream(
                server_id=server_id,
                message=message_data.get("message", ""),
                max_tokens=message_data.get("max_tokens", 512),
                temperature=message_data.get("temperature")
            ):
                await websocket.send_text(chunk)
                
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()

# Utility Endpoints

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "server_running": server_manager.is_running(),
        "models_available": len(await model_manager.list_models())
    }

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main UI"""
    html_file = Path("templates/index.html")
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return {"message": "llama.cpp Control Center API", "docs": "/docs"}

# Cleanup on shutdown
# Cleanup handled by lifespan

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
    