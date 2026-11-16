"""Deterministic, soft-contact 2D disk DEM with semi-implicit Euler integration."""
from dataclasses import dataclass
import warnings
import numpy as np
from .config import HopperConfig
from .contact import contact_response
from .geometry import hopper_walls, segment_contacts, check_wall_crossings
from .neighbors import NeighborList


@dataclass
class ParticleState:
    position: np.ndarray
    velocity: np.ndarray
    radius: np.ndarray
    mass: np.ndarray
    angle: np.ndarray
    omega: np.ndarray
    active: np.ndarray

    @classmethod
    def create(cls, positions, radius, mass, velocities=None, omega=None):
        x = np.asarray(positions, dtype=float).copy()
        n = len(x)
        return cls(x, np.zeros_like(x) if velocities is None else np.asarray(velocities, dtype=float).copy(),
                   np.broadcast_to(radius, (n,)).astype(float).copy(),
                   np.broadcast_to(mass, (n,)).astype(float).copy(), np.zeros(n),
                   np.zeros(n) if omega is None else np.broadcast_to(omega, (n,)).astype(float).copy(),
                   np.ones(n, dtype=bool))

    @property
    def inertia(self):
        return 0.5 * self.mass * self.radius**2

    def validate(self):
        n = len(self.position)
        if n < 1 or self.position.shape != (n, 2) or self.velocity.shape != (n, 2):
            raise ValueError("positions and velocities must be nonempty (N, 2) arrays")
        for name in ("radius", "mass", "angle", "omega", "active"):
            if getattr(self, name).shape != (n,):
                raise ValueError(f"invalid {name} shape")
        for name in ("position", "velocity", "radius", "mass", "angle", "omega"):
            if not np.all(np.isfinite(getattr(self, name))):
                raise ValueError(f"nonfinite particle {name}")
        if np.any(self.radius <= 0) or np.any(self.mass <= 0):
            raise ValueError("particle radii and masses must be positive")


def initial_state(config):
    """Seeded, non-overlapping staggered lattice inside the finite hopper walls."""
    rng = np.random.default_rng(config.seed)
    r, spacing = config.particle_radius_m, 2.2 * config.particle_radius_m
    positions = []
    walls = hopper_walls(config, 0)
    for row, y in enumerate(np.arange(3 * r, config.height_m - 2 * r, spacing)):
        half = min(config.width_m / 2, config.outlet_width_m / 2 +
                   (config.width_m - config.outlet_width_m) / 2 * y / config.funnel_height_m)
        xs = np.arange(-half + 2 * r, half - 2 * r, spacing) + (row % 2) * spacing / 2
        for x in xs:
            point = np.array([x, y]) + rng.uniform(-0.025 * r, 0.025 * r, 2)
            distance, _, _ = segment_contacts(point[None], walls)
            if np.min(distance) >= 1.05 * r:
                positions.append(point)
            if len(positions) == config.n_particles:
                return ParticleState.create(positions, r, config.particle_mass_kg)
    raise ValueError("particle count does not fit initial hopper fill")


class DEMSystem:
    def __init__(self, config=None, state=None, walls=None, backend="cpu", track_outlet=True):
        self.config = HopperConfig() if config is None else config
        self.config.validate()
        self.state = initial_state(self.config) if state is None else state
        self.state.validate()
        if self.config.dt_s > self.config.timestep_limit_s(float(np.min(self.state.mass))):
            raise ValueError("dt exceeds stability limit for actual particle masses")
        self.fixed_walls = None if walls is None else np.asarray(walls, dtype=float).reshape(-1, 2, 2)
        self.track_outlet = track_outlet
        self.step_index = 0
        self.history = {}
        self.neighbors = NeighborList(self.config.neighbor_skin_m)
        self.crossing_time = np.full(len(self.state.mass), np.nan)
        self.max_overlap_ratio = 0.0
        self.max_step_ratio = 0.0
        self.response = contact_response
        self.backend = "numpy-cpu"
        self.backend_note = None
        if backend not in ("cpu", "auto", "cuda", "taichi-cpu"):
            raise ValueError("backend must be cpu, auto, cuda or taichi-cpu")
        if backend != "cpu":
            try:
                from .taichi_backend import TaichiContacts
                self.response = TaichiContacts("cpu" if backend == "taichi-cpu" else "cuda")
                self.backend = self.response.name
            except Exception as error:
                if backend != "auto":
                    raise RuntimeError(f"Taichi {backend} unavailable; use --backend cpu: {error}") from error
                self.backend_note = str(error)
                warnings.warn(f"CUDA unavailable; using NumPy CPU: {error}", RuntimeWarning)

    @property
    def time_s(self):
        return self.step_index * self.config.dt_s

    @property
    def walls(self):
        return hopper_walls(self.config, self.time_s) if self.fixed_walls is None else self.fixed_walls

    def forces(self):
        s, c = self.state, self.config
        force = np.zeros_like(s.position)
        force[s.active, 1] = -s.mass[s.active] * c.gravity_m_s2
        torque = np.zeros(len(s.mass))
        pairs = self.neighbors.get(s.position, s.radius, s.active)
        i, j = pairs[:, 0], pairs[:, 1]
        delta = s.position[i] - s.position[j]
        distance = np.linalg.norm(delta, axis=1)
        overlap = s.radius[i] + s.radius[j] - distance
        keep = (overlap > 0) & s.active[i] & s.active[j]
        if np.any(keep & (distance < 1e-15)):
            raise RuntimeError("coincident particle centers")
        i, j, overlap, distance = i[keep], j[keep], overlap[keep], distance[keep]
        normal = delta[keep] / distance[:, None]
        pair_count = len(i)
        li, lj = s.radius[i] - overlap / 2, s.radius[j] - overlap / 2
        relative_v = s.velocity[i] - s.velocity[j]
        scale = np.minimum(s.radius[i], s.radius[j])
        mu = np.full(pair_count, c.friction)
        wd, wn, _ = segment_contacts(s.position, self.walls)
        wi, wall = np.nonzero((wd < s.radius[:, None]) & s.active[:, None])
        wo = s.radius[wi] - wd[wi, wall]
        if np.any(wd[wi, wall] < 1e-15):
            raise RuntimeError("particle center lies on wall")
        # Wall contact point is the closest segment point, so lever length = distance.
        li = np.concatenate((li, wd[wi, wall]))
        lj = np.concatenate((lj, np.zeros(len(wi))))
        normal = np.concatenate((normal, wn[wi, wall]))
        relative_v = np.concatenate((relative_v, s.velocity[wi]))
        overlap = np.concatenate((overlap, wo))
        scale = np.concatenate((scale, s.radius[wi]))
        mu = np.concatenate((mu, np.full(len(wi), c.wall_friction)))
        i, j = np.concatenate((i, wi)), np.concatenate((j, -wall - 1))
        if not len(i):
            self.history = {}
            return force, torque
        ratio = float(np.max(overlap / scale))
        self.max_overlap_ratio = max(self.max_overlap_ratio, ratio)
        if ratio > c.max_overlap_ratio:
            raise RuntimeError(f"excessive overlap {ratio:.4g} radii (limit {c.max_overlap_ratio})")
        tangent = np.column_stack((-normal[:, 1], normal[:, 0]))
        vn = np.sum(relative_v * normal, axis=1)
        vt = np.sum(relative_v * tangent, axis=1) - s.omega[i] * li
        vt[:pair_count] -= s.omega[j[:pair_count]] * lj[:pair_count]
        keys = list(zip(i.tolist(), j.tolist()))
        old = np.array([self.history.get(key, (0.0, 0.0)) for key in keys])
        displacement = np.sum(old * tangent, axis=1)
        fn, ft, xi = self.response(overlap, vn, vt, displacement, mu, c.dt_s,
                                  c.normal_stiffness_n_m, c.tangential_stiffness_n_m,
                                  c.normal_damping_kg_s, c.tangential_damping_kg_s)
        contact_force = fn[:, None] * normal + ft[:, None] * tangent
        np.add.at(force, i, contact_force)
        np.add.at(torque, i, -li * ft)
        np.add.at(force, j[:pair_count], -contact_force[:pair_count])
        np.add.at(torque, j[:pair_count], -lj[:pair_count] * ft[:pair_count])
        self.history = dict(zip(keys, xi[:, None] * tangent))
        return force, torque

    def step(self):
        s, c = self.state, self.config
        if not all(np.all(np.isfinite(a)) for a in (s.position, s.velocity, s.angle, s.omega)):
            raise RuntimeError("nonfinite DEM state")
        previous, walls = s.position.copy(), self.walls
        force, torque = self.forces()
        s.velocity[s.active] += c.dt_s * force[s.active] / s.mass[s.active, None]
        s.omega[s.active] += c.dt_s * torque[s.active] / s.inertia[s.active]
        s.position[s.active] += c.dt_s * s.velocity[s.active]
        s.angle[s.active] += c.dt_s * s.omega[s.active]
        if not all(np.all(np.isfinite(a)) for a in (s.position, s.velocity, s.angle, s.omega)):
            raise RuntimeError("nonfinite integrated DEM state")
        step_ratio = float(np.max(np.linalg.norm(s.position - previous, axis=1) / s.radius))
        self.max_step_ratio = max(self.max_step_ratio, step_ratio)
        if step_ratio > 0.25:
            raise RuntimeError("particle moves > 0.25 radius per step; reduce dt")
        check_wall_crossings(previous[s.active], s.position[s.active], walls)
        if self.track_outlet:
            eligible = s.active & np.isnan(self.crossing_time) & (previous[:, 1] >= 0) & (s.position[:, 1] < 0)
            ids = np.flatnonzero(eligible)
            alpha = previous[ids, 1] / (previous[ids, 1] - s.position[ids, 1])
            x = previous[ids, 0] + alpha * (s.position[ids, 0] - previous[ids, 0])
            accepted = np.abs(x) < c.outlet_width_m / 2
            self.crossing_time[ids[accepted]] = self.time_s + alpha[accepted] * c.dt_s
            removed = s.active & (s.position[:, 1] < c.removal_y_m)
            if np.any(removed & np.isnan(self.crossing_time)):
                raise RuntimeError("particle left domain without crossing outlet")
            s.active[removed] = False
        self.step_index += 1

    def advance(self, steps):
        for _ in range(steps):
            self.step()
        return self.state
