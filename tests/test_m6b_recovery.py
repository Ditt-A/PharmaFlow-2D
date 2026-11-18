"""Recovered actual summaries, conservative units and malformed-summary guards."""
from pathlib import Path
import numpy as np
import pytest
from pharmaflow.m6b_recovery import validate_fixed_grain_arrays,parse_recovered_fixed_grain


@pytest.mark.parametrize('x,m,s',[
    ([0,1],[1],[.1,.2]),([0,0],[1,2],[.1,.2]),
    ([1,0],[1,2],[.1,.2]),([0,1],[1,np.nan],[.1,.2]),
    ([0,1],[1,2],[.1,-.2]),([0,1],[-1,2],[.1,.2]),
])
def test_malformed_experimental_summary_rejected(x,m,s):
    with pytest.raises(ValueError):validate_fixed_grain_arrays(x,m,s)


def test_actual_recovered_official_files():
    directory=Path(__file__).resolve().parents[1]/'data/raw/m6b/recovery'
    if not (directory/'README.md').exists():pytest.skip('User-provided official raw files are not present on this checkout')
    rows,files=parse_recovered_fixed_grain(directory)
    assert len(rows)==17 and len(files)==4 and sum(f['bytes'] for f in files)==6699
    assert all(f['provider_checksum_verified'] for f in files)
    assert rows[0]['fixed_grain_distance_over_dFG']==pytest.approx(.06)
    peak=max(rows,key=lambda r:r['normalized_mean_ejected_mass'])
    assert peak['fixed_grain_distance_over_dFG']==pytest.approx(.66)
    assert peak['normalized_mean_ejected_mass']==pytest.approx(1.704679980957189)
    assert peak['reported_standard_error']==pytest.approx(.07697811656707769)
    assert all('time_s' not in r and 'particle_id' not in r for r in rows)
