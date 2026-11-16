"""Optional f64 contact-law kernel. Neighbor search and reduction remain on CPU.

No Python dictionaries enter a Taichi kernel. This small-N hybrid backend has
transfer/launch overhead and makes no GPU speedup claim.
"""
import numpy as np
import taichi as ti


@ti.kernel
def _contacts(data: ti.types.ndarray(dtype=ti.f64, ndim=2),
              result: ti.types.ndarray(dtype=ti.f64, ndim=2),
              count: ti.i32, dt: ti.f64, kn: ti.f64, kt: ti.f64, gn: ti.f64, gt: ti.f64):
    for i in range(count):
        fn = kn * data[i, 0] - gn * ti.min(data[i, 1], 0.0)
        xi = data[i, 3] + data[i, 2] * dt
        trial = -kt * xi - gt * data[i, 2]
        cap = data[i, 4] * fn
        ft = ti.max(-cap, ti.min(cap, trial))
        if ti.abs(trial) > cap:
            xi = -(ft + gt * data[i, 2]) / kt
        result[i, 0], result[i, 1], result[i, 2] = fn, ft, xi


class TaichiContacts:
    def __init__(self, arch):
        selected = ti.cuda if arch == "cuda" else ti.cpu
        ti.init(arch=selected, enable_fallback=False, default_fp=ti.f64,
                device_memory_GB=0.25, cpu_max_num_threads=4, log_level=ti.ERROR,
                random_seed=0, offline_cache=True)
        if ti.lang.impl.current_cfg().arch != selected:
            raise RuntimeError("requested Taichi backend was not initialized")
        self.name = "taichi-" + arch

    def __call__(self, overlap, vn, vt, history, friction, dt, kn, kt, gn, gt):
        data = np.ascontiguousarray(np.column_stack((overlap, vn, vt, history, friction)), dtype=np.float64)
        result = np.empty((len(data), 3), dtype=np.float64)
        if len(data):
            _contacts(data, result, len(data), dt, kn, kt, gn, gt)
        return result[:, 0], result[:, 1], result[:, 2]
