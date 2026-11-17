"""Explicit physical conversions for external benchmarks; never infer unknown units."""
import math
import numpy as np


def positive(value, name):
    if isinstance(value, (bool,np.bool_)):
        raise ValueError(name + ' must be numeric, not boolean')
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(name + ' must be known') from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name + ' must be finite and positive')
    return value


def length_to_m(value, unit):
    factors = {'m': 1., 'cm': .01, 'mm': .001}
    if unit not in factors:
        raise ValueError('Unverified/unsupported length unit: ' + str(unit))
    a = np.asarray(value, dtype=float)
    if not np.isfinite(a).all():
        raise ValueError('Nonfinite length')
    return a * factors[unit]


def velocity_to_m_s(value, unit, sampling_hz=None):
    factors = {'m/s': 1., 'cm/s': .01, 'mm/s': .001}
    if unit in factors:
        factor = factors[unit]
    elif unit == 'mm/frame':
        factor = .001 * positive(sampling_hz, 'sampling frequency')
    else:
        raise ValueError('Unverified/unsupported velocity unit: ' + str(unit))
    a = np.asarray(value, dtype=float)
    if not np.isfinite(a).all():
        raise ValueError('Nonfinite velocity')
    return a * factor


def disk_mass_kg(diameter_m, density_kg_m3, physical_thickness_m):
    """Cylinder/disk mass. Plate separation is NOT interchangeable with thickness."""
    d = positive(diameter_m, 'diameter')
    return math.pi * d*d/4 * positive(density_kg_m3, 'material density') * positive(physical_thickness_m, 'disk thickness')


def number_to_mass_rate(number_rate_s, particle_mass_kg):
    """Only a known constant per-particle mass permits this monodisperse conversion."""
    if np.ndim(particle_mass_kg) != 0:
        raise ValueError('Mixtures require individual crossing masses, not a mass array/mean shortcut')
    q = np.asarray(number_rate_s, dtype=float)
    if not np.isfinite(q).all() or np.any(q < 0):
        raise ValueError('Invalid number rate')
    return q * positive(particle_mass_kg, 'known particle mass')


def normalized_number_rate(number_rate_s, diameter_m, gravity_m_s2):
    q=np.asarray(number_rate_s,dtype=float)
    if not np.isfinite(q).all() or np.any(q<0):raise ValueError('Invalid number rate')
    return q * math.sqrt(positive(diameter_m, 'diameter') / positive(gravity_m_s2, 'gravity'))


def bulk_areal_density(material_density_kg_m3, thickness_m, bulk_area_fraction):
    phi = positive(bulk_area_fraction, 'bulk area fraction')
    if phi > 1:
        raise ValueError('Use a physical bulk area fraction, not an unbounded occupancy estimator')
    return positive(material_density_kg_m3, 'density') * positive(thickness_m, 'physical thickness') * phi


def normalized_mass_rate_2d(mass_rate_kg_s, bulk_areal_density_kg_m2, diameter_m, gravity_m_s2):
    denominator = positive(bulk_areal_density_kg_m2, 'bulk areal density') * math.sqrt(positive(gravity_m_s2, 'gravity')) * positive(diameter_m, 'diameter')**1.5
    q=np.asarray(mass_rate_kg_s,dtype=float)
    if not np.isfinite(q).all() or np.any(q<0):raise ValueError('Invalid mass rate')
    return q / denominator


def beverloo_mass_2d(outlet_m, diameter_m, gravity_m_s2, bulk_areal_density_kg_m2, coefficient, offset):
    """Dimensional 2D candidate, NOT a calibrated universal law or clog predictor.

    All constants must be supplied. It is undefined for D <= k*d. Returning zero
    there would incorrectly treat clogged states as free-flow regression samples.
    """
    d = positive(diameter_m, 'diameter')
    k = float(offset)
    D = np.asarray(outlet_m, dtype=float)
    if not math.isfinite(k) or k < 0 or not np.isfinite(D).all() or np.any(D <= k*d) or np.any(D <= 0):
        raise ValueError('Free-flow scaling requires finite D > k*d >=' + str(k*d))
    return (positive(coefficient, 'empirical coefficient') * positive(bulk_areal_density_kg_m2, 'bulk areal density')
            * math.sqrt(positive(gravity_m_s2, 'gravity')) * (D-k*d)**1.5)
