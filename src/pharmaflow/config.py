from dataclasses import dataclass

@dataclass(frozen=True)
class HopperConfig:
    width_m: float = 0.16
    height_m: float = 0.24
    outlet_width_m: float = 0.03
    particle_radius_m: float = 0.002
    gravity_m_s2: float = 9.81
    dt_s: float = 1e-5

    def validate(self):
        if not (self.width_m > self.outlet_width_m > 2 * self.particle_radius_m > 0):
            raise ValueError("invalid width/outlet/radius")
        if min(self.height_m, self.gravity_m_s2, self.dt_s) <= 0:
            raise ValueError("height, gravity, dt must be positive")
