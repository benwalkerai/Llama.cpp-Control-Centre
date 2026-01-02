"""
Model Manager Service
Handles downloading, listing, and deleting models
"""
import os
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
import aiohttp
import aiofiles
from huggingface_hub import hf_hub_download, list_repo_files
from datetime import datetime
import json

class ModelManager:
    def __init__(self, models_dir: str = "./models", hf_token: Optional[str] = None):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.hf_token = hf_token
        self.download_status = {
            "is_downloading": False,
            "current_file": None,
            "progress": 0,
            "speed": 0,
            "eta": 0,
            "last_error": None
        }
    
    def update_settings(self, models_dir: str, hf_token: Optional[str] = None):
        """Update model manager settings"""
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.hf_token = hf_token
        
    async def list_models(self) -> List[Dict]:
        """List all downloaded models with metadata"""
        models = []
        
        for model_file in self.models_dir.glob("*.gguf"):
            stat = model_file.stat()
            models.append({
                "name": model_file.name,
                "path": str(model_file),
                "size_bytes": stat.st_size,
                "size": stat.st_size,
                "size_gb": round(stat.st_size / (1024**3), 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "type": self._detect_model_type(model_file.name)
            })
        
        return sorted(models, key=lambda x: x["modified"], reverse=True)
    
    def _detect_model_type(self, filename: str) -> str:
        """Detect model quantization type from filename"""
        filename_lower = filename.lower()
        
        quant_types = {
            "q2": "2-bit", "q3": "3-bit", "q4": "4-bit",
            "q5": "5-bit", "q6": "6-bit", "q8": "8-bit",
            "f16": "16-bit float", "f32": "32-bit float"
        }
        
        for key, value in quant_types.items():
            if key in filename_lower:
                return value
        
        return "Unknown"
    
    async def download_model(self, repo_id: str, filename: str) -> Dict:
        """Download a model from HuggingFace with progress tracking"""
        import time
        
        if self.download_status["is_downloading"]:
            raise Exception("A download is already in progress")
        
        self.download_status["is_downloading"] = True
        self.download_status["current_file"] = filename
        self.download_status["progress"] = 0
        self.download_status["current_size_mb"] = 0
        self.download_status["total_size_mb"] = 0
        self.download_status["speed_mb_s"] = 0
        self.download_status["eta_seconds"] = 0
        self.download_status["last_error"] = None
        
        url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
        headers = {}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
            
        local_path = self.models_dir / filename
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"Download failed with status {response.status}: {response.reason}")
                    
                    total_size = int(response.headers.get('content-length', 0))
                    self.download_status["total_size_mb"] = round(total_size / (1024 * 1024), 2)
                    
                    downloaded_size = 0
                    start_time = time.time()
                    last_update_time = start_time
                    
                    async with aiofiles.open(local_path, mode='wb') as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024): # 1MB chunks
                            await f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # Calculate stats
                            current_time = time.time()
                            elapsed_time = current_time - start_time
                            
                            # Update status
                            if total_size > 0:
                                self.download_status["progress"] = round((downloaded_size / total_size) * 100, 1)
                            
                            self.download_status["current_size_mb"] = round(downloaded_size / (1024 * 1024), 2)
                            
                            # Speed and ETA (update every 0.5s to avoid jitter)
                            if current_time - last_update_time > 0.5:
                                speed = downloaded_size / elapsed_time if elapsed_time > 0 else 0
                                self.download_status["speed_mb_s"] = round(speed / (1024 * 1024), 2)
                                
                                if speed > 0:
                                    remaining_bytes = total_size - downloaded_size
                                    self.download_status["eta_seconds"] = round(remaining_bytes / speed, 0)
                                else:
                                    self.download_status["eta_seconds"] = 0
                                    
                                last_update_time = current_time
            
            return {
                "path": str(local_path),
                "filename": filename,
                "repo_id": repo_id
            }
            
        except Exception as e:
            # Clean up partial download
            if local_path.exists():
                local_path.unlink()
            self.download_status["last_error"] = str(e)
            print(f"Download Error: {str(e)}")
            raise Exception(f"Download failed: {str(e)}")
        
        finally:
            self.download_status["is_downloading"] = False
            self.download_status["current_file"] = None
            self.download_status["progress"] = 0
            self.download_status["speed_mb_s"] = 0
            self.download_status["eta_seconds"] = 0
    
    async def delete_model(self, model_name: str) -> bool:
        """Delete a model file"""
        model_path = self.models_dir / model_name
        
        if not model_path.exists():
            raise Exception(f"Model {model_name} not found")
        
        if not model_path.suffix == ".gguf":
            raise Exception("Can only delete .gguf files")
        
        try:
            model_path.unlink()
            return True
        except Exception as e:
            raise Exception(f"Failed to delete model: {str(e)}")
    
    def get_download_status(self) -> Dict:
        """Get current download status"""
        return self.download_status.copy()
    
    async def search_huggingface(self, query: str, limit: int = 10) -> List[Dict]:
        """Search HuggingFace for GGUF models"""
        # This is a simplified version - you might want to use the HF API more extensively
        try:
            from huggingface_hub import HfApi
            api = HfApi(token=self.hf_token)
            
            models = api.list_models(
                search=query,
                filter="gguf",
                limit=limit
            )
            
            results = []
            for model in models:
                results.append({
                    "repo_id": model.id,
                    "downloads": model.downloads,
                    "likes": model.likes,
                    "last_modified": model.lastModified
                })
            
            return results
        except Exception as e:
            raise Exception(f"Search failed: {str(e)}")
    
    async def get_model_files(self, repo_id: str) -> List[str]:
        """List available GGUF files in a HuggingFace repo"""
        try:
            files = list_repo_files(repo_id, token=self.hf_token)
            gguf_files = [f for f in files if f.endswith(".gguf")]
            return gguf_files
        except Exception as e:
            raise Exception(f"Failed to list files: {str(e)}")
