"""Conservative geometric/kinematic arch observations, not a prediction model."""
import numpy as np
from .config import HopperConfig
from .geometry import hopper_walls, segment_contacts


def spanning_contact_chain(position, radius, active, config, contact_tolerance_m=1e-6):
    ids = np.flatnonzero(active & (position[:, 1] > -radius) & (position[:, 1] < 0.025))
    if len(ids) < 2:
        return False
    x, r = position[ids], radius[ids]
    distance = np.linalg.norm(x[:, None] - x[None, :], axis=2)
    adjacent = distance <= r[:, None] + r[None, :] + contact_tolerance_m
    wd, _, _ = segment_contacts(x, hopper_walls(config, config.gate_open_time_s + 1)[:2])
    left, right = wd[:, 0] <= r + contact_tolerance_m, wd[:, 1] <= r + contact_tolerance_m
    reached = left.copy()
    for _ in range(len(ids)):
        expanded = reached | np.any(adjacent & reached[:, None], axis=0)
        if np.array_equal(expanded, reached):
            break
        reached = expanded
    return bool(np.any(reached & right))


def arch_observation(arrays, metadata, window_s=0.2, stationary_speed_m_s=0.003):
    """Require retained grains, persistent contact bridge, low speed, and no flux.

    This is a finite-window, near-outlet arch observation only; it makes no
    claim about infinite stability or calibrated industrial clogging thresholds.
    """
    config = HopperConfig(**metadata["config"])
    time = arrays["time_s"]
    if window_s <= 0 or stationary_speed_m_s <= 0:
        raise ValueError("window and stationary threshold must be positive")
    start = time[-1] - window_s
    indices = np.flatnonzero(time >= start - 1e-12)
    spans, speeds, retained = [], [], []
    for frame in indices:
        p, v, active = arrays["position_m"][frame], arrays["velocity_m_s"][frame], arrays["active"][frame]
        near = active & (p[:, 1] >= 0) & (p[:, 1] < 0.025)
        speeds.append(float(np.max(np.linalg.norm(v[near], axis=1))) if near.any() else float("inf"))
        retained.append(int(np.sum(active & (p[:, 1] >= 0))))
        spans.append(spanning_contact_chain(p, arrays["radius_m"], active, config))
    no_flux = bool(np.all(arrays["discharged_count"][indices] == arrays["discharged_count"][indices[0]]))
    sufficiently_long = start >= config.gate_open_time_s and len(indices) > 1 and time[-1] - time[indices[0]] >= window_s - config.dt_s
    max_speed = max(speeds)
    observed = sufficiently_long and no_flux and min(retained) >= 2 and all(spans) and max_speed < stationary_speed_m_s
    return {"observed_stationary_spanning_arch": bool(observed), "window_s": window_s,
            "sampled_frames": len(indices), "no_outlet_crossings_in_window": no_flux,
            "minimum_retained_particles": min(retained), "spanning_chain_every_frame": all(spans),
            "maximum_near_outlet_speed_m_s": max_speed if np.isfinite(max_speed) else None,
            "stationary_speed_threshold_m_s": stationary_speed_m_s,
            "limitation": "Finite sampled window; qualitative 2D behavior, not M2 reference validation or an ML label."}
