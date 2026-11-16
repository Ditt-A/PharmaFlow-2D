from dataclasses import replace
import numpy as np
import pytest
from pharmaflow.config import HopperConfig
from pharmaflow.contact import contact_response
from pharmaflow.dem import DEMSystem, ParticleState, initial_state
from pharmaflow.geometry import check_wall_crossings
from pharmaflow.neighbors import cell_pairs
from pharmaflow.run import simulate, save_run, load_run


def config(**kw):
    return replace(HopperConfig(), gravity_m_s2=0, gate_open_time_s=0, **kw)


def isolated(c, x, v=None, omega=None, walls=()):
    state = ParticleState.create(x, c.particle_radius_m, c.particle_mass_kg, v, omega)
    return DEMSystem(c, state, walls=walls, track_outlet=False)


def kinetic(s):
    return np.sum(0.5 * s.mass * np.sum(s.velocity**2, axis=1) + 0.5 * s.inertia * s.omega**2)


def angular_momentum(s):
    return np.sum(s.mass * (s.position[:, 0] * s.velocity[:, 1] - s.position[:, 1] * s.velocity[:, 0]) + s.inertia * s.omega)


def test_free_fall_and_first_order_convergence():
    errors = []
    for dt in (1e-5, 5e-6):
        c = HopperConfig(n_particles=1, dt_s=dt)
        system = isolated(c, [[0, 1]])
        system.advance(round(0.02 / dt))
        np.testing.assert_allclose(system.state.velocity[0], [0, -c.gravity_m_s2 * 0.02], atol=1e-12)
        exact = 1 - 0.5 * c.gravity_m_s2 * 0.02**2
        errors.append(abs(system.state.position[0, 1] - exact))
    assert errors[1] < 0.51 * errors[0]


def test_equal_opposite_contact_force():
    c = config(normal_damping_kg_s=0, tangential_damping_kg_s=0)
    system = isolated(c, [[-0.00195, 0], [0.00195, 0]])
    force, torque = system.forces()
    np.testing.assert_allclose(force[:, 0], [-0.1, 0.1], atol=1e-14)
    np.testing.assert_allclose(force.sum(axis=0), 0, atol=1e-14)
    np.testing.assert_array_equal(torque, 0)


def test_approach_only_normal_damping_no_adhesion():
    fn, ft, _ = contact_response(np.full(3, 0.0001), np.array([-1, 0, 1.]), np.zeros(3), np.zeros(3),
                                 np.full(3, 0.4), 1e-5, 1000, 250, 0.15, 0.03)
    np.testing.assert_allclose(fn, [0.25, 0.1, 0.1])
    np.testing.assert_array_equal(ft, 0)


def test_coulomb_cap_and_persistent_spring():
    c = config(normal_damping_kg_s=0, tangential_damping_kg_s=0)
    system = isolated(c, [[-0.00195, 0], [0.00195, 0]], [[0, 100], [0, 0]])
    force, torque = system.forces()
    assert abs(force[0, 1]) == pytest.approx(c.friction * abs(force[0, 0]))
    assert force[0, 1] < 0 and np.all(torque < 0)
    np.testing.assert_allclose(torque, -0.00195 * abs(force[0, 1]))
    system.state.velocity[:] = 0
    remembered_force, _ = system.forces()
    assert abs(remembered_force[0, 1]) > 0
    system.state.position[1, 0] += 0.01
    system.forces()
    assert system.history == {}


def test_sliding_friction_dissipates_energy_and_rotates():
    c = config(normal_damping_kg_s=0.1, tangential_damping_kg_s=0.02)
    system = isolated(c, [[-0.00195, 0], [0.00195, 0]], [[0.02, 0.1], [-0.02, 0]])
    initial_energy = kinetic(system.state) + 0.5 * c.normal_stiffness_n_m * 0.0001**2
    system.advance(300)
    assert np.any(abs(system.state.omega) > 0)
    assert kinetic(system.state) < initial_energy


def test_elastic_pair_linear_angular_momentum_and_energy():
    c = config(normal_damping_kg_s=0, tangential_damping_kg_s=0, friction=0)
    system = isolated(c, [[-0.0021, 0], [0.0021, 0]], [[0.1, 0], [-0.1, 0]])
    before = kinetic(system.state)
    momentum = np.sum(system.state.mass[:, None] * system.state.velocity, axis=0)
    system.advance(500)
    np.testing.assert_allclose(np.sum(system.state.mass[:, None] * system.state.velocity, axis=0), momentum, atol=1e-15)
    assert system.state.velocity[0, 0] < 0
    assert kinetic(system.state) == pytest.approx(before, rel=0.003)


def test_tangential_pair_conserves_total_angular_momentum():
    c = config(normal_damping_kg_s=0, tangential_damping_kg_s=0)
    system = isolated(c, [[-0.00195, 0], [0.00195, 0]], [[0.03, 0.08], [-0.03, -0.02]])
    initial = angular_momentum(system.state)
    system.advance(200)
    assert angular_momentum(system.state) == pytest.approx(initial, abs=2e-14)


def test_wall_contact_friction_rotation_and_rebound():
    c = config(normal_damping_kg_s=0)
    system = isolated(c, [[0, 0.00195]], [[0.1, -0.02]], walls=[[[-0.1, 0], [0.1, 0]]])
    force, torque = system.forces()
    assert force[0, 1] > 0 and force[0, 0] < 0 and torque[0] < 0
    system.advance(500)
    assert system.state.position[0, 1] > c.particle_radius_m
    assert system.max_overlap_ratio < c.max_overlap_ratio


def test_settled_particle_supported_by_wall():
    c = HopperConfig(n_particles=1)
    system = isolated(c, [[0, 0.002]], walls=[[[-0.1, 0], [0.1, 0]]])
    system.advance(10000)
    expected_overlap = c.particle_mass_kg * c.gravity_m_s2 / c.normal_stiffness_n_m
    assert c.particle_radius_m - system.state.position[0, 1] == pytest.approx(expected_overlap, rel=0.03)
    assert abs(system.state.velocity[0, 1]) < 1e-4


def test_wall_endpoint_and_outlet_gap():
    c = config()
    system = isolated(c, [[0.00135, 0.00135]], walls=[[[0, 0], [-0.1, 0]]])
    force, _ = system.forces()
    assert force[0, 0] > 0 and force[0, 1] > 0
    open_hopper = DEMSystem(c, ParticleState.create([[0, 0.001]], c.particle_radius_m, c.particle_mass_kg))
    np.testing.assert_array_equal(open_hopper.forces()[0], 0)


def test_hash_pairs_match_brute_force():
    rng = np.random.default_rng(13)
    x, r = rng.uniform(-0.01, 0.01, (50, 2)), rng.uniform(0.001, 0.002, 50)
    active = rng.random(50) > 0.2
    found = set(map(tuple, cell_pairs(x, r, active, 0.0003)))
    brute = {(i, j) for i in range(50) for j in range(i + 1, 50)
             if active[i] and active[j] and np.linalg.norm(x[i] - x[j]) < r[i] + r[j] + 0.0003}
    assert found == brute


@pytest.mark.parametrize("kw", [{"dt_s": 0.001}, {"dt_s": float("nan")}, {"friction": -1},
                                    {"normal_damping_kg_s": -1}, {"seed": -1}, {"n_particles": 1.5}])
def test_invalid_config_rejected(kw):
    with pytest.raises(ValueError):
        replace(HopperConfig(), **kw).validate()


def test_fail_fast_overlap_nan_and_displacement():
    c = config()
    system = isolated(c, [[0, 0], [0.001, 0]])
    with pytest.raises(RuntimeError, match="overlap"):
        system.step()
    system = isolated(c, [[0, 0]])
    system.state.velocity[0, 0] = np.nan
    with pytest.raises(RuntimeError, match="nonfinite"):
        system.step()
    system = isolated(c, [[0, 0]], [[1000, 0]])
    with pytest.raises(RuntimeError, match="radius"):
        system.step()


def test_wall_tunneling_detector():
    with pytest.raises(RuntimeError, match="tunneling"):
        check_wall_crossings(np.array([[0., 0.001]]), np.array([[0., -0.001]]), np.array([[[-1., 0], [1., 0]]]))


def test_seeded_fill_and_short_trajectory_are_deterministic(tmp_path):
    c = HopperConfig(n_particles=50)
    np.testing.assert_array_equal(initial_state(c).position, initial_state(c).position)
    assert not np.array_equal(initial_state(c).position, initial_state(replace(c, seed=43)).position)
    a, ma = simulate(c, 0.002, 100)
    b, mb = simulate(c, 0.002, 100)
    for key in a:
        np.testing.assert_array_equal(a[key], b[key])
    assert ma["trajectory_sha256"] == mb["trajectory_sha256"]
    assert ma["accuracy_checks"]["particle_accounting"]
    path = tmp_path / "trajectory.npz"
    save_run(path, a, ma)
    restored, metadata = load_run(path)
    np.testing.assert_array_equal(restored["position_m"], a["position_m"])
    assert metadata["config"]["seed"] == c.seed


def test_discharge_crossing_counted_once_and_particles_accounted():
    c = HopperConfig(n_particles=1, gate_open_time_s=0)
    state = ParticleState.create([[0, 0.003]], c.particle_radius_m, c.particle_mass_kg)
    system = DEMSystem(c, state)
    system.advance(12000)
    assert np.isfinite(system.crossing_time).sum() == 1
    assert not system.state.active[0]
    assert system.crossing_time[0] == pytest.approx(np.sqrt(0.006 / c.gravity_m_s2), abs=2 * c.dt_s)


def test_headless_animation_export(tmp_path):
    from pharmaflow.visualize import render_gif
    from PIL import Image
    arrays, metadata = simulate(HopperConfig(n_particles=2), 0.001, 50)
    path = tmp_path / "hopper.gif"
    render_gif(arrays, metadata, path, max_frames=3)
    with Image.open(path) as image:
        assert image.n_frames >= 2


@pytest.mark.parametrize("backend", ["taichi-cpu", "cuda"])
def test_optional_taichi_contact_and_trajectory_parity(backend):
    import os
    if os.environ.get("PHARMAFLOW_TEST_TAICHI") != "1":
        pytest.skip("set PHARMAFLOW_TEST_TAICHI=1 for strict optional CPU/CUDA tests")
    c = config()
    accelerated = isolated(c, [[-0.00195, 0], [0.00195, 0]], [[0.03, 0.08], [-0.03, -0.02]])
    reference = isolated(c, [[-0.00195, 0], [0.00195, 0]], [[0.03, 0.08], [-0.03, -0.02]])
    accelerated = DEMSystem(c, accelerated.state, walls=(), backend=backend, track_outlet=False)
    accelerated.advance(100)
    reference.advance(100)
    np.testing.assert_allclose(accelerated.state.position, reference.state.position, atol=1e-13)
    np.testing.assert_allclose(accelerated.state.omega, reference.state.omega, atol=1e-9)


def test_cpu_fallback_when_optional_backend_cannot_import(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "pharmaflow.taichi_backend", None)
    with pytest.warns(RuntimeWarning, match="using NumPy CPU"):
        system = DEMSystem(HopperConfig(n_particles=2), backend="auto")
    system.advance(20)
    assert system.backend == "numpy-cpu"
    with pytest.raises(RuntimeError, match="unavailable"):
        DEMSystem(HopperConfig(n_particles=2), backend="cuda")


def test_interacting_frictional_trajectory_is_repeatable():
    c = config()
    outputs = []
    for _ in range(2):
        system = isolated(c, [[-0.00195, 0], [0.00195, 0]], [[0.03, 0.08], [-0.03, -0.02]])
        system.advance(200)
        outputs.append((system.state.position.copy(), system.state.velocity.copy(), system.state.omega.copy()))
    for first, second in zip(*outputs):
        np.testing.assert_array_equal(first, second)


def test_zero_flux_without_retained_contact_arch_is_not_clogging():
    from pharmaflow.diagnostics import arch_observation, spanning_contact_chain
    c = HopperConfig(n_particles=2, gate_open_time_s=0)
    time = np.linspace(0, 0.4, 5)
    positions = np.tile(np.array([[-0.02, 0.01], [0.02, 0.01]]), (5, 1, 1))
    arrays = {"time_s": time, "position_m": positions, "velocity_m_s": np.zeros_like(positions),
              "active": np.ones((5, 2), dtype=bool), "radius_m": np.full(2, c.particle_radius_m),
              "discharged_count": np.zeros(5, dtype=int)}
    from dataclasses import asdict
    observation = arch_observation(arrays, {"config": asdict(c)})
    assert observation["no_outlet_crossings_in_window"]
    assert not observation["observed_stationary_spanning_arch"]
    assert not spanning_contact_chain(positions[0], arrays["radius_m"], np.ones(2, dtype=bool), c)
