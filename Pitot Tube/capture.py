#!/usr/bin/env python3
"""Live-plot or record fluid velocity and pressure from a serial sensor.

Serial line format (one sample per line):
    timestamp_ms,velocity_m_s,pressure_kpa
"""

import csv
import os
import time
from collections import deque
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import serial
from matplotlib.animation import FuncAnimation


# =============================================================================
# Configuration
# =============================================================================

MODE = "live"                           # "live" or "export"

FILTER_MODE = True                      # low-pass the velocity
FILTER_CUTOFF_HZ = 5                    # discard content above this frequency

RECORDING_SECONDS = 300                 # export mode only
DATA_DIRECTORY = "Data/8-5-26 Testing"  # export mode only

PORT = "COM4"
BAUD = 115200

# =============================================================================


# -----------------------------------------------------------------------------
# Serial input
# -----------------------------------------------------------------------------

def read_sample(ser):
    """Return (timestamp_ms, velocity, pressure), or None for a bad line."""
    text = ser.readline().decode("ascii", errors="ignore").strip()
    parts = text.split(",")

    if len(parts) != 3:
        return None

    try:
        return int(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        # Column headers and partial lines land here.
        return None


def print_sample(timestamp, velocity, pressure):
    print(f"{timestamp},{velocity:.4f},{pressure:.4f}")


# -----------------------------------------------------------------------------
# Signal processing
# -----------------------------------------------------------------------------

def fourier_filter(times, values):
    """Zero out frequency content above FILTER_CUTOFF_HZ."""
    values = np.asarray(values, dtype=float)

    if values.size < 2:
        return values

    intervals = np.diff(times)
    intervals = intervals[intervals > 0]

    if intervals.size == 0:
        return values

    sample_period = float(np.median(intervals))

    spectrum = np.fft.rfft(values)
    frequencies = np.fft.rfftfreq(values.size, d=sample_period)
    spectrum[frequencies > FILTER_CUTOFF_HZ] = 0

    return np.fft.irfft(spectrum, n=values.size)


def decimate(times, values):
    """Thin a trace to ~20,000 drawn points. Stored data is never touched."""
    if len(times) <= 20_000:
        return times, values

    stride = len(times) // 20_000 + 1
    return times[::stride], values[::stride]


# -----------------------------------------------------------------------------
# Plot helpers
# -----------------------------------------------------------------------------

def style_velocity_axis(axis):
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Fluid Velocity (m/s)")
    axis.grid(alpha=0.2)


def apply_velocity_ylim(axis, values):
    """Fit the y-axis to the data with 5% padding above and below."""
    values = np.asarray(values, dtype=float)

    if values.size == 0:
        return

    data_min = float(np.nanmin(values))
    data_max = float(np.nanmax(values))
    span = data_max - data_min

    # Flat trace: fall back to a window at least 0.05 m/s tall.
    if span <= 0:
        span = max(abs(data_max), 0.05)

    axis.set_ylim(data_min - 0.05 * span, data_max + 0.05 * span)


def filter_suffix():
    return f" — {FILTER_CUTOFF_HZ} Hz Cutoff" if FILTER_MODE else ""


# -----------------------------------------------------------------------------
# Live mode
# -----------------------------------------------------------------------------

class LivePlot:
    """Streams samples from the serial port into a scrolling velocity graph."""

    def __init__(self, ser):
        self.ser = ser
        self.first_timestamp = None

        self.times = deque()
        self.velocities = deque()
        self.pressures = deque()

        self.figure, self.axis = plt.subplots(figsize=(10, 5))
        self.line, = self.axis.plot([], [], linewidth=1.5, color="tab:blue")

        style_velocity_axis(self.axis)
        self.axis.set_xlim(0, 10)

        self.figure.suptitle(f"Live Fluid Velocity{filter_suffix()}")

    def drain_serial(self):
        """Consume every sample currently waiting in the input buffer."""
        while self.ser.in_waiting:
            sample = read_sample(self.ser)

            if sample is None:
                continue

            timestamp, velocity, pressure = sample

            if self.first_timestamp is None:
                self.first_timestamp = timestamp

            self.times.append((timestamp - self.first_timestamp) / 1000.0)
            self.velocities.append(velocity)
            self.pressures.append(pressure)

            print_sample(timestamp, velocity, pressure)

    def update(self, _frame):
        self.drain_serial()

        if not self.times:
            return (self.line,)

        times = list(self.times)
        velocities = list(self.velocities)

        if FILTER_MODE:
            velocities = fourier_filter(times, velocities)

        draw_times, draw_velocities = decimate(times, velocities)
        self.line.set_data(draw_times, draw_velocities)

        # Anchored at 0 s; the right edge grows with the run, 10 s minimum.
        self.axis.set_xlim(0, max(10, times[-1] * 1.02))
        apply_velocity_ylim(self.axis, draw_velocities)

        return (self.line,)

    def run(self):
        animation = FuncAnimation(
            self.figure,
            self.update,
            interval=50,          # redraw every 50 ms
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
    velocities = []
    pressures = []

    first_timestamp = None
    start_time = time.time()

    print(f"Recording for {RECORDING_SECONDS} seconds...")

    while time.time() - start_time < RECORDING_SECONDS:
        sample = read_sample(ser)

        if sample is None:
            continue

        timestamp, velocity, pressure = sample

        if first_timestamp is None:
            first_timestamp = timestamp

        times.append((timestamp - first_timestamp) / 1000.0)
        velocities.append(velocity)
        pressures.append(pressure)

        print_sample(timestamp, velocity, pressure)

    save_data(times, velocities, pressures)


def save_data(times, velocities, pressures):
    """Write the raw CSV and the velocity graph."""
    if not times:
        print("No valid sensor data was recorded.")
        return

    os.makedirs(DATA_DIRECTORY, exist_ok=True)

    run_name = datetime.now().strftime("sensor_%Y%m%d_%H%M%S")
    base_path = os.path.join(DATA_DIRECTORY, run_name)
    csv_path = base_path + ".csv"

    # Pressure is recorded but not graphed.
    with open(csv_path, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["time_s", "velocity_m_s", "pressure_kpa"])
        writer.writerows(zip(times, velocities, pressures))

    if FILTER_MODE:
        plot_velocities = fourier_filter(times, velocities)
        graph_path = base_path + "_filtered.png"
        title = f"Filtered Fluid Velocity{filter_suffix()}"
    else:
        plot_velocities = np.asarray(velocities, dtype=float)
        graph_path = base_path + ".png"
        title = f"Fluid Velocity — {RECORDING_SECONDS} Second Recording"

    figure, axis = plt.subplots(figsize=(10, 5))
    axis.plot(times, plot_velocities, linewidth=1.5, color="tab:blue")

    style_velocity_axis(axis)
    axis.margins(x=0.02)
    apply_velocity_ylim(axis, plot_velocities)

    figure.suptitle(title)
    figure.tight_layout()
    figure.savefig(graph_path, dpi=300, bbox_inches="tight")
    plt.close(figure)

    print(f"Raw CSV saved: {csv_path}")
    print(f"Graph saved:   {graph_path}")


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
        # Opening the serial port resets many ESP32 boards.
        time.sleep(2)
        ser.reset_input_buffer()

        if MODE == "live":
            run_live_mode(ser)
        else:
            run_export_mode(ser)


if __name__ == "__main__":
    main()