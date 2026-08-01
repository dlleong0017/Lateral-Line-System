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
FILTER_MODE = False           # True = filtered, False = unfiltered

PORT = "COM4"
BAUD = 115200
CHANNELS = 8

PLOT_WINDOW_SECONDS = 10
RECORDING_SECONDS = 5
DATA_DIRECTORY = "Data"

FILTER_CUTOFF_HZ = 5.0       # Remove frequencies above this value


# Shared live-plot variables
ser = None
fig = None
ax = None
lines = []

times = deque()
pressures = [deque() for _ in range(CHANNELS)]
first_timestamp = None


def read_sample():
    """Read and parse one ESP32 sample."""

    text = ser.readline().decode("ascii", errors="ignore").strip()
    parts = text.split(",")

    # Expected:
    # timestamp,p0,p1,p2,p3,p4,p5,p6,p7
    if len(parts) != CHANNELS + 1:
        return None

    try:
        timestamp = int(parts[0])
        values = [float(value) for value in parts[1:]]
    except ValueError:
        return None

    return timestamp, values


def fourier_filter(recorded_times, recorded_pressures):
    """Remove frequencies above the configured cutoff frequency."""

    if len(recorded_times) < 2:
        return recorded_pressures

    time_differences = np.diff(recorded_times)
    valid_differences = time_differences[time_differences > 0]

    if len(valid_differences) == 0:
        return recorded_pressures

    sample_period = np.median(valid_differences)
    filtered_pressures = []

    for pressure_data in recorded_pressures:
        pressure_array = np.asarray(pressure_data)

        frequency_data = np.fft.rfft(pressure_array)

        frequencies = np.fft.rfftfreq(
            len(pressure_array),
            d=sample_period,
        )

        frequency_data[frequencies > FILTER_CUTOFF_HZ] = 0

        filtered_signal = np.fft.irfft(
            frequency_data,
            n=len(pressure_array),
        )

        filtered_pressures.append(filtered_signal)

    return filtered_pressures


def update_live_plot(_):
    """Read available samples and update the live graph."""

    global first_timestamp

    while ser.in_waiting:
        sample = read_sample()

        if sample is None:
            continue

        timestamp, values = sample

        if first_timestamp is None:
            first_timestamp = timestamp

        time_s = (timestamp - first_timestamp) / 1000.0

        times.append(time_s)

        for channel, value in zip(pressures, values):
            channel.append(value)

        print(timestamp, *values)

        # Keep only the configured live window.
        while times and time_s - times[0] > PLOT_WINDOW_SECONDS:
            times.popleft()

            for channel in pressures:
                channel.popleft()

    if times:
        plot_times = list(times)
        plot_pressures = [list(channel) for channel in pressures]

        if FILTER_MODE:
            plot_pressures = fourier_filter(
                plot_times,
                plot_pressures,
            )

        for line, channel in zip(lines, plot_pressures):
            line.set_data(plot_times, channel)

        ax.set_xlim(
            max(0, plot_times[-1] - PLOT_WINDOW_SECONDS),
            max(PLOT_WINDOW_SECONDS, plot_times[-1]),
        )

        ax.relim()
        ax.autoscale_view(scalex=False)

    return lines


def run_live_mode():
    """Continuously display live sensor data."""

    global fig, ax, lines

    fig, ax = plt.subplots(figsize=(11, 5))

    lines = [
        ax.plot([], [], label=f"ch{i}")[0]
        for i in range(CHANNELS)
    ]

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Pressure (kPa)")

    if FILTER_MODE:
        ax.set_title(
            f"Live Filtered Pressure Data — "
            f"{FILTER_CUTOFF_HZ} Hz Cutoff"
        )
    else:
        ax.set_title("Live Pressure Sensor Data")

    ax.grid(alpha=0.2)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=8,
        frameon=False,
        handlelength=0.8,
        handletextpad=0.4,
        columnspacing=0.9,
    )

    animation = FuncAnimation(
        fig,
        update_live_plot,
        interval=50,
        cache_frame_data=False,
    )

    if FILTER_MODE:
        print("Mode: live filtered")
    else:
        print("Mode: live unfiltered")

    print("Close the graph to stop.")

    fig.tight_layout()
    plt.show()


def run_export_mode():
    """Record data and save it as a CSV and graph."""

    recorded_times = []
    recorded_pressures = [[] for _ in range(CHANNELS)]

    first_sample_timestamp = None
    start_time = time.time()

    if FILTER_MODE:
        print("Mode: export filtered")
    else:
        print("Mode: export unfiltered")

    print(f"Recording for {RECORDING_SECONDS} seconds...")

    while time.time() - start_time < RECORDING_SECONDS:
        sample = read_sample()

        if sample is None:
            continue

        timestamp, values = sample

        if first_sample_timestamp is None:
            first_sample_timestamp = timestamp

        time_s = (timestamp - first_sample_timestamp) / 1000.0

        recorded_times.append(time_s)

        for channel, value in zip(recorded_pressures, values):
            channel.append(value)

        print(timestamp, *values)

    if FILTER_MODE:
        recorded_pressures = fourier_filter(
            recorded_times,
            recorded_pressures,
        )

    save_data(recorded_times, recorded_pressures)


def save_data(recorded_times, recorded_pressures):
    """Save recorded sensor data as a CSV and PNG graph."""

    if not recorded_times:
        print("No valid sensor data was recorded.")
        return

    os.makedirs(DATA_DIRECTORY, exist_ok=True)

    run_name = datetime.now().strftime("pressure_%Y%m%d_%H%M%S")

    if FILTER_MODE:
        run_name += "_filtered"

    base_path = os.path.join(DATA_DIRECTORY, run_name)

    # Save the selected data type to CSV.
    with open(base_path + ".csv", "w", newline="") as csv_file:
        writer = csv.writer(csv_file)

        writer.writerow(
            ["time_s"] +
            [f"ch{i}_kPa" for i in range(CHANNELS)]
        )

        for sample in zip(recorded_times, *recorded_pressures):
            writer.writerow(sample)

    # Save the selected data type as a graph.
    fig, ax = plt.subplots(figsize=(10, 5))

    for channel, pressure_data in enumerate(recorded_pressures):
        ax.plot(
            recorded_times,
            pressure_data,
            linewidth=1.5,
            label=f"ch{channel}",
        )

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Pressure (kPa)")

    if FILTER_MODE:
        ax.set_title(
            f"Filtered Pressure Data — "
            f"{FILTER_CUTOFF_HZ} Hz Cutoff"
        )
    else:
        ax.set_title(
            f"Pressure Data — "
            f"{RECORDING_SECONDS} Second Recording"
        )

    ax.grid(alpha=0.2)
    ax.margins(x=0.02)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=8,
        frameon=False,
        handlelength=0.8,
        handletextpad=0.4,
        columnspacing=0.9,
    )

    fig.tight_layout()
    fig.savefig(
        base_path + ".png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)

    print(f"CSV saved:   {base_path}.csv")
    print(f"Graph saved: {base_path}.png")


def main():
    global ser

    ser = serial.Serial(PORT, BAUD, timeout=0.1)

    # Opening the serial port can reset the ESP32.
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