"""Probe real CPU/CUDA kernels in subprocesses, without silent CUDA fallback."""
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

print("Executable:", sys.executable, flush=True)
print("Python:", platform.python_version(), "GLIBC:", platform.libc_ver(), flush=True)
print("CPU cores:", os.cpu_count(), flush=True)
print("Free disk GB:", round(shutil.disk_usage(os.getcwd()).free / 1e9, 2), flush=True)
for package in ("numpy", "taichi", "torch", "matplotlib", "requests", "numbers-parser", "pytest"):
    try:
        print(package, version(package), flush=True)
    except PackageNotFoundError:
        print(package, "not installed", flush=True)
try:
    result = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu", "--format=csv"],
                            capture_output=True, text=True, timeout=10)
    print(result.stdout or result.stderr, flush=True)
except (OSError, subprocess.SubprocessError) as error:
    print("NVIDIA driver unavailable:", error, flush=True)
from pharmaflow.config import HopperConfig
from pharmaflow.dem import DEMSystem
DEMSystem(HopperConfig(n_particles=1)).advance(10)
print("NumPy CPU DEM: passed (Taichi and torch are optional)", flush=True)
template = '''import numpy as np
import taichi as ti
ti.init(arch=ti.ARCH, enable_fallback=False, device_memory_GB=0.25, cpu_max_num_threads=4, log_level=ti.ERROR)
assert ti.lang.impl.current_cfg().arch == ti.ARCH
@ti.kernel
def square(a: ti.types.ndarray(dtype=ti.f64, ndim=1)):
    for i in range(a.shape[0]):
        a[i] = a[i] * a[i]
a = np.arange(8, dtype=np.float64)
square(a)
np.testing.assert_array_equal(a, np.arange(8)**2)
print('Taichi ARCH compute: passed')
'''
for arch in ("cpu", "cuda"):
    with tempfile.TemporaryDirectory(prefix="pharmaflow-probe-") as directory:
        script = Path(directory) / "probe.py"
        script.write_text(template.replace("ARCH", arch))
        try:
            result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=90)
            print(result.stdout.strip(), flush=True)
            if result.returncode:
                print(f"Taichi {arch} unavailable: {result.stderr.strip()}", flush=True)
                if "GLIBC_2.32" in result.stderr:
                    print('Use python -m pip install "taichi==1.7.3" in this environment.', flush=True)
        except subprocess.SubprocessError as error:
            print(f"Taichi {arch} probe failed: {error}", flush=True)
