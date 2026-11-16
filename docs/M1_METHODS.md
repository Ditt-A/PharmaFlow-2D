# M1 physical and numerical model

This is dry, strictly 2D soft-contact disk DEM. It is an uncalibrated research
model, not CFD, a pharmaceutical process validation, or a reproduction of the
reference paper's quasi-2D 3D-sphere DEM.

## Units and particles

All coordinates, timestamps and physical parameters use SI. Each disk has
`m = density * pi * R^2 * thickness` kg and `I = m R^2 / 2` kg m². The assumed
out-of-plane thickness is explicit; there are no front/back plates or fluid
forces. Defaults are R=0.002 m, density=2500 kg/m³, thickness=0.01 m,
m=0.000314159 kg. These are illustrative parameters, not calibrated powder data.

The staggered initial fill has spacing 2.2R plus small seeded jitter and wall
clearance. It cannot silently place more particles than the geometry fits.
There is no particle reinsertion or artificial random forcing.

## Contacts and persistent friction

For a contacting pair, `n = (xi-xj)/distance`, `t = (-ny,nx)`, and
`delta = Ri+Rj-distance > 0`. Otherwise both contact force and history vanish.
Normal force magnitude is `Fn = kn delta - gamma_n min(vn, 0)`.
The dashpot acts only on approach; separation is elastically repulsive and never
adhesive. This is intentionally not the usual full-cycle dashpot restitution
law; no analytic restitution coefficient is claimed.

Each contact has a persistent world-vector tangential spring displacement. It
is projected onto the new tangent each step, then incremented by `vt dt`.
`Ft_trial = -kt xi_t - gamma_t vt`; `Ft` is clamped to `[-mu Fn, mu Fn]`.
For sliding, spring displacement is returned to `-(Ft+gamma_t vt)/kt`, preventing
unbounded windup. History is removed at separation, particle removal or gate
opening. Projection may dissipate spring energy as a contact turns; it does
not assert exact conservative transport at finite timestep.

`vt` uses the actual contact-point velocities, including both spins. Pair
contact arms have lengths `Ri-delta/2` and `Rj-delta/2`, locating a common point
between the centers; forces are equal/opposite and torques are `-arm * Ft` on
both disks. Thus the isolated pair's total linear and angular momentum are
conserved to roundoff, including frictional exchange with spin. A wall uses its
closest point as the contact point and a separate wall friction coefficient.

Defaults: kn=1000 N/m, kt=250 N/m, gamma_n=0.15 kg/s,
gamma_t=0.03 kg/s, mu_pp=mu_wall=0.4. Energy dissipation tests include impact and
sliding. A finite-step history spring is not asserted to conserve energy in
arbitrary many-body motion; sensitivity and calibration belong to M2.

## Walls, integration and validity guards

Two sloped finite segments and two vertical segments define the hopper; a fifth
segment closes the outlet only before `gate_open_time_s`. Closest-point contact
handles circular particle interaction with the segment ends. There is no fake
floor across the open outlet. The top is open. Corners join finite segments;
more than one wall segment can contribute a contact near a junction.

Semi-implicit Euler updates velocities/spins, then positions/angles. A uniform
cell list plus Verlet skin avoids full all-pairs search each step. Candidate
pairs are sorted and rebuilt when any center moves half the skin or the active
set changes. Contact state dictionaries are CPU-side only.

The undamped normal pair contact duration is `tc = pi sqrt((m/2)/kn)`, about
0.00124512 s for defaults. The conservative guard is

`dt <= 0.05 min(sqrt(m_min/(6 max(kn,kt))), m_min/(6 max(gamma_n,gamma_t)))`.

The factor six accounts for the tangential rotational inverse effective mass
of uniform disks. This is a conservative timestep screen, not a proof that all
initial velocities/configurations are valid. Default dt=1e-5 s is below the
1.14411e-5 s limit and resolves a normal contact by about 125 steps. The solver
also fails on nonfinite state, coincident centers, overlap greater than 15% of
the smaller radius, motion above 0.25 radius per step, or center trajectories
crossing a finite wall interior. Recheck final-frame contacts before export.

An outlet event is an interpolated downward center crossing of y=0 within the
gap, counted once per particle. A disk is removed below y=-0.04 m only if it has
a recorded crossing. Active + removed always equals the initial particle count;
removed particles retain their last state for fixed array shapes. Use the active
mask when visualizing or computing local statistics. Discharged particles can
remain active below the outlet until reaching the removal plane.

## Backends and reproducibility

`cpu` is NumPy and requires no Taichi import. `taichi-cpu` and `cuda` evaluate the
same per-contact scalar laws with an f64 Taichi ndarray kernel; contact state,
neighbor search, force/torque reduction and integration remain CPU-side. This
preserves a deterministic reduction order and avoids GPU atomic summation.
Transfer and launch overhead can make this slower for small runs. No performance
gain is claimed. Explicit CUDA requests disable silent architecture fallback;
`auto` reports failures and uses NumPy. Hardware-dependent fatal driver failures
cannot always be recovered inside the same process; the environment probe runs
backends in isolated subprocesses.

NPZ files use no pickle and contain arrays:

| Key | Shape | Meaning |
| --- | --- | --- |
| time_s | F | Exact step index times dt, including initial and final frame |
| position_m, velocity_m_s | F,N,2 | Disk centers and velocities |
| angle_rad, omega_rad_s | F,N | Rotation and angular velocity |
| active | F,N | False after downstream removal |
| radius_m, mass_kg, particle_id | N | Fixed particle properties/identity |
| crossing_time_s | N | Interpolated first crossing; NaN if never discharged |
| discharged_count | F | Cumulative unique crossings |
| metadata_json | scalar string | Versioned JSON provenance |

Metadata and the JSON sidecar record config, seed, solver version, Git HEAD and
dirty flag, source hash for current runs, actual/requested duration, backend,
hardware/packages, wall time and accuracy checks. A trajectory-array SHA256
permits repeated-run comparison. Same CPU/software/config/seed runs are expected
to be bitwise reproducible; different hardware/backends are compared with
numerical tolerances. Export is for replay/analysis, not a contact-history restart.

## Validation boundary

Tests cover free fall and first-order timestep convergence, normal force,
approach-only damping, Coulomb cap/history reset, sliding dissipation/spin,
isolated elastic collision and energy, linear/angular momentum, wall rebound
and static support, wall endpoints/outlet gap, neighbor search vs brute force,
invalid parameters, NaNs/overlaps/tunneling, crossing accounting, seed
reproducibility, NPZ roundtrip, headless GIF, and optional CPU/CUDA parity.

Wide/narrow examples additionally check conservation/stability over full runs.
The arch observation requires retained particles, no crossings, a contacting
chain between both lower walls at every sampled frame, and near-outlet maximum
speed below 0.003 m/s during the final 0.2 s after gate opening. Zero flux alone
does not count. This finite-window qualitative observation does not prove
indefinite stability or define an ML training label. No reference-rate agreement
or pharmaceutical calibration is claimed; those require M2.
