"""Headless animation of actual DEM trajectories; Pillow requires no ffmpeg."""
from pathlib import Path
import numpy as np
from .config import HopperConfig
from .geometry import hopper_walls


def render_gif(arrays, metadata, path, fps=25, max_frames=150):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter
    from matplotlib.collections import EllipseCollection, LineCollection
    if fps <= 0 or max_frames < 2:
        raise ValueError("fps must be positive and max_frames >= 2")
    config = HopperConfig(**metadata["config"])
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax, chart) = plt.subplots(1, 2, figsize=(9, 5), gridspec_kw={"width_ratios": [1, 1]})
    fig.suptitle("PharmaFlow-2D | physical DEM trajectory (uncalibrated)")
    diameter = 2 * arrays["radius_m"]
    disks = EllipseCollection(diameter, diameter, np.zeros_like(diameter), units="xy",
                              offsets=arrays["position_m"][0], transOffset=ax.transData,
                              cmap="viridis", clim=(0, 1.5), edgecolors="black", linewidths=0.25)
    ax.add_collection(disks)
    walls = LineCollection(hopper_walls(config, 0), colors="black", linewidths=2)
    ax.add_collection(walls)
    spin, = ax.plot([], [], color="white", lw=0.6)
    ax.annotate("outlet", (0, -0.003), (0.035, -0.025), arrowprops={"arrowstyle": "->"}, fontsize=8)
    ax.set(xlim=(-config.width_m * 0.6, config.width_m * 0.6), ylim=(config.removal_y_m, config.height_m),
           xlabel="x [m]", ylabel="y [m]", aspect="equal")
    fig.colorbar(disks, ax=ax, label="speed [m/s]", fraction=0.04)
    times, counts = arrays["time_s"], arrays["discharged_count"]
    chart.plot(times, counts, color="#255aab")
    marker, = chart.plot([0], [0], "o", color="#d95235")
    chart.set(xlabel="simulation time [s]", ylabel="cumulative outlet crossings [particles]",
              xlim=(0, max(times[-1], 1e-6)), ylim=(0, max(len(diameter), 1)))
    chart.grid(alpha=0.25)
    stamp = chart.text(0.03, 0.9, "", transform=chart.transAxes)
    indices = np.unique(np.linspace(0, len(times) - 1, min(max_frames, len(times)), dtype=int))
    def update(frame):
        positions = arrays["position_m"][frame].copy()
        active = arrays["active"][frame]
        positions[~active] = np.nan
        disks.set_offsets(positions)
        disks.set_array(np.linalg.norm(arrays["velocity_m_s"][frame], axis=1))
        angle = arrays["angle_rad"][frame]
        endpoints = positions + arrays["radius_m"][:, None] * np.column_stack((np.cos(angle), np.sin(angle)))
        lines = np.stack((positions, endpoints, np.full_like(positions, np.nan)), axis=1)
        spin.set_data(lines[:, :, 0].ravel(), lines[:, :, 1].ravel())
        walls.set_segments(hopper_walls(config, float(times[frame])))
        marker.set_data([times[frame]], [counts[frame]])
        stamp.set_text(f"t = {times[frame]:.3f} s\ndischarged = {counts[frame]} / {len(diameter)}")
        return disks, walls, marker, stamp, spin
    animation = FuncAnimation(fig, update, frames=indices, interval=1000 / fps, blit=False)
    fig.tight_layout()
    try:
        animation.save(path, writer=PillowWriter(fps=fps), dpi=100)
    finally:
        plt.close(fig)
