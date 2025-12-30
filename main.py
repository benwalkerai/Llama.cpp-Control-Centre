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
from pathlib import Path

# Internal Module Imports
from services.model_manager import ModelManager
from services.server_manager import ServerManager
from services.hardware_detector import HardwareDetector
from utils.config import ConfigManager

# Initialize FastAPI app
app = FastAPI(
    title="Llama.cpp Control Center",
    description="A modern control center for managing llama.cpp models and servers",
    version="1.0.0"
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
config_manager = ConfigManager()
model_manager = ModelManager(
    models_dir=config_manager.get("models_dir"),
    hf_token=config_manager.get("hf_token")
)
server_manager = ServerManager()
hardware_detector = HardwareDetector()

# Pydantic models for request/response
class ModelDownloadRequest(BaseModel):
    repo_id: str = Field(..., description="HuggingFace repo ID (e.g., 'TheBloke/Llama-2-7B-GGUF')")
    filename: str = Field(..., description="Specific GGUF file to download")



class ChatRequest(BaseModel):
    message: str
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = None
    stream: Optional[bool] = True

class PerformanceTestRequest(BaseModel):
    model_path: str
    prompt: Optional[str] = "Once upon a time"
    max_tokens: Optional[int] = 100

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
    """Download a mdoel from HuggingFace"""
    try:
        result = await model_manager.download_model(request.repo_id, request.filename)
        return {"success": True, "data": result}
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
        if server_manager.delete_server(server_id):
            return {"success": True, "message": "Server deleted"}
        raise HTTPException(status_code=404, detail="Server not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/servers/{server_id}/start")
async def start_server_by_id(server_id: str):
    """Start a saved server configuration"""
    try:
        result = await server_manager.start_server(server_id)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/server/stop")
async def stop_server():
    """Stop the running Llama.cpp server"""
    try:
        result = await server_manager.stop_server()
        return {"success": True, "message": "Server stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/server/status")
async def get_server_status():
    """Get current server status"""
    try:
        status = server_manager.get_status()
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

# Chat Endpoints

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Send a chat message to the loaded model"""
    if not server_manager.is_running():
        raise HTTPException(status_code=400, detail="Server is not running")
    
    try:
        if request.stream:
            return StreamingResponse(
                server_manager.chat_stream(
                    request.message,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature
                ),
                media_type="text/event-stream"
            )
        else:
            response = await server_manager.chat(
                request.message,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            return {"success": True, "data": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat"""
    await websocket.accept()
    
    if not server_manager.is_running():
        await websocket.send_json({
            "error": "Server is not running"
        })
        await websocket.close()
        return
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            async for chunk in server_manager.chat_stream(
                message_data.get("message", ""),
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
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup when shutting down"""
    if server_manager.is_running():
        await server_manager.stop_server()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
    