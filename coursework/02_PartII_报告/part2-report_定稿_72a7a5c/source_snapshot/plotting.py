"""Plot speed-colored trajectories from a completed simulation."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection


def plot_time_space_diagram(
    sim,
    config,
    output: Path | None = None,
    show: bool = True,
    vehicle_stride: int = 1,
    line_width: float = 1.2,
):
    """Create, optionally save, and return a time-space diagram.

    vehicle_stride: draw every Nth vehicle. The default (1) plots the whole
    fleet, which is the macroscopic view used for throughput comparison.
    A larger stride produces the readable view where individual trajectories
    and stop-and-go waves stay visible instead of merging into a solid band.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    cmap = plt.get_cmap("jet_r")
    norm = plt.Normalize(vmin=0.0, vmax=config.speed_limit)
    any_segments = False

    stride = max(1, int(vehicle_stride))
    for vehicle in sim.vehicles[::stride]:
        if len(vehicle.history) < 2:
            continue
        times = np.array([record["t"] for record in vehicle.history])
        positions = np.array([record["position"] for record in vehicle.history])
        speeds = np.array([record["speed"] for record in vehicle.history])
        points = np.column_stack((times, positions)).reshape(-1, 1, 2)
        segments = np.concatenate((points[:-1], points[1:]), axis=1)
        collection = LineCollection(
            segments, cmap=cmap, norm=norm, linewidths=line_width
        )
        collection.set_array(0.5 * (speeds[:-1] + speeds[1:]))
        ax.add_collection(collection)
        any_segments = True

    if any_segments:
        colorbar = fig.colorbar(
            plt.cm.ScalarMappable(cmap=cmap, norm=norm),
            ax=ax,
        )
        colorbar.set_label("Speed (m/s)")

    wave_speed = config.reference_wave_speed_kmh / 3.6
    start_time = config.bottleneck_t_start
    start_position = config.bottleneck_x_start
    if wave_speed < 0.0:
        end_time = min(
            config.time_max,
            start_time + start_position / abs(wave_speed),
        )
        wave_times = np.array([start_time, end_time])
        wave_positions = start_position + wave_speed * (wave_times - start_time)
        ax.plot(
            wave_times,
            wave_positions,
            color="darkred",
            linestyle="--",
            linewidth=1.8,
            label=f"Reference wave ({config.reference_wave_speed_kmh:g} km/h)",
        )
        ax.legend(frameon=False)

    ax.set_xlim(0.0, config.time_max)
    ax.set_ylim(0.0, config.road_length)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Position (m)")
    ax.set_title(f"Time-Space Diagram — Experiment {config.experiment}")
    ax.grid(linestyle="--", alpha=0.3)
    fig.tight_layout()

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=160, bbox_inches="tight")
        print(f"Time-space diagram saved to: {output}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig, ax
