#!/usr/bin/env python3

import csv
import os
import time
from collections import deque
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import serial
from matplotlib.animation import FuncAnimation


# =========================
# Configuration
# =========================

MODE = "live"          # "live" or "export"
FILTER_MODE = True       # True = filtered graphs

PORT = "COM4"
BAUD = 115200

# Live mode starts the x-axis at 0 s and grows it as the run continues.
# This is only the initial width, so the plot is not squashed at t = 0.
LIVE_INITIAL_X_SECONDS = 10

# Display-only decimation. The live axis keeps every sample, but drawing
# hundreds of thousands of points every 50 ms stalls the animation, so
# the trace is strided down to at most this many points for rendering.
LIVE_MAX_DRAW_POINTS = 20000

RECORDING_SECONDS = 240
DATA_DIRECTORY = "Data/8-5-26 Testing"

FILTER_CUTOFF_HZ = 5

# Anchor the velocity axis at 0 m/s.
# NOTE: set this False for runs with reverse flow, otherwise
# negative velocities are drawn below the visible axis.
Y_AXIS_START_AT_ZERO = False

# Headroom above the largest plotted velocity.
Y_AXIS_HEADROOM = 1.05

# Fallback axis top when no positive data is present.
Y_AXIS_MIN_TOP = 0.05


# Live-plot variables
ser = None
fig = None

velocity_ax = None
velocity_line = None

times = deque()
velocities = deque()
pressures = deque()

first_timestamp = None


def read_sample():
    """Read timestamp, fluid velocity, and pressure."""

    text = ser.readline().decode(
        "ascii",
        errors="ignore",
    ).strip()

    parts = text.split(",")

    # Expected:
    # timestamp,velocity,pressure
    if len(parts) != 3:
        return None

    try:
        timestamp = int(parts[0])
        velocity = float(parts[1])
        pressure = float(parts[2])
    except ValueError:
        # Ignore column headers and malformed lines.
        return None

    return timestamp, velocity, pressure


def fourier_filter(recorded_times, signal_data):
    """Remove signal frequencies above the cutoff."""

    if len(recorded_times) < 2:
        return np.asarray(signal_data)

    time_differences = np.diff(recorded_times)
    valid_differences = time_differences[
        time_differences > 0
    ]

    if len(valid_differences) == 0:
        return np.asarray(signal_data)

    sample_period = np.median(valid_differences)
    signal_array = np.asarray(signal_data)

    frequency_data = np.fft.rfft(signal_array)

    frequencies = np.fft.rfftfreq(
        len(signal_array),
        d=sample_period,
    )

    frequency_data[
        frequencies > FILTER_CUTOFF_HZ
    ] = 0

    return np.fft.irfft(
        frequency_data,
        n=len(signal_array),
    )


def apply_velocity_ylim(axis, plotted_values):
    """Set the velocity axis limits, starting at 0 if configured."""

    values = np.asarray(plotted_values, dtype=float)

    if values.size == 0:
        return

    data_min = float(np.nanmin(values))
    data_max = float(np.nanmax(values))

    if Y_AXIS_START_AT_ZERO:
        bottom = 0.0
        top = max(
            data_max * Y_AXIS_HEADROOM,
            Y_AXIS_MIN_TOP,
        )
    else:
        span = data_max - data_min

        if span <= 0:
            span = max(abs(data_max), Y_AXIS_MIN_TOP)

        bottom = data_min - 0.05 * span
        top = data_max + 0.05 * span

    axis.set_ylim(bottom, top)


def update_live_plot(_):
    """Read available samples and update the velocity graph."""

    global first_timestamp

    while ser.in_waiting:
        sample = read_sample()

        if sample is None:
            continue

        timestamp, velocity, pressure = sample

        if first_timestamp is None:
            first_timestamp = timestamp

        time_s = (
            timestamp - first_timestamp
        ) / 1000.0

        times.append(time_s)
        velocities.append(velocity)
        pressures.append(pressure)

        print(
            f"{timestamp},"
            f"{velocity:.4f},"
            f"{pressure:.4f}"
        )

    if times:
        plot_times = list(times)
        plot_velocities = list(velocities)

        if FILTER_MODE:
            plot_velocities = fourier_filter(
                plot_times,
                plot_velocities,
            )

        # Decimate for drawing only; the stored data is untouched.
        if len(plot_times) > LIVE_MAX_DRAW_POINTS:
            stride = (
                len(plot_times) // LIVE_MAX_DRAW_POINTS
            ) + 1
            draw_times = plot_times[::stride]
            draw_velocities = plot_velocities[::stride]
        else:
            draw_times = plot_times
            draw_velocities = plot_velocities

        velocity_line.set_data(
            draw_times,
            draw_velocities,
        )

        # Always anchored at 0 s; the right edge grows with the run.
        x_max = max(
            LIVE_INITIAL_X_SECONDS,
            plot_times[-1] * 1.02,
        )

        velocity_ax.set_xlim(0, x_max)

        apply_velocity_ylim(
            velocity_ax,
            draw_velocities,
        )

    return (velocity_line,)


def run_live_mode():
    """Continuously display fluid velocity."""

    global fig
    global velocity_ax
    global velocity_line

    fig, velocity_ax = plt.subplots(
        figsize=(10, 5),
    )

    velocity_line, = velocity_ax.plot(
        [],
        [],
        linewidth=1.5,
        color="tab:blue",
    )

    velocity_ax.set_ylabel(
        "Fluid Velocity (m/s)"
    )
    velocity_ax.set_xlabel("Time (s)")

    velocity_ax.grid(alpha=0.2)

    velocity_ax.set_xlim(0, LIVE_INITIAL_X_SECONDS)

    if Y_AXIS_START_AT_ZERO:
        velocity_ax.set_ylim(0, Y_AXIS_MIN_TOP)

    if FILTER_MODE:
        fig.suptitle(
            "Live Fluid Velocity "
            f"— {FILTER_CUTOFF_HZ} Hz Cutoff"
        )
    else:
        fig.suptitle(
            "Live Fluid Velocity"
        )

    animation = FuncAnimation(
        fig,
        update_live_plot,
        interval=50,
        cache_frame_data=False,
    )

    print(
        "Mode: live filtered"
        if FILTER_MODE
        else "Mode: live unfiltered"
    )
    print("Close the graph to stop.")

    fig.tight_layout()
    plt.show()


def run_export_mode():
    """Record velocity and pressure data."""

    recorded_times = []
    recorded_velocities = []
    recorded_pressures = []

    first_sample_timestamp = None
    start_time = time.time()

    print(
        "Mode: export filtered"
        if FILTER_MODE
        else "Mode: export unfiltered"
    )
    print(
        f"Recording for "
        f"{RECORDING_SECONDS} seconds..."
    )

    while time.time() - start_time < RECORDING_SECONDS:
        sample = read_sample()

        if sample is None:
            continue

        timestamp, velocity, pressure = sample

        if first_sample_timestamp is None:
            first_sample_timestamp = timestamp

        time_s = (
            timestamp - first_sample_timestamp
        ) / 1000.0

        recorded_times.append(time_s)
        recorded_velocities.append(velocity)
        recorded_pressures.append(pressure)

        print(
            f"{timestamp},"
            f"{velocity:.4f},"
            f"{pressure:.4f}"
        )

    save_data(
        recorded_times,
        recorded_velocities,
        recorded_pressures,
    )


def save_data(
    recorded_times,
    recorded_velocities,
    recorded_pressures,
):
    """Save raw data and the velocity graph."""

    if not recorded_times:
        print("No valid sensor data was recorded.")
        return

    os.makedirs(
        DATA_DIRECTORY,
        exist_ok=True,
    )

    run_name = datetime.now().strftime(
        "sensor_%Y%m%d_%H%M%S"
    )
    base_path = os.path.join(
        DATA_DIRECTORY,
        run_name,
    )

    # Pressure is still recorded, just not graphed.
    with open(
        base_path + ".csv",
        "w",
        newline="",
    ) as csv_file:
        writer = csv.writer(csv_file)

        writer.writerow([
            "time_s",
            "velocity_m_s",
            "pressure_kpa",
        ])

        writer.writerows(zip(
            recorded_times,
            recorded_velocities,
            recorded_pressures,
        ))

    plot_velocities = recorded_velocities
    graph_path = base_path + ".png"

    if FILTER_MODE:
        plot_velocities = fourier_filter(
            recorded_times,
            recorded_velocities,
        )

        graph_path = (
            base_path + "_filtered.png"
        )

    if Y_AXIS_START_AT_ZERO and min(plot_velocities) < 0:
        print(
            "Warning: negative velocities present "
            f"(min {min(plot_velocities):.4f} m/s). "
            "They fall below the 0 m/s axis limit. "
            "Set Y_AXIS_START_AT_ZERO = False to see them."
        )

    fig, velocity_ax = plt.subplots(
        figsize=(10, 5),
    )

    velocity_ax.plot(
        recorded_times,
        plot_velocities,
        linewidth=1.5,
        color="tab:blue",
    )

    velocity_ax.set_ylabel(
        "Fluid Velocity (m/s)"
    )
    velocity_ax.set_xlabel("Time (s)")

    velocity_ax.grid(alpha=0.2)
    velocity_ax.margins(x=0.02)

    apply_velocity_ylim(
        velocity_ax,
        plot_velocities,
    )

    if FILTER_MODE:
        fig.suptitle(
            "Filtered Fluid Velocity "
            f"— {FILTER_CUTOFF_HZ} Hz Cutoff"
        )
    else:
        fig.suptitle(
            "Fluid Velocity "
            f"— {RECORDING_SECONDS} Second Recording"
        )

    fig.tight_layout()

    fig.savefig(
        graph_path,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(f"Raw CSV saved: {base_path}.csv")
    print(f"Graph saved:   {graph_path}")


def main():
    global ser

    ser = serial.Serial(
        PORT,
        BAUD,
        timeout=0.1,
    )

    # Opening the serial port resets many ESP32 boards.
    time.sleep(2)
    ser.reset_input_buffer()

    try:
        if MODE == "live":
            run_live_mode()
        elif MODE == "export":
            run_export_mode()
        else:
            print(f'Invalid MODE: "{MODE}"')
            print(
                'Use MODE = "live" or '
                'MODE = "export".'
            )
    finally:
        ser.close()


if __name__ == "__main__":
    main()