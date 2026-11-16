"""Linear normal spring, approach damping, history spring and Coulomb friction."""
import numpy as np


def contact_response(overlap, vn, vt, history, friction, dt, kn, kt, gn, gt):
    """Contact histories are scalar displacements projected onto current tangents.

    All inputs are arrays of active contacts. Normal points from j/wall to i.
    Damping acts only during approach, so separation cannot produce adhesion.
    Sliding returns the spring to the Coulomb surface, avoiding windup.
    """
    fn = kn * overlap - gn * np.minimum(vn, 0.0)
    xi = history + vt * dt
    trial = -kt * xi - gt * vt
    ft = np.clip(trial, -friction * fn, friction * fn)
    xi = np.where(np.abs(trial) > friction * fn, -(ft + gt * vt) / kt, xi)
    return fn, ft, xi
