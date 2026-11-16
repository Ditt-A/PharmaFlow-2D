"""Run real 2D DEM, export trajectories/provenance and optionally a headless GIF."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
from pharmaflow.config import HopperConfig
from pharmaflow.run import simulate, save_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="JSON object of HopperConfig SI parameters")
    parser.add_argument("--backend", choices=["cpu", "auto", "cuda", "taichi-cpu"], default="cpu")
    parser.add_argument("--duration", type=float, default=0.5)
    parser.add_argument("--particles", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--outlet", type=float)
    parser.add_argument("--dt", type=float)
    parser.add_argument("--sample-every", type=int, default=250)
    parser.add_argument("--output", type=Path, default=Path("outputs/rollouts/m1_hopper.npz"))
    parser.add_argument("--gif", type=Path)
    args = parser.parse_args()
    config = HopperConfig(**json.loads(args.config.read_text())) if args.config else HopperConfig()
    overrides = {name: value for name, value in (("n_particles", args.particles), ("seed", args.seed),
                 ("outlet_width_m", args.outlet), ("dt_s", args.dt)) if value is not None}
    config = replace(config, **overrides)
    arrays, metadata = simulate(config, args.duration, args.sample_every, args.backend)
    save_run(args.output, arrays, metadata)
    print(json.dumps(metadata, indent=2), flush=True)
    print("Saved:", args.output, flush=True)
    if args.gif:
        from pharmaflow.visualize import render_gif
        render_gif(arrays, metadata, args.gif)
        print("Saved:", args.gif, flush=True)


if __name__ == "__main__":
    main()
