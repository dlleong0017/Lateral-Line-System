#!/usr/bin/env python3
"""Live-plot or record 8 channels of differential pressure from a serial sensor array.

Serial line format (one sample per line):
    timestamp_ms,p0,p1,p2,p3,p4,p5,p6,p7
"""

import csv
import os
import time
from collections import deque
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import serial
from matplotlib.animation import FuncAnimation


# Configuration
# =============================================================================

MODE = "export"                # "live" or "export"

FILTER_MODE = True             # low-pass the pressure traces
FILTER_METHOD = "turbulence"    # Options: "turbulence", fourier

TURBULENCE_WINDOW_SEC = 2.5     # Rolling window in seconds for turbulence intensity
FILTER_CUTOFF_HZ = 5.0          # discard content above this frequency

RECORDING_SECONDS = 60           # export mode only
DATA_DIRECTORY = "Data/9-4-2026 Testing"         # export mode only

PORT = "COM13"
BAUD = 115200
CHANNELS = 8

# =============================================================================


# -----------------------------------------------------------------------------
# Serial input
# -----------------------------------------------------------------------------

def read_sample(ser):
    """Return (timestamp_ms, [p0..p7]), or None for a bad line."""
    text = ser.readline().decode("ascii", errors="ignore").strip()
    parts = text.split(",")

    if len(parts) != CHANNELS + 1:
        return None

    try:
        timestamp = int(parts[0])
        values = [float(value) for value in parts[1:]]
    except ValueError:
        # Column headers and partial lines land here.
        return None

    return timestamp, values


def print_sample(timestamp, values):
    print(timestamp, *values)


# -----------------------------------------------------------------------------
# Signal processing
# -----------------------------------------------------------------------------

def fourier_filter(times, channel_values, cutoff = FILTER_CUTOFF_HZ):
    """Zero out frequency content above FILTER_CUTOFF_HZ, per channel."""
    if len(times) < 2:
        return channel_values

    intervals = np.diff(times)
    intervals = intervals[intervals > 0]

    if intervals.size == 0:
        return channel_values

    sample_period = float(np.median(intervals))
    filtered = []

    for values in channel_values:
        values = np.asarray(values, dtype=float)

        spectrum = np.fft.rfft(values)
        frequencies = np.fft.rfftfreq(values.size, d=sample_period)
        spectrum[frequencies > cutoff] = 0

        filtered.append(np.fft.irfft(spectrum, n=values.size))

    return filtered

def rolling_turbulence_intensity(times, channel_values, window_seconds=TURBULENCE_WINDOW_SEC):
    """Calculates the rolling standard deviation (RMS pressure fluctuation) per channel."""
    if len(times) < 2:
        return channel_values

    dt = float(np.median(np.diff(times)))
    if dt <= 0:
        return channel_values

    window_samples = int(round(window_seconds / dt))
    window_samples = max(2, window_samples)  

    turbulence_signals = []
    for values in channel_values:
        series = pd.Series(values)
        rolling_std = series.rolling(window=window_samples, min_periods=1).std().values
        
        rolling_std[np.isnan(rolling_std)] = 0.0
        turbulence_signals.append(rolling_std)

    return turbulence_signals

def apply_selected_filter(times, channel_values):
    """Routes channel data to the selected filtering technique."""
    if not FILTER_MODE or len(times) < 2:
        return channel_values

    if FILTER_METHOD == "turbulence":
        return rolling_turbulence_intensity(times, channel_values)

    if FILTER_METHOD == "fourier":
        return fourier_filter(times, channel_values)


# -----------------------------------------------------------------------------
# Plot helpers
# -----------------------------------------------------------------------------

def style_pressure_axis(axis):
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Pressure (kPa)")
    axis.grid(alpha=0.2)


def add_channel_legend(axis):
    axis.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=CHANNELS,
        frameon=False,
        handlelength=0.8,
        handletextpad=0.4,
        columnspacing=0.9,
    )


def filter_suffix():
    if not FILTER_MODE:
        return ""
    if FILTER_METHOD == "turbulence":
        return f" — Turbulence Intensity ({TURBULENCE_WINDOW_SEC}s Window)"
    elif FILTER_METHOD == "fourier":
        return f" — {FILTER_CUTOFF_HZ} Hz Cutoff" if FILTER_MODE else ""


# -----------------------------------------------------------------------------
# Live mode
# -----------------------------------------------------------------------------

class LivePlot:
    """Streams samples from the serial port into a scrolling multi-channel graph."""

    def __init__(self, ser):
        self.ser = ser
        self.first_timestamp = None

        self.times = deque()
        self.channels = [deque() for _ in range(CHANNELS)]

        self.figure, self.axis = plt.subplots(figsize=(11, 5))
        self.lines = [
            self.axis.plot([], [], label=f"ch{i}")[0]
            for i in range(CHANNELS)
        ]

        style_pressure_axis(self.axis)
        add_channel_legend(self.axis)

        self.figure.suptitle(f"Live Pressure Sensor Data{filter_suffix()}")

    def drain_serial(self):
        """Consume every sample currently waiting in the input buffer."""
        while self.ser.in_waiting:
            sample = read_sample(self.ser)

            if sample is None:
                continue

            timestamp, values = sample

            if self.first_timestamp is None:
                self.first_timestamp = timestamp

            time_s = (timestamp - self.first_timestamp) / 1000.0
            self.times.append(time_s)

            for channel, value in zip(self.channels, values):
                channel.append(value)

            print_sample(timestamp, values)

            # Keep only the configured live window.
            while self.times and time_s - self.times[0] > 10:
                self.times.popleft()

                for channel in self.channels:
                    channel.popleft()

    def update(self, _frame):
        self.drain_serial()

        if not self.times:
            return self.lines

        times = list(self.times)
        values = [list(channel) for channel in self.channels]

        if FILTER_MODE:
            values = apply_selected_filter(times, values)

        for line, channel_values in zip(self.lines, values):
            line.set_data(times, channel_values)

        self.axis.set_xlim(
            max(0, times[-1] - 10),
            max(10, times[-1]),
        )
        self.axis.relim()
        self.axis.autoscale_view(scalex=False)

        return self.lines

    def run(self):
        animation = FuncAnimation(
            self.figure,
            self.update,
            interval=50,           # redraw every 50 ms
            cache_frame_data=False,
        )

        self.figure.tight_layout()
        plt.show()

        # Keeps the animation alive until the window closes.
        del animation


def run_live_mode(ser):
    print("Close the graph to stop.")
    LivePlot(ser).run()


# -----------------------------------------------------------------------------
# Export mode
# -----------------------------------------------------------------------------

def run_export_mode(ser):
    """Record for RECORDING_SECONDS, then write a CSV and a graph."""
    times = []
    channels = [[] for _ in range(CHANNELS)]

    first_timestamp = None
    start_time = time.time()

    print(f"Recording for {RECORDING_SECONDS} seconds...")

    while time.time() - start_time < RECORDING_SECONDS:
        sample = read_sample(ser)

        if sample is None:
            continue

        timestamp, values = sample

        if first_timestamp is None:
            first_timestamp = timestamp

        times.append((timestamp - first_timestamp) / 1000.0)

        for channel, value in zip(channels, values):
            channel.append(value)

        print_sample(timestamp, values)

    if FILTER_MODE:
        channels = apply_selected_filter(times, channels)

    save_data(times, channels)


def save_data(times, channels):
    """Write the CSV and the pressure graph for all channels."""
    if not times:
        print("No valid sensor data was recorded.")
        return

    os.makedirs(DATA_DIRECTORY, exist_ok=True)

    run_name = datetime.now().strftime("pressure_%Y%m%d_%H%M%S")

    if FILTER_MODE:
        run_name += f"_{FILTER_METHOD}"

    base_path = os.path.join(DATA_DIRECTORY, run_name)
    csv_path = base_path + ".csv"
    graph_path = base_path + ".png"

    with open(csv_path, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        unit_header = "std_kPa" if (FILTER_MODE and FILTER_METHOD == "turbulence") else "kPa"
        writer.writerow(["time_s"] + [f"ch{i}_kPa" for i in range(CHANNELS)])
        writer.writerows(zip(times, *channels))

    figure, axis = plt.subplots(figsize=(10, 5))

    for index, channel_values in enumerate(channels):
        axis.plot(times, channel_values, linewidth=1.5, label=f"ch{index}")

    style_pressure_axis(axis)
    axis.margins(x=0.02)
    add_channel_legend(axis)

    if FILTER_MODE:
        title = f"Filtered Pressure Data{filter_suffix()}"
    else:
        title = f"Pressure Data — {RECORDING_SECONDS} Second Recording"

    figure.suptitle(title)
    figure.tight_layout()
    figure.savefig(graph_path, dpi=300, bbox_inches="tight")
    plt.close(figure)

    print(f"CSV saved:   {csv_path}")
    print(f"Graph saved: {graph_path}")


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def main():
    # Validated before opening the port so a typo fails instantly.
    if MODE not in ("live", "export"):
        print(f'Invalid MODE: "{MODE}". Use "live" or "export".')
        return

    print(f"Mode: {MODE} {'filtered' if FILTER_MODE else 'unfiltered'}")

    with serial.Serial(PORT, BAUD, timeout=0.1) as ser:
        # Opening the serial port can reset the ESP32.
        time.sleep(2)
        ser.reset_input_buffer()

        if MODE == "live":
            run_live_mode(ser)
        else:
            run_export_mode(ser)


if __name__ == "__main__":
    main()