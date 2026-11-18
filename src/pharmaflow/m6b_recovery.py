"""Verified user-provided Cornerstones summaries; no network, DEM or fitting."""
from pathlib import Path
import numpy as np
from .m6b_data import file_hash

SOURCE_FILES={
    'README.md':(5424,'d84a2a16eac6a1e8d34d9425375063a3a6fbbcad9cfa14993f7c0ce7ed397fe3'),
    'BinCenters.txt':(425,'d4d983b80f5b35592aca1024d71e507de7ef861bdfdb1e2179b043723a9e3ec4'),
    'Dimensionless_M.txt':(425,'a8afd9b86ccd7180b027d8556fb804db4a90795a89d4f12cf6ac3f54451c189f'),
    'Dimensionless_M_std_error.txt':(425,'528a57b77f8ef14ea83123ac0614d63a3a6c6c91db7d6e2daa23ea0e60b8cba3'),
}


def validate_fixed_grain_arrays(position,ratio,standard_error):
    """Validate summaries, never reinterpret positions as timestamps or SEM as CI."""
    x,m,s=(np.asarray(v,float) for v in (position,ratio,standard_error))
    if x.ndim!=1 or len(x)<2 or m.shape!=x.shape or s.shape!=x.shape:
        raise ValueError('Aligned one-dimensional summary arrays required')
    if not all(np.isfinite(v).all() for v in (x,m,s)):
        raise ValueError('Nonfinite experimental summary value')
    if np.any(np.diff(x)<=0):raise ValueError('Bin centers must increase strictly')
    if np.any(m<0) or np.any(s<0):raise ValueError('Mass ratios and standard errors must be nonnegative')
    return x,m,s


def parse_recovered_fixed_grain(directory):
    """Semantics pinned to the official README and companion notebook cells 14/18.

    x is distance from outlet edge divided by fixed-grain diameter. The source
    labels y normalized ejected mass; no kg conversion, trajectory or event
    denominator is inferred. All 17 aggregate bins are retained.
    """
    directory=Path(directory);provenance=[]
    for name,(size,sha) in SOURCE_FILES.items():
        p=directory/name
        actual=file_hash(p)
        if p.stat().st_size!=size or actual!=sha:
            raise ValueError('Published Dryad size/SHA-256 mismatch: '+name)
        provenance.append(dict(file=name,bytes=size,sha256=actual,provider_checksum_verified=True,
            access_method='user_supplied_local_download',http_status_observed_by_pipeline=None,
            license='CC0 1.0',provider_version=376462))
    x,m,s=validate_fixed_grain_arrays(*(np.loadtxt(directory/name,ndmin=1) for name in
        ('BinCenters.txt','Dimensionless_M.txt','Dimensionless_M_std_error.txt')))
    rows=[dict(bin_index=int(i),fixed_grain_distance_over_dFG=float(a),
              normalized_mean_ejected_mass=float(b),reported_standard_error=float(c))
          for i,(a,b,c) in enumerate(zip(x,m,s))]
    return rows,provenance
