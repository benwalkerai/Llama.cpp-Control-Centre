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
            "eta": 0
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
        """Download a model from HuggingFace"""
        if self.download_status["is_downloading"]:
            raise Exception("A download is already in progress")
        
        self.download_status["is_downloading"] = True
        self.download_status["current_file"] = filename
        self.download_status["progress"] = 0
        
        try:
            # Use huggingface_hub to download with progress
            local_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=str(self.models_dir),
                local_dir_use_symlinks=False,
                token=self.hf_token
            )
            
            self.download_status["progress"] = 100
            
            return {
                "path": local_path,
                "filename": filename,
                "repo_id": repo_id
            }
            
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")
        
        finally:
            self.download_status["is_downloading"] = False
            self.download_status["current_file"] = None
            self.download_status["progress"] = 0
    
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
            api = HfApi()
            
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
            files = list_repo_files(repo_id)
            gguf_files = [f for f in files if f.endswith(".gguf")]
            return gguf_files
        except Exception as e:
            raise Exception(f"Failed to list files: {str(e)}")
