"""Read-only physical benchmark definitions, evidence gates and grouped summaries."""
import math
import re
from html import unescape
import numpy as np


VALIDATION_GATES = ('units_verified', 'boundary_and_definition_matched', 'geometry_matched',
                    'particle_system_matched', 'averaging_matched', 'data_quality_verified',
                    'experimental_uncertainty_available', 'numerical_sensitivity_bounded')


def quantitative_eligibility(evidence):
    """Unknown is not equivalent to verified. A measured value is not a calibration."""
    reasons = [key for key in VALIDATION_GATES if evidence.get(key) is not True]
    return dict(quantitative_validation_allowed=not reasons, unresolved_or_failed_gates=reasons,
                calibration_claim_allowed=False, fitting_performed=False)


def crossing_rates(crossing_times_s, edges_s, crossing_masses_kg=None):
    """Count observed crossing events in (a,b]; NaN denotes an uncrossed particle.

    Historical DEM times are UNIQUE first downward crossings. A recirculating
    experiment must instead supply every passage and reconcile its boundary.
    """
    times, edges = np.asarray(crossing_times_s, float), np.asarray(edges_s, float)
    if times.ndim != 1 or edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all() or np.any(np.diff(edges) <= 0):
        raise ValueError('Invalid crossing time/bin geometry')
    if np.isinf(times).any() or np.any(times[np.isfinite(times)] < 0):
        raise ValueError('Invalid event timestamps')
    keep = np.isfinite(times)
    t = times[keep]
    count = np.array([np.count_nonzero((t > a) & (t <= b)) for a,b in zip(edges[:-1],edges[1:])])
    result = dict(start_s=edges[:-1], end_s=edges[1:], count=count, number_rate_s=count/np.diff(edges))
    if crossing_masses_kg is not None:
        masses = np.asarray(crossing_masses_kg, float)
        if masses.shape != times.shape or not np.isfinite(masses).all() or np.any(masses <= 0):
            raise ValueError('Every crossing needs a known individual mass')
        result['mass_rate_kg_s'] = np.array([masses[keep][(t>a)&(t<=b)].sum()/(b-a) for a,b in zip(edges[:-1],edges[1:])])
    return result


def grouped_summary(values, independent_groups, seed=20261117, draws=2000):
    """Equal-weight independent-group means; never bootstrap correlated frames."""
    values = np.asarray(values, float)
    groups = np.asarray(independent_groups)
    if values.ndim != 1 or values.shape != groups.shape or not len(values) or not np.isfinite(values).all():
        raise ValueError('Finite, aligned observations and independent groups required')
    means = np.array([values[groups==g].mean() for g in np.unique(groups)])
    n = len(means)
    result = dict(independent_groups=n, observations=len(values), mean=float(means.mean()),
                  sample_sd=float(means.std(ddof=1)) if n>1 else None, ci95=None)
    if n > 1:
        if draws < 100:
            raise ValueError('Use at least 100 cluster draws')
        rng = np.random.default_rng(seed)
        boot = means[rng.integers(n,size=(draws,n))].mean(axis=1)
        result['ci95'] = np.quantile(boot,[.025,.975]).tolist()
    return result


def steady_flow_support(trace, config, protocol):
    """Prespecified finite-fill screening, not proof of a universal steady state."""
    t = np.asarray(trace['time_s'],float)
    count = np.asarray(trace['discharged_count'],float)
    remaining = np.asarray(trace['remaining_count'],float)
    if t.ndim!=1 or len(t)<2 or t.shape!=count.shape or t.shape!=remaining.shape or not np.isfinite([t,count,remaining]).all():
        raise ValueError('Invalid observed discharge trace')
    if (np.any(np.diff(t)<=0) or np.any(np.diff(count)<0) or np.any(count<0) or np.any(remaining<0)
            or np.any(count!=np.rint(count)) or np.any(remaining!=np.rint(remaining))):
        raise ValueError('Invalid chronology/counts')
    start = int(np.searchsorted(t,config.gate_open_time_s+protocol['post_gate_buffer_s'],side='left'))
    depletion = np.flatnonzero(remaining < protocol['minimum_retained_fraction']*config.n_particles)
    end = int(depletion[0]-1) if len(depletion) else len(t)-1
    reasons=[]
    duration = float(t[end]-t[start]) if 0<=start<end<len(t) else 0.
    crossings = int(count[end]-count[start]) if duration>0 else 0
    if duration < protocol['minimum_window_s']-1e-12:reasons.append('insufficient_duration_before_depletion')
    if crossings < protocol['minimum_crossings']:reasons.append('insufficient_independent_crossings')
    block_rates=[];maximum_gap=None
    if duration>0:
        observed = t[start+1:end+1][np.diff(count[start:end+1])>0]
        maximum_gap=float(np.diff(np.r_[t[start],observed,t[end]]).max())
        if maximum_gap>protocol['maximum_crossing_gap_s']+1e-12:reasons.append('flow_interruption_or_arch_tail')
        width=protocol['block_s'];nblocks=int(math.floor((duration+1e-12)/width))
        for j in range(nblocks):
            a,b=t[start]+j*width,t[start]+(j+1)*width
            ia=int(np.searchsorted(t,a,side='right')-1);ib=int(np.searchsorted(t,b,side='right')-1)
            block_rates.append(float((count[ib]-count[ia])/width))
    cv=drift=None
    if len(block_rates)>=protocol['minimum_blocks'] and np.mean(block_rates)>0:
        cv=float(np.std(block_rates,ddof=1)/np.mean(block_rates))
        drift=float(abs(block_rates[-1]-block_rates[0])/np.mean(block_rates))
        if cv>protocol['maximum_block_cv']:reasons.append('nonstationary_block_rates')
        if drift>protocol['maximum_end_block_drift']:reasons.append('flow_drift')
    else:reasons.append('insufficient_nonzero_rate_blocks')
    return dict(eligible_for_scaling=not reasons, reasons=reasons, usable_window_s=duration,
                observed_crossings=crossings, block_rates_s=block_rates, block_cv=cv, end_block_drift=drift,
                maximum_sampled_crossing_gap_s=maximum_gap,
                post_gate_buffer_s=protocol['post_gate_buffer_s'], fitting_performed=False)


def delft_file_inventory(page, record_url):
    """Read only advertised file entries; never follow archive download links."""
    from urllib.parse import urljoin
    pattern = (r'<li>\s*<span class="size">\s*([\d,]+) bytes\s*</span>.*?'
               r'<code>\s*([a-f0-9]{32})\s*</code>.*?'
               r'<a[^>]*href="(/file/[^\"]+)"[^>]*>\s*([^<]+)\s*</a>\s*</li>')
    return [dict(name=unescape(name.strip()), bytes=int(size.replace(',','')),
                 published_checksum='md5:'+md5, url=urljoin(record_url,url))
            for size,md5,url,name in re.findall(pattern,page,re.S)]


def delft_acquisition_info(text):
    """Headerless rows stay provisional; pixel coordinates are not physical units."""
    headered='framerate' in text.lower()
    result=[]
    seen=set()
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('%'):continue
        fields=re.findall(r'[-+]?\d+(?:\.\d+)?',line)
        if len(fields)<2:raise ValueError('Unrecognized acquisition metadata row')
        if int(fields[0])<=0 or float(fields[1])<=0 or int(fields[0]) in seen:
            raise ValueError('Invalid or duplicated acquisition metadata')
        seen.add(int(fields[0]))
        result.append(dict(run_index=int(fields[0]),recorded_rate_value=float(fields[1]),
                           sampling_hz=float(fields[1]) if headered else None,
                           header_verified=headered,
                           note='Frame-rate header present' if headered else 'Headerless annotation; frequency interpretation provisional'))
    return result
