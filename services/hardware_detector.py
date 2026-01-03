"""
Hardware Detector Service
Detects system hardware and recommends optimal parameters

Author: Ben Walker ()
"""
import psutil
import platform
from typing import Dict, Optional
import subprocess

class HardwareDetector:
    def __init__(self):
        self.system_info = self._detect_hardware()
    
    def _detect_hardware(self) -> Dict:
        """Detect system hardware specifications"""
        info = {
            "cpu": {
                "model": platform.processor(),
                "cores_physical": psutil.cpu_count(logical=False),
                "cores_logical": psutil.cpu_count(logical=True),
                "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None
            },
            "memory": {
                "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                "percent_used": psutil.virtual_memory().percent
            },
            "gpu": self._detect_gpu(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine()
            }
        }
        
        return info
    
    def _detect_gpu(self) -> Dict:
        """Detect GPU information"""
        gpu_info = {
            "available": False,
            "name": None,
            "vram_gb": None,
            "cuda_available": False,
            "cuda_version": None
        }
        
        try:
            # Try to detect NVIDIA GPU using nvidia-smi
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    parts = output.split(',')
                    gpu_info["available"] = True
                    gpu_info["name"] = parts[0].strip()
                    gpu_info["vram_gb"] = round(float(parts[1].strip().split()[0]) / 1024, 2)
                    gpu_info["cuda_available"] = True
                    gpu_info["driver_version"] = parts[2].strip() if len(parts) > 2 else None
                    
                    # Try to get CUDA version from nvcc
                    try:
                        nvcc_result = subprocess.run(
                            ['nvcc', '--version'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if nvcc_result.returncode == 0:
                            # Parse CUDA version from nvcc output
                            import re
                            version_match = re.search(r'release (\d+\.\d+)', nvcc_result.stderr.lower())
                            if version_match:
                                gpu_info["cuda_version"] = version_match.group(1)
                    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                        pass
                    
                    # If nvcc not available, try to infer from driver version
                    if not gpu_info["cuda_version"] and gpu_info["driver_version"]:
                        # Map driver versions to CUDA versions (approximate)
                        driver_to_cuda = {
                            # Latest drivers
                            "546.01": "12.3",
                            "546.00": "12.3",
                            "545.23": "12.3",
                            "545.01": "12.3",
                            "535.54": "12.2",
                            "535.104": "12.2",
                            "535.82": "12.2",
                            "535.61": "12.2",
                            "535.54": "12.2",
                            "535.43": "12.2",
                            "535.34": "12.2",
                            "535.31": "12.2",
                            "535.30": "12.2",
                            "535.28": "12.2",
                            "535.27": "12.2",
                            "535.26": "12.2",
                            "535.25": "12.2",
                            "535.24": "12.2",
                            "535.23": "12.2",
                            "535.22": "12.2",
                            "535.21": "12.2",
                            "535.20": "12.2",
                            "535.17": "12.2",
                            "535.16": "12.2",
                            "535.15": "12.2",
                            "535.14": "12.2",
                            "535.13": "12.2",
                            "535.12": "12.2",
                            "535.11": "12.2",
                            "535.10": "12.2",
                            "535.09": "12.2",
                            "535.08": "12.2",
                            "535.07": "12.2",
                            "535.06": "12.2",
                            "535.05": "12.2",
                            "535.04": "12.2",
                            "535.03": "12.2",
                            "535.02": "12.2",
                            "535.01": "12.2",
                            "530.30": "12.1",
                            "530.86": "12.1",
                            "530.41": "12.1",
                            "530.30": "12.1",
                            "525.60": "12.0",
                            "525.85": "12.0",
                            "525.60": "12.0",
                            "525.47": "12.0",
                            "525.31": "12.0",
                            "525.30": "12.0",
                            "525.16": "12.0",
                            "525.15": "12.0",
                            "525.14": "12.0",
                            "525.13": "12.0",
                            "525.12": "12.0",
                            "525.11": "12.0",
                            "525.10": "12.0",
                            "525.09": "12.0",
                            "525.08": "12.0",
                            "525.07": "12.0",
                            "525.06": "12.0",
                            "515.65": "11.8",
                            "515.76": "11.8",
                            "515.65": "11.8",
                            "515.57": "11.8",
                            "515.52": "11.8",
                            "515.49": "11.8",
                            "515.48": "11.8",
                            "515.47": "11.8",
                            "515.43": "11.8",
                            "510.47": "11.7",
                            "510.108": "11.7",
                            "510.86": "11.7",
                            "510.73": "11.7",
                            "510.54": "11.7",
                            "510.47": "11.7",
                            "510.39": "11.7",
                            "470.57": "11.4",
                            "470.223": "11.4",
                            "470.161": "11.4",
                            "470.141": "11.4",
                            "470.129": "11.4",
                            "470.103": "11.4",
                            "470.86": "11.4",
                            "470.82": "11.4",
                            "470.81": "11.4",
                            "470.63": "11.4",
                            "470.57": "11.4",
                            "460.27": "11.2",
                            "460.89": "11.2",
                            "460.82": "11.2",
                            "460.79": "11.2",
                            "470.27": "11.2",
                            "455.28": "11.1",
                            "455.45": "11.1",
                            "455.38": "11.1",
                            "455.32": "11.1",
                            "455.28": "11.1",
                            "450.36": "11.0"
                        }
                        
                        # Try to match exact driver version first
                        exact_match = driver_to_cuda.get(gpu_info["driver_version"])
                        if exact_match:
                            gpu_info["cuda_version"] = exact_match
                        else:
                            # Try prefix matching
                            driver_prefix = '.'.join(gpu_info["driver_version"].split('.')[:2])
                            gpu_info["cuda_version"] = driver_to_cuda.get(driver_prefix, "Unknown")
                            
                            # If still unknown, try to estimate based on version number
                            if gpu_info["cuda_version"] == "Unknown":
                                driver_major = int(gpu_info["driver_version"].split('.')[0])
                                if driver_major >= 535:
                                    gpu_info["cuda_version"] = "12.2+"
                                elif driver_major >= 530:
                                    gpu_info["cuda_version"] = "12.1+"
                                elif driver_major >= 525:
                                    gpu_info["cuda_version"] = "12.0+"
                                elif driver_major >= 515:
                                    gpu_info["cuda_version"] = "11.8+"
                                elif driver_major >= 470:
                                    gpu_info["cuda_version"] = "11.4+"
                                else:
                                    gpu_info["cuda_version"] = f"~11.{min(driver_major - 459, 0)}"
                    
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # Try alternative method using torch if available
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_info["available"] = True
                    gpu_info["cuda_available"] = True
                    gpu_info["name"] = torch.cuda.get_device_name(0)
                    gpu_info["vram_gb"] = round(
                        torch.cuda.get_device_properties(0).total_memory / (1024**3), 2
                    )
                    gpu_info["cuda_version"] = torch.version.cuda
            except ImportError:
                pass
        
        return gpu_info
    
    def get_system_info(self) -> Dict:
        """Get current system information (refreshed)"""
        self.system_info = self._detect_hardware()
        return self.system_info
    
    def recommend_parameters(self, model_size_gb: Optional[float] = None) -> Dict:
        """Recommend optimal parameters based on hardware"""
        recommendations = {
            "n_threads": self.system_info["cpu"]["cores_physical"],
            "n_ctx": 2048,
            "n_gpu_layers": 0,
            "use_mmap": True,
            "use_mlock": False,
            "reasoning": []
        }
        
        # Memory-based recommendations
        available_ram = self.system_info["memory"]["available_gb"]
        
        if model_size_gb:
            if model_size_gb > available_ram * 0.8:
                recommendations["reasoning"].append(
                    f"⚠️ Warning: Model size ({model_size_gb}GB) is close to or exceeds "
                    f"available RAM ({available_ram}GB). Consider using a smaller quantization."
                )
        
        # Context length recommendations
        if available_ram < 8:
            recommendations["n_ctx"] = 1024
            recommendations["reasoning"].append(
                "Limited RAM: Using smaller context window (1024)"
            )
        elif available_ram < 16:
            recommendations["n_ctx"] = 2048
            recommendations["reasoning"].append(
                "Moderate RAM: Using standard context window (2048)"
            )
        elif available_ram >= 32:
            recommendations["n_ctx"] = 4096
            recommendations["reasoning"].append(
                "High RAM: Can use larger context window (4096)"
            )
        
        # GPU recommendations
        gpu = self.system_info["gpu"]
        if gpu["available"] and gpu["cuda_available"]:
            vram = gpu["vram_gb"]
            
            if model_size_gb:
                # Estimate layers based on model size and VRAM
                estimated_layers = int((vram / model_size_gb) * 35)
                recommendations["n_gpu_layers"] = min(estimated_layers, 35)
            else:
                # Conservative estimate
                if vram >= 24:
                    recommendations["n_gpu_layers"] = 35
                elif vram >= 12:
                    recommendations["n_gpu_layers"] = 25
                elif vram >= 8:
                    recommendations["n_gpu_layers"] = 15
                elif vram >= 6:
                    recommendations["n_gpu_layers"] = 10
                else:
                    recommendations["n_gpu_layers"] = 5
            
            recommendations["reasoning"].append(
                f"GPU detected ({gpu['name']}, {vram}GB VRAM): "
                f"Using {recommendations['n_gpu_layers']} GPU layers"
            )
        else:
            recommendations["reasoning"].append(
                "No GPU detected: Using CPU-only inference"
            )
        
        # Thread recommendations
        physical_cores = self.system_info["cpu"]["cores_physical"]
        if physical_cores:
            # Use physical cores minus 1 for system overhead
            recommendations["n_threads"] = max(1, physical_cores - 1)
            recommendations["reasoning"].append(
                f"Using {recommendations['n_threads']} threads "
                f"(physical cores: {physical_cores})"
            )
        
        # Additional performance tips
        if self.system_info["platform"]["system"] == "Linux":
            recommendations["use_mlock"] = available_ram > 16
            if recommendations["use_mlock"]:
                recommendations["reasoning"].append(
                    "Sufficient RAM: Enabling mlock for better performance"
                )
        
        # Quantization recommendations
        recommendations["suggested_quantization"] = self._suggest_quantization(available_ram)
        
        return recommendations
    
    def _suggest_quantization(self, available_ram_gb: float) -> Dict:
        """Suggest appropriate model quantization based on RAM"""
        suggestions = {
            "7B_models": [],
            "13B_models": [],
            "34B_models": [],
            "70B_models": []
        }
        
        # 7B model suggestions
        if available_ram_gb >= 4:
            suggestions["7B_models"].append("Q4_K_M (4GB RAM, good balance)")
        if available_ram_gb >= 6:
            suggestions["7B_models"].append("Q5_K_M (6GB RAM, better quality)")
        if available_ram_gb >= 8:
            suggestions["7B_models"].append("Q6_K (8GB RAM, high quality)")
        if available_ram_gb >= 14:
            suggestions["7B_models"].append("Q8_0 (14GB RAM, very high quality)")
        
        # 13B model suggestions
        if available_ram_gb >= 8:
            suggestions["13B_models"].append("Q4_K_M (8GB RAM, good balance)")
        if available_ram_gb >= 10:
            suggestions["13B_models"].append("Q5_K_M (10GB RAM, better quality)")
        if available_ram_gb >= 12:
            suggestions["13B_models"].append("Q6_K (12GB RAM, high quality)")
        
        # 34B model suggestions
        if available_ram_gb >= 20:
            suggestions["34B_models"].append("Q4_K_M (20GB RAM, good balance)")
        if available_ram_gb >= 24:
            suggestions["34B_models"].append("Q5_K_M (24GB RAM, better quality)")
        
        # 70B model suggestions
        if available_ram_gb >= 40:
            suggestions["70B_models"].append("Q4_K_M (40GB RAM, good balance)")
        if available_ram_gb >= 48:
            suggestions["70B_models"].append("Q5_K_M (48GB RAM, better quality)")
        
        return suggestions
