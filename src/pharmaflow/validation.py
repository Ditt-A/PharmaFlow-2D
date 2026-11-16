"""Passive M2 diagnostics. Measurement does not advance contact history."""
import numpy as np
from .geometry import segment_contacts
from .diagnostics import arch_observation


class PhysicsMonitor:
    def __init__(self, config):
        self.config = config
        self.bins = np.linspace(0, config.max_overlap_ratio, 151)
        self.hist = np.zeros(150, dtype=np.int64)
        self.max_force = self.max_omega = self.max_acceleration = 0.0
        self.normal_loss = self.tangential_work = self.exported = 0.0
        self.gate_removed = self.last_gate_energy = 0.0
        self.gate_was_closed = config.gate_open_time_s > 0
        self.leak_samples = 0
        self.series = []
        self.last_force = 0.0

    def contacts(self, system, overlap, radius, fn, vn, tangential_power, j):
        c = self.config
        if len(overlap):
            self.hist += np.histogram(overlap / radius, self.bins)[0]
            self.last_force = float(np.max(fn))
            self.max_force = max(self.max_force, self.last_force)
            self.normal_loss += float(c.normal_damping_kg_s * np.sum(np.minimum(vn, 0)**2) * c.dt_s)
            self.tangential_work += float(np.sum(tangential_power) * c.dt_s)
        else:
            self.last_force = 0.0
        closed = system.time_s < c.gate_open_time_s
        if self.gate_was_closed and not closed:
            self.gate_removed += self.last_gate_energy
        self.last_gate_energy = float(0.5 * c.normal_stiffness_n_m * np.sum(overlap[j == -5]**2)) if closed else 0.0
        self.gate_was_closed = closed

    def remove(self, system, removed):
        s, c = system.state, self.config
        self.exported += float(np.sum(0.5 * s.mass[removed] * np.sum(s.velocity[removed]**2, axis=1) +
                                     0.5 * s.inertia[removed] * s.omega[removed]**2 +
                                     s.mass[removed] * c.gravity_m_s2 * s.position[removed, 1]))

    def after_step(self, system, force, torque):
        s = system.state
        self.max_omega = max(self.max_omega, float(np.max(np.abs(s.omega))))
        self.max_acceleration = max(self.max_acceleration, float(np.max(np.linalg.norm(force / s.mass[:, None], axis=1))))
        if not np.all(np.isfinite(force)) or not np.all(np.isfinite(torque)):
            raise RuntimeError("nonfinite contact force or torque")

    def sample(self, system):
        s, c = system.state, self.config
        ids = np.flatnonzero(s.active)
        pairs = system.neighbors.get(s.position, s.radius, s.active)
        i, j = pairs[:, 0], pairs[:, 1]
        overlap = s.radius[i] + s.radius[j] - np.linalg.norm(s.position[i] - s.position[j], axis=1)
        keep = (overlap > 0) & s.active[i] & s.active[j]
        keys = list(zip(i[keep].tolist(), j[keep].tolist()))
        normal_u = float(0.5 * c.normal_stiffness_n_m * np.sum(overlap[keep]**2))
        wd, _, _ = segment_contacts(s.position, system.walls)
        wi, wall = np.nonzero((wd < s.radius[:, None]) & s.active[:, None])
        normal_u += float(0.5 * c.normal_stiffness_n_m * np.sum((s.radius[wi] - wd[wi, wall])**2))
        keys.extend(zip(wi.tolist(), (-wall - 1).tolist()))
        tangent_u = 0.5 * c.tangential_stiffness_n_m * sum(float(np.dot(system.history.get(key, (0., 0.)), system.history.get(key, (0., 0.)))) for key in keys)
        k = float(np.sum(0.5 * s.mass[ids] * np.sum(s.velocity[ids]**2, axis=1)))
        kr = float(np.sum(0.5 * s.inertia[ids] * s.omega[ids]**2))
        pe = float(np.sum(s.mass[ids] * c.gravity_m_s2 * s.position[ids, 1]))
        half = np.minimum(c.width_m / 2, c.outlet_width_m / 2 + (c.width_m - c.outlet_width_m) / 2 * s.position[:, 1] / c.funnel_height_m)
        self.leak_samples += int(np.sum(s.active & (s.position[:, 1] > 0) & (np.abs(s.position[:, 0]) > half + 1e-12)))
        self.series.append(dict(kinetic_j=k, rotation_j=kr, gravity_j=pe, normal_spring_j=normal_u,
                               tangent_spring_j=tangent_u, exported_j=self.exported,
                               gate_removed_j=self.gate_removed, normal_damping_loss_j=self.normal_loss,
                               tangential_contact_work_j=self.tangential_work, max_contact_force_n=self.last_force))

    def arrays(self):
        return {"diag_" + key: np.array([row[key] for row in self.series]) for key in self.series[0]}

    def summary(self):
        count = int(self.hist.sum())
        quantiles = {}
        for q in (0.5, 0.95, 0.99):
            index = np.searchsorted(np.cumsum(self.hist), q * count) if count else 0
            quantiles[str(q)] = float(self.bins[min(index + 1, len(self.bins) - 1)]) if count else 0.0
        return {"overlap_histogram_counts": self.hist.tolist(), "overlap_histogram_edges": self.bins.tolist(),
                "overlap_quantile_upper_bounds": quantiles, "contact_step_observations": count,
                "max_contact_force_n": self.max_force, "max_angular_speed_rad_s": self.max_omega,
                "max_acceleration_m_s2": self.max_acceleration, "normal_damping_loss_j": self.normal_loss,
                "net_tangential_contact_work_j": self.tangential_work, "exported_energy_j": self.exported,
                "gate_removed_normal_spring_energy_j_approx": self.gate_removed,
                "boundary_center_leak_samples": self.leak_samples,
                "energy_limit": "History springs sampled after prior force update; gate energy approximate. No exact hopper energy closure claimed."}


def flow_metrics(arrays, config, duration, bin_s=0.02, quiet_s=0.06):
    """Finite-horizon flow observations. Never infer permanent clogging."""
    crossing = arrays["crossing_time_s"]
    crossing = np.sort(crossing[np.isfinite(crossing)])
    edges = np.arange(0, duration + bin_s / 2, bin_s)
    if edges[-1] < duration - 1e-12:
        edges = np.append(edges, duration)
    counts = np.histogram(crossing, edges)[0]
    rate = counts / np.diff(edges)
    p, v, active = arrays["position_m"], arrays["velocity_m_s"], arrays["active"]
    near = active & (p[..., 1] >= 0) & (p[..., 1] < 0.02)
    # Center-assigned disk area in the exact trapezoid. Boundary disks are not clipped.
    top_width = config.outlet_width_m + (config.width_m - config.outlet_width_m) * 0.02 / config.funnel_height_m
    roi_area = 0.02 * (config.outlet_width_m + min(config.width_m, top_width)) / 2
    phi = np.sum(near * (np.pi * arrays["radius_m"]**2), axis=1) / roi_area
    speed = np.linalg.norm(v, axis=2)
    means = np.divide(np.sum(speed * near, axis=1), near.sum(axis=1), out=np.zeros(len(p)), where=near.sum(axis=1) > 0)
    observation = arch_observation(arrays, {"config": __import__('dataclasses').asdict(config)}, window_s=min(0.2, duration / 2))
    # Ever crossing the outlet is insufficient if particles have re-entered it.
    retained_final = active[-1] & (p[-1, :, 1] >= 0)
    completed = len(crossing) == config.n_particles and not np.any(retained_final)
    gaps = np.diff(crossing)
    intermittent = bool(len(gaps) and np.max(gaps) >= quiet_s)
    if completed:
        state = "completed_discharge"
    elif observation["observed_stationary_spanning_arch"]:
        state = "persistent_clogging_observed"
    elif intermittent:
        state = "intermittent_flow"
    elif len(crossing) >= 3 and duration - crossing[-1] < quiet_s:
        state = "continuous_flow_observed"
    else:
        state = "unresolved_transient"
    return {"total_discharged": len(crossing), "discharge_fraction": len(crossing) / config.n_particles,
            "time_to_empty_s": float(crossing[-1]) if completed else None,
            "flow_state": state, "had_interior_pause": intermittent,
            "largest_between_crossing_gap_s": float(np.max(gaps)) if len(gaps) else None,
            "quiet_threshold_s": quiet_s, "flow_bin_edges_s": edges.tolist(), "flow_rate_particles_s": rate.tolist(),
            "near_outlet_area_fraction_mean": float(np.mean(phi)), "near_outlet_area_fraction_series": phi.tolist(),
            "near_outlet_speed_mean_series_m_s": means.tolist(),
            "active_speed_p50_m_s": float(np.median(speed[active])) if active.any() else 0,
            "active_speed_p95_m_s": float(np.quantile(speed[active], .95)) if active.any() else 0,
            "arch": observation, "permanent_clogging_claimed": False,
            "density_definition": "Center-assigned disk area / near-outlet trapezoid area; not a 3D solid fraction."}
