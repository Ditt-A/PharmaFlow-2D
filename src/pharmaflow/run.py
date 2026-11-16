"""Run-level provenance and pickle-free, versioned NPZ trajectory export."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import time
from importlib.metadata import PackageNotFoundError, version
import numpy as np
from . import __version__
from .dem import DEMSystem


def hardware_info():
    info = {"platform": platform.platform(), "python": platform.python_version(), "numpy": np.__version__,
            "processor": platform.processor(), "libc": platform.libc_ver()}
    info["packages"] = {}
    for package in ("taichi", "matplotlib", "pillow"):
        try:
            info["packages"][package] = version(package)
        except PackageNotFoundError:
            info["packages"][package] = None
    try:
        info["gpu"] = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            text=True, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        info["gpu"] = None
    return info


def simulate(config, duration_s=0.5, sample_every=250, backend="cpu", monitor=None):
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("duration must be finite and positive")
    if not isinstance(sample_every, int) or sample_every < 1:
        raise ValueError("sample_every must be a positive integer")
    start = time.perf_counter()
    system = DEMSystem(config, backend=backend)
    system.monitor = monitor
    arrays = {key: [] for key in ("time_s", "position_m", "velocity_m_s", "angle_rad", "omega_rad_s", "active", "discharged_count")}
    def sample():
        s = system.state
        arrays["time_s"].append(system.time_s)
        for key, value in (("position_m", s.position), ("velocity_m_s", s.velocity),
                           ("angle_rad", s.angle), ("omega_rad_s", s.omega), ("active", s.active)):
            arrays[key].append(value.copy())
        arrays["discharged_count"].append(int(np.isfinite(system.crossing_time).sum()))
        if monitor is not None:
            monitor.sample(system)
    steps = int(math.ceil(duration_s / config.dt_s - 1e-10))
    sample()
    for index in range(1, steps + 1):
        system.step()
        if index % sample_every == 0 or index == steps:
            sample()
    # Check final contacts without advancing contact history or integration.
    history = system.history.copy()
    system.monitor = None
    system.forces()
    system.history = history
    result = {key: np.asarray(value) for key, value in arrays.items()}
    result.update(radius_m=system.state.radius.copy(), mass_kg=system.state.mass.copy(),
                  crossing_time_s=system.crossing_time.copy(), particle_id=np.arange(config.n_particles))
    if monitor is not None:
        result.update(monitor.arrays())
    checks = {"finite": all(np.all(np.isfinite(result[key])) for key in
              ("position_m", "velocity_m_s", "angle_rad", "omega_rad_s", "time_s")),
              "max_overlap_over_radius": system.max_overlap_ratio,
              "overlap_limit": config.max_overlap_ratio, "max_step_over_radius": system.max_step_ratio,
              "particle_count": config.n_particles, "active_final": int(system.state.active.sum()),
              "removed_final": int((~system.state.active).sum()),
              "discharged_final": int(np.isfinite(system.crossing_time).sum()),
              "wall_tunneling": False,
              "timestep_limit_s": config.timestep_limit_s(), "normal_contact_time_s": config.contact_time_s}
    checks["particle_accounting"] = checks["active_final"] + checks["removed_final"] == config.n_particles
    checks["removed_have_crossing"] = bool(np.all(np.isfinite(system.crossing_time[~system.state.active])))
    fingerprint = hashlib.sha256()
    for key in sorted(result):
        fingerprint.update(key.encode())
        fingerprint.update(result[key].tobytes())
    try:
        git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        git_dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.SubprocessError):
        git_head, git_dirty = None, None
    source_hash = hashlib.sha256()
    for source in sorted(Path(__file__).parent.glob("*.py")):
        source_hash.update(source.name.encode())
        source_hash.update(source.read_bytes())
    metadata = {"schema_version": 1, "solver_version": __version__, "source_git_head": git_head,
                "solver_source_sha256": source_hash.hexdigest(),
                "source_git_dirty": git_dirty, "config": asdict(config), "seed": config.seed,
                "backend": system.backend, "backend_note": system.backend_note,
                "hardware": hardware_info(), "duration_requested_s": duration_s,
                "duration_actual_s": system.time_s, "sample_every": sample_every,
                "steps": steps, "wall_time_s": time.perf_counter() - start,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "trajectory_sha256": fingerprint.hexdigest(), "accuracy_checks": checks,
                "scope": "uncalibrated dry 2D disks; no CFD, AI or published trajectory reconstruction"}
    if monitor is not None:
        metadata["physics_monitor"] = monitor.summary()
    return result, metadata


def save_run(path, arrays, metadata):
    path = Path(path)
    if path.suffix != ".npz":
        raise ValueError("trajectory output must have .npz extension")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays, metadata_json=np.array(json.dumps(metadata, sort_keys=True, allow_nan=False)))
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def load_run(path):
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata_json"]))
        arrays = {key: archive[key].copy() for key in archive.files if key != "metadata_json"}
    return arrays, metadata
