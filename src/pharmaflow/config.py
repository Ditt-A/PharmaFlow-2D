"""SI parameters for disks of material density and explicit finite thickness."""
from dataclasses import dataclass, asdict
import math

@dataclass(frozen=True)
class HopperConfig:
    width_m: float = 0.16
    height_m: float = 0.24
    outlet_width_m: float = 0.03
    particle_radius_m: float = 0.002
    gravity_m_s2: float = 9.81
    dt_s: float = 1e-5
    funnel_height_m: float = 0.10
    density_kg_m3: float = 2500.0
    thickness_m: float = 0.01
    normal_stiffness_n_m: float = 1000.0
    tangential_stiffness_n_m: float = 250.0
    normal_damping_kg_s: float = 0.15
    tangential_damping_kg_s: float = 0.03
    friction: float = 0.4
    wall_friction: float = 0.4
    n_particles: int = 100
    seed: int = 42
    gate_open_time_s: float = 0.05
    removal_y_m: float = -0.04
    neighbor_skin_m: float = 0.001
    max_overlap_ratio: float = 0.15

    @property
    def particle_mass_kg(self):
        return self.density_kg_m3 * math.pi * self.particle_radius_m**2 * self.thickness_m

    @property
    def contact_time_s(self):
        """Undamped normal half-period for two equal disks (not restitution)."""
        return math.pi * math.sqrt(self.particle_mass_kg / (2 * self.normal_stiffness_n_m))

    def timestep_limit_s(self, min_mass_kg=None):
        # m/6 includes the rotational tangential inverse effective mass of disks.
        mass = self.particle_mass_kg if min_mass_kg is None else min_mass_kg
        spring = math.sqrt(mass / (6 * max(self.normal_stiffness_n_m, self.tangential_stiffness_n_m)))
        damping = mass / (6 * max(self.normal_damping_kg_s, self.tangential_damping_kg_s, 1e-30))
        return 0.05 * min(spring, damping)

    def validate(self):
        if any(not math.isfinite(float(value)) for value in asdict(self).values()):
            raise ValueError("all parameters must be finite")
        if not (self.width_m > self.outlet_width_m > 2 * self.particle_radius_m > 0):
            raise ValueError("invalid width/outlet/radius")
        if not (0 < self.funnel_height_m < self.height_m):
            raise ValueError("funnel height must lie inside hopper")
        positive = (self.dt_s, self.density_kg_m3, self.thickness_m, self.normal_stiffness_n_m,
                    self.tangential_stiffness_n_m, self.neighbor_skin_m)
        if min(positive) <= 0:
            raise ValueError("mass, stiffness, skin and timestep must be positive")
        if min(self.gravity_m_s2, self.friction, self.wall_friction, self.normal_damping_kg_s,
               self.tangential_damping_kg_s, self.gate_open_time_s) < 0:
            raise ValueError("gravity, friction, damping and gate time must be nonnegative")
        if not isinstance(self.n_particles, int) or self.n_particles < 1:
            raise ValueError("n_particles must be a positive integer")
        if not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        if not 0 < self.max_overlap_ratio <= 0.25 or self.removal_y_m >= -2 * self.particle_radius_m:
            raise ValueError("invalid overlap tolerance or removal plane")
        if self.dt_s > self.timestep_limit_s():
            raise ValueError(f"unstable dt: use dt <= {self.timestep_limit_s():.6g} s")
