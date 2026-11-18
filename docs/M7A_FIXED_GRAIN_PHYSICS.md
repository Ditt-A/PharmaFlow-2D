# M7A fixed-grain physics verification

The legacy `dem.py`, `contact.py`, `geometry.py`, configuration and historical
solver/label modules are unchanged. The new `fixed_grain.py` subclass supplies
an immobile circular boundary and selectable ideal flat-floor geometry. Wedge
mode without an obstacle is checked bit-for-bit through actual wall contacts.

## Contact mechanics

The fixed grain is an immutable center/radius/friction object outside
`ParticleState`. It has no position integration, velocity, angular state or
post-step freezing operation. Its contact reaction goes to an external support;
it is excluded from mobile particle counts and mass.

For mobile grain i and obstacle o:

```text
delta = R_i + R_o - ||r_i-r_o|| > 0
n = (r_i-r_o)/||r_i-r_o||,  t = (-n_y,n_x)
l_i = R_i-delta/2
v_n = v_i dot n
v_t = v_i dot t - omega_i*l_i
F_n = k_n*delta - gamma_n*min(v_n,0)
xi_new = projected_previous_xi + v_t*dt
F_t = clip(-k_t*xi_new-gamma_t*v_t, -mu_o*F_n, +mu_o*F_n)
F_i += F_n*n + F_t*t
tau_i += -l_i*F_t
```

Sliding returns the tangential spring to the Coulomb surface, as in the existing
contact response. Vector history projects onto the current tangent; histories
are keyed separately by mobile ID and removed on separation. No contact history
is shared with an unrelated floor contact. Passive graphs/visualization do not
advance friction memory. Torque uses the same midpoint lever convention as
legacy disk-disk contacts. The prescribed nonrotating obstacle's reaction torque
is recorded separately; the support's mechanical work is zero at zero prescribed
linear/angular velocity.

Mobile-particle momentum alone is **not** conserved in this supported system.
In isolated impact tests, mobile momentum change plus integrated obstacle
reaction is conserved to floating-point precision. This checks force/impulse
accounting, not a physically isolated hopper.

## Safeguards and numerical assumptions

Pilot kn=4000 N/m, kt=1000 N/m, gamma_n=0.15 kg/s, gamma_t=0.03 kg/s,
mu_pp=mu_wall=mu_fixed=0.4. These are uncalibrated numerical/material assumptions,
not measured restitution/friction. Gravity is 9.81 m/s2. No drag, cohesion,
front/back friction, rolling resistance or vibration law is added.

The .15-radius overlap guard remains unchanged, normalized by the smaller
contacting radius for disk/obstacle contacts. It is checked both before force
evaluation and after integration, including the final step. Coincident centers,
nonfinite state/forces, excessive step displacement, wall tunneling and removal
without a unique outlet crossing fail the run. Failed attempts remain charged.

Polydisperse mobile states already fit the legacy array-based mass/inertia and
neighbor APIs; the new packing supplies actual radii and cylinder masses.
The smallest species sets dt_limit=2.967140e-6s. Pilot dt=2.5e-6s respects that
guard. No nominal mean mass substitutes for the smallest mass, or for actual
ejected masses. Mixture/timestep and unequal-mass discharge tests verify this.

## Analytic and implementation checks

An elastic, frictionless 6ms disk/fixed-disk impact at dt=10/5/2.5 microseconds
gives maximum relative mechanical-energy excursions **0.900050%, 0.448023%,
0.223513%**. The final kinetic-energy errors are **0.002440%, 0.001127%,
0.000449%**, and support-impulse residual is below **6.8e-20 kg m/s**.
These are numerical tests with damping disabled, not restitution calibration.
See [elastic_contact_verification.json](results/m7a/elastic_contact_verification.json).

Additional tests cover sliding/Coulomb limits, contact-memory retention/reset,
spin torque, nonadhesive damping, post-step penetration, minimum-mass stability,
floor/outlet conservation, mass rather than count fractions, deterministic
replay, actual obstacle-anchored contact paths and Taichi CPU/CUDA parity.
The [prepilot verification](results/m7a/prepilot_verification.json) records the
strict checks that passed before any campaign attempt and is hash-bound to the
design freeze. Mock dispatcher tests verify charging, no failed retries and the
three-worker concurrency limit without starting a solver.

## Finite arches and diagnostic limits

A near-outlet graph includes mobile-mobile and mobile-floor contacts plus an
explicit fixed-grain node attached to its floor support. A finite arch requires
a common support-spanning contact path, retained mobile grains, no new crossings
and near-outlet maximum speed <=0.003 m/s for 0.4s, after the gate buffer.
The contact-path intersection is checked at every integration step; sample
endpoints use a passive current-state graph. It is a conservative finite-window
observation, not proof of indefinite clogging or the source five-second rule.
It is stored under a separate M7A protocol and never rewrites M3 labels.

Energy diagnostics include mobile translation/spin/gravity, normal and history
spring energy, damping/contact work and exported energy. Gate removal and
history-spring sampling are approximate; no exact hopper energy closure is
claimed. Damping/friction/exported mass can reduce observed mechanical energy
legitimately. The analytic refinement test isolates discretization effects.
