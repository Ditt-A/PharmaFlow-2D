import os
import sys
import shutil
from importlib.metadata import PackageNotFoundError, version

print("Python:", sys.version.split()[0])
print("CPU cores:", os.cpu_count())
print("Free disk GB:", round(shutil.disk_usage(os.getcwd()).free / 1e9, 2))
for package in ("numpy", "taichi", "torch", "matplotlib", "requests"):
    try:
        print(package, version(package))
    except PackageNotFoundError:
        print(package, "not installed")
try:
    import torch
    print("PyTorch CUDA:", torch.cuda.is_available(), "CUDA version:", torch.version.cuda)
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))
except ImportError:
    pass
try:
    import taichi as ti
    ti.init(arch=ti.cuda, log_level=ti.ERROR)
    print("Taichi CUDA initialized")
except Exception as error:
    print("Taichi CUDA not initialized:", str(error)[:200])
