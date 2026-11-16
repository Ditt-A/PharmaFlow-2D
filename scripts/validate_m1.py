"""Check saved wide/narrow DEM runs and write a compact M1 evidence report."""
import argparse
import json
from pathlib import Path
import numpy as np
from pharmaflow.diagnostics import arch_observation
from pharmaflow.run import load_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wide", type=Path, default=Path("outputs/rollouts/m1_hopper.npz"))
    parser.add_argument("--narrow", type=Path, default=Path("outputs/rollouts/m1_narrow.npz"))
    parser.add_argument("--output", type=Path, default=Path("outputs/metrics/m1_validation.json"))
    args = parser.parse_args()
    report = {}
    for name, path in (("wide", args.wide), ("narrow", args.narrow)):
        arrays, metadata = load_run(path)
        checks = metadata["accuracy_checks"]
        assert checks["finite"] and checks["particle_accounting"] and checks["removed_have_crossing"]
        assert checks["max_overlap_over_radius"] < checks["overlap_limit"]
        assert not checks["wall_tunneling"]
        assert np.all(np.diff(arrays["discharged_count"]) >= 0)
        assert len(np.unique(arrays["particle_id"])) == checks["particle_count"]
        report[name] = {"trajectory": str(path), "backend": metadata["backend"], "accuracy_checks": checks,
                        "arch_observation": arch_observation(arrays, metadata)}
    assert report["wide"]["accuracy_checks"]["discharged_final"] > 0, "wide hopper did not discharge"
    assert report["narrow"]["arch_observation"]["observed_stationary_spanning_arch"], "narrow run has no verified persistent arch"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
