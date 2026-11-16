"""Finite line segments: real outlet gap, circular lips, optional settling gate."""
import numpy as np


def hopper_walls(config, time_s):
    w, o, h, f = config.width_m / 2, config.outlet_width_m / 2, config.height_m, config.funnel_height_m
    segments = [((-o, 0), (-w, f)), ((w, f), (o, 0)),
                ((-w, f), (-w, h)), ((w, h), (w, f))]
    if time_s < config.gate_open_time_s:
        segments.append(((-o, 0), (o, 0)))
    return np.asarray(segments, dtype=float)


def segment_contacts(positions, walls):
    """Return distances, outward contact normals, and segment projection."""
    if len(walls) == 0:
        shape = (len(positions), 0)
        return np.empty(shape), np.empty(shape + (2,)), np.empty(shape)
    start, direction = walls[:, 0], walls[:, 1] - walls[:, 0]
    length2 = np.sum(direction**2, axis=1)
    if np.any(length2 <= 0):
        raise ValueError("wall segments must have nonzero length")
    relative = positions[:, None, :] - start
    projection = np.sum(relative * direction, axis=2) / length2
    closest = start + np.clip(projection, 0, 1)[..., None] * direction
    delta = positions[:, None, :] - closest
    distance = np.linalg.norm(delta, axis=2)
    normal = delta / np.maximum(distance[..., None], 1e-30)
    return distance, normal, projection


def check_wall_crossings(previous, current, walls):
    """Catch center trajectories crossing segment interiors, in either direction."""
    if not len(walls):
        return
    start, direction = walls[:, 0], walls[:, 1] - walls[:, 0]
    relative0, relative1 = previous[:, None] - start, current[:, None] - start
    side0 = direction[:, 0] * relative0[..., 1] - direction[:, 1] * relative0[..., 0]
    side1 = direction[:, 0] * relative1[..., 1] - direction[:, 1] * relative1[..., 0]
    crosses = side0 * side1 <= 0
    alpha = np.divide(side0, side0 - side1, out=np.zeros_like(side0), where=(side0 != side1))
    intersection = relative0 + alpha[..., None] * (relative1 - relative0)
    u = np.sum(intersection * direction, axis=2) / np.sum(direction**2, axis=1)
    if np.any(crosses & (side0 != side1) & (u > 1e-10) & (u < 1 - 1e-10)):
        raise RuntimeError("wall tunneling detected; reduce dt / initial velocities")
