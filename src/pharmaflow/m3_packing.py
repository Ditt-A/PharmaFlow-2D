"""Independent seeded packing families and explicit, controlled wall geometry."""
import hashlib
import math
import numpy as np
from .config import HopperConfig
from .dem import ParticleState, initial_state
from .geometry import hopper_walls, segment_contacts


def physical_config(parameters, numerical, seed):
    parameters = dict(parameters)
    ratio = parameters.pop('outlet_ratio')
    angle = parameters.pop('wall_angle_deg')
    if not 10 <= angle <= 65:
        raise ValueError('angle from vertical must lie in [10,65] degrees')
    radius = parameters.get('particle_radius_m', .002)
    width = parameters.get('width_m', .16)
    outlet = 2 * radius * ratio
    # Preserve inclination exactly when varying outlet width.
    height = (width - outlet) / (2 * math.tan(math.radians(angle)))
    c = HopperConfig(**dict(parameters, **numerical, seed=seed,
                           outlet_width_m=outlet, funnel_height_m=height))
    c.validate()
    return c


def make_packing(config, family):
    if family == 'staggered':
        state = initial_state(config)
    elif family in ('hexagonal', 'random_sequential'):
        rng = np.random.default_rng(config.seed)
        r = config.particle_radius_m
        walls = hopper_walls(config, 0)
        points = []
        if family == 'hexagonal':
            step = 2.2*r
            candidates = []
            for row, y in enumerate(np.arange(3*r, config.height_m-2*r, step*np.sqrt(3)/2)):
                xs = np.arange(-config.width_m/2+2*r, config.width_m/2-2*r, step)+(row%2)*step/2
                # Independent row phase and randomized truncation order, not small jitter.
                xs = xs + rng.uniform(-.3*r,.3*r)
                for x in rng.permutation(xs):
                    candidates.append((x,y))
        else:
            candidates = ((rng.uniform(-config.width_m/2,config.width_m/2),rng.uniform(3*r,.055)) for _ in range(100000))
        for candidate in candidates:
            point = np.asarray(candidate,dtype=float)
            if point[1] <= 0 or point[1] >= config.height_m-r:
                continue
            half = min(config.width_m/2,config.outlet_width_m/2+(config.width_m-config.outlet_width_m)/2*point[1]/config.funnel_height_m)
            if abs(point[0]) >= half:
                continue
            distance,_,_ = segment_contacts(point[None],walls)
            if np.min(distance) < 1.05*r:
                continue
            if points and np.min(np.linalg.norm(np.asarray(points)-point,axis=1)) < 2.05*r:
                continue
            points.append(point)
            if len(points) == config.n_particles:
                break
        if len(points) != config.n_particles:
            raise ValueError('packing rejected: requested particle count does not fit')
        state = ParticleState.create(points,r,config.particle_mass_kg)
    else:
        raise ValueError('unknown packing family: '+family)
    digest=hashlib.sha256()
    for value in (state.position,state.velocity,state.radius,state.mass,state.angle,state.omega):digest.update(value.tobytes())
    return state,digest.hexdigest()
