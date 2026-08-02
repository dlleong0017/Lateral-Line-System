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

MODE = "export"              # "live" or "export"
FILTER_MODE = True        # True = filtered graph

PORT = "COM4"
BAUD = 115200

PLOT_WINDOW_SECONDS = 10
RECORDING_SECONDS = 5
DATA_DIRECTORY = "Data"

FILTER_CUTOFF_HZ = 5.0


# Shared live-plot variables
ser = None
fig = None
ax = None
line = None

times = deque()
velocities = deque()
first_timestamp = None


def read_sample():
    """Read one timestamp and fluid-velocity sample."""

    text = ser.readline().decode(
        "ascii",
        errors="ignore",
    ).strip()

    parts = text.split(",")

    # Expected:
    # timestamp,velocity
    if len(parts) != 2:
        return None

    try:
        timestamp = int(parts[0])
        velocity = float(parts[1])
    except ValueError:
        # This also ignores the ESP32 column header.
        return None

    return timestamp, velocity


def fourier_filter(recorded_times, velocity_data):
    """Remove frequencies above the configured cutoff."""

    if len(recorded_times) < 2:
        return velocity_data

    time_differences = np.diff(recorded_times)
    valid_differences = time_differences[time_differences > 0]

    if len(valid_differences) == 0:
        return velocity_data

    sample_period = np.median(valid_differences)
    velocity_array = np.asarray(velocity_data)

    frequency_data = np.fft.rfft(velocity_array)

    frequencies = np.fft.rfftfreq(
        len(velocity_array),
        d=sample_period,
    )

    frequency_data[frequencies > FILTER_CUTOFF_HZ] = 0

    return np.fft.irfft(
        frequency_data,
        n=len(velocity_array),
    )


def update_live_plot(_):
    """Read available samples and update the live graph."""

    global first_timestamp

    while ser.in_waiting:
        sample = read_sample()

        if sample is None:
            continue

        timestamp, velocity = sample

        if first_timestamp is None:
            first_timestamp = timestamp

        time_s = (timestamp - first_timestamp) / 1000.0

        times.append(time_s)
        velocities.append(velocity)

        print(f"{timestamp},{velocity:.4f}")

        # Keep only the configured plotting window.
        while times and time_s - times[0] > PLOT_WINDOW_SECONDS:
            times.popleft()
            velocities.popleft()

    if times:
        plot_times = list(times)
        plot_velocities = list(velocities)

        if FILTER_MODE:
            plot_velocities = fourier_filter(
                plot_times,
                plot_velocities,
            )

        line.set_data(plot_times, plot_velocities)

        ax.set_xlim(
            max(
                -0.02 * PLOT_WINDOW_SECONDS,
                plot_times[-1] - PLOT_WINDOW_SECONDS,
            ),
            max(PLOT_WINDOW_SECONDS, plot_times[-1]),
        )

        ax.relim()
        ax.autoscale_view(scalex=False)

    return [line]


def run_live_mode():
    """Continuously display fluid velocity."""

    global fig, ax, line

    fig, ax = plt.subplots(figsize=(10, 5))

    line, = ax.plot(
        [],
        [],
        linewidth=1.5,
        color="tab:blue",
    )

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Fluid Velocity (m/s)")
    ax.grid(alpha=0.2)

    if FILTER_MODE:
        ax.set_title(
            f"Live Filtered Fluid Velocity — "
            f"{FILTER_CUTOFF_HZ} Hz Cutoff"
        )
    else:
        ax.set_title("Live Fluid Velocity")

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
    """Record and export fluid-velocity data."""

    recorded_times = []
    recorded_velocities = []

    first_sample_timestamp = None
    start_time = time.time()

    print(
        "Mode: export filtered"
        if FILTER_MODE
        else "Mode: export unfiltered"
    )
    print(f"Recording for {RECORDING_SECONDS} seconds...")

    while time.time() - start_time < RECORDING_SECONDS:
        sample = read_sample()

        if sample is None:
            continue

        timestamp, velocity = sample

        if first_sample_timestamp is None:
            first_sample_timestamp = timestamp

        time_s = (
            timestamp - first_sample_timestamp
        ) / 1000.0

        recorded_times.append(time_s)
        recorded_velocities.append(velocity)

        print(f"{timestamp},{velocity:.4f}")

    save_data(recorded_times, recorded_velocities)


def save_data(recorded_times, recorded_velocities):
    """Save raw velocity data and its selected graph."""

    if not recorded_times:
        print("No valid sensor data was recorded.")
        return

    os.makedirs(DATA_DIRECTORY, exist_ok=True)

    run_name = datetime.now().strftime(
        "velocity_%Y%m%d_%H%M%S"
    )
    base_path = os.path.join(DATA_DIRECTORY, run_name)

    # Always save raw velocity data.
    with open(base_path + ".csv", "w", newline="") as csv_file:
        writer = csv.writer(csv_file)

        writer.writerow([
            "time_s",
            "velocity_m_s",
        ])

        writer.writerows(
            zip(recorded_times, recorded_velocities)
        )

    # Filter only the graph data when enabled.
    plot_velocities = recorded_velocities
    graph_path = base_path + ".png"

    if FILTER_MODE:
        plot_velocities = fourier_filter(
            recorded_times,
            recorded_velocities,
        )
        graph_path = base_path + "_filtered.png"

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(
        recorded_times,
        plot_velocities,
        linewidth=1.5,
        color="tab:blue",
    )

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Fluid Velocity (m/s)")
    ax.grid(alpha=0.2)
    ax.margins(x=0.02)

    if FILTER_MODE:
        ax.set_title(
            f"Filtered Fluid Velocity — "
            f"{FILTER_CUTOFF_HZ} Hz Cutoff"
        )
    else:
        ax.set_title(
            f"Fluid Velocity — "
            f"{RECORDING_SECONDS} Second Recording"
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

    ser = serial.Serial(PORT, BAUD, timeout=0.1)

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
            print('Use MODE = "live" or MODE = "export".')
    finally:
        ser.close()


if __name__ == "__main__":
    main()