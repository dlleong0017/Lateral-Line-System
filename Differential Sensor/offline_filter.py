#!/usr/bin/env python3
"""Offline CSV Pressure Filter & Visualizer

Loads a pressure recording CSV file (formatted as time_s, ch0_kPa, ch1_kPa, ...),
applies a selected signal processing filter, saves the filtered data to a new CSV,
and displays a multi-channel plot.
"""

import argparse
import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Signal Processing Methods
# -----------------------------------------------------------------------------

def apply_fourier(times, channel_values, low_cutoff_hz=0.5, high_cutoff_hz=1.5):
    """Applies a Fourier Transform (FFT) low-pass filter with smooth windowing."""
    if len(times) < 2:
        return channel_values

    dt = float(np.median(np.diff(times)))
    if dt <= 0:
        return channel_values

    n = len(times)
    frequencies = np.fft.rfftfreq(n, d=dt)

    # Cosine-tapered frequency mask to attenuate high frequencies smoothly
    freq_mask = np.ones_like(frequencies)

    low_transition = low_cutoff_hz * 0.25
    high_transition = high_cutoff_hz * 0.25

    for idx, f in enumerate(frequencies):
            # 1. High-pass side (cut off frequencies that are too low)
            if f < low_cutoff_hz - low_transition:
                freq_mask[idx] = 0.0
            elif f < low_cutoff_hz + low_transition:
                progress = (f - (low_cutoff_hz - low_transition)) / (2 * low_transition)
                freq_mask[idx] = 0.5 * (1.0 - np.cos(np.pi * progress))

            # 2. Low-pass side (cut off frequencies that are too high)
            elif f > high_cutoff_hz + high_transition:
                freq_mask[idx] = 0.0
            elif f > high_cutoff_hz - high_transition:
                progress = (f - (high_cutoff_hz - high_transition)) / (2 * high_transition)
                freq_mask[idx] = 0.5 * (1.0 + np.cos(np.pi * progress))

    filtered = []
    for values in channel_values:
        fft_coefficients = np.fft.rfft(values)
        fft_filtered = fft_coefficients * freq_mask
        filtered_signal = np.fft.irfft(fft_filtered, n=n)
        filtered.append(filtered_signal)

    return filtered

def apply_turbulence_intensity(times, channel_values, window_seconds=2.5):
    """Calculates rolling standard deviation (RMS pressure fluctuation) per channel."""
    if len(times) < 2:
        return channel_values

    intervals = np.diff(times)
    intervals = intervals[intervals > 0]
    if intervals.size == 0:
        return channel_values

    sample_period = float(np.median(intervals))
    window_samples = max(2, int(round(window_seconds / sample_period)))

    filtered = []
    for values in channel_values:
        series = pd.Series(values)
        rolling_std = series.rolling(window=window_samples, min_periods=1).std().values
        rolling_std[np.isnan(rolling_std)] = 0.0
        filtered.append(rolling_std)

    return filtered


def apply_butterworth(times, channel_values, cutoff_hz=1.5, order=4):
    """Applies a zero-phase Butterworth low-pass filter."""
    from scipy.signal import butter, filtfilt

    if len(times) < 2:
        return channel_values

    dt = float(np.median(np.diff(times)))
    fs = 1.0 / dt if dt > 0 else 20.0
    nyquist = 0.5 * fs
    normal_cutoff = min(0.99, cutoff_hz / nyquist)

    b, a = butter(order, normal_cutoff, btype="low", analog=False)
    return [filtfilt(b, a, v) for v in channel_values]


def apply_ema(channel_values, alpha=0.1):
    """Applies an Exponential Moving Average low-pass filter."""
    filtered = []
    for v in channel_values:
        arr = np.zeros_like(v, dtype=float)
        arr[0] = v[0]
        for t in range(1, len(v)):
            arr[t] = alpha * v[t] + (1 - alpha) * arr[t-1]
        filtered.append(arr)
    return filtered


def apply_savgol(channel_values, window_length=21, polyorder=2):
    """Applies a Savitzky-Golay polynomial smoothing filter."""
    from scipy.signal import savgol_filter

    n_samples = len(channel_values[0])
    win = min(window_length, n_samples)
    if win % 2 == 0:
        win -= 1
    if win >= 3:
        return [savgol_filter(v, win, polyorder=polyorder) for v in channel_values]
    return channel_values


# -----------------------------------------------------------------------------
# Main Processing & Visualizer
# -----------------------------------------------------------------------------

def process_file(csv_filepath, method="turbulence", param=None, low_cutoff=0.5, high_cutoff=1.5, save_output=True, show_plot=True):
    if not os.path.exists(csv_filepath):
        print(f"Error: File '{csv_filepath}' not found.")
        return

    # 1. Load CSV data
    df = pd.read_csv(csv_filepath)
    time_col = df.columns[0]
    times = df[time_col].values

    channel_cols = [col for col in df.columns if col != time_col]
    raw_channels = [df[col].values for col in channel_cols]

    # 2. Apply selected filtering method
    if method == "fourier":
        filtered_channels = apply_fourier(times, raw_channels, low_cutoff_hz=low_cutoff, high_cutoff_hz=high_cutoff)
        y_label = "Pressure (kPa)"
        title_suffix = f"Fourier Bandpass ({low_cutoff}–{high_cutoff} Hz)"
        file_suffix = f"fourier_{low_cutoff}to{high_cutoff}hz"

    elif method == "turbulence":
        window_sec = float(param) if param is not None else 2.5
        filtered_channels = apply_turbulence_intensity(times, raw_channels, window_seconds=window_sec)
        y_label = "Std Dev (kPa)"
        title_suffix = f"Turbulence Intensity ({window_sec}s Window)"
        file_suffix = f"turbulence_{window_sec}s"

    elif method == "butterworth":
        cutoff = float(param) if param is not None else 1.5
        filtered_channels = apply_butterworth(times, raw_channels, cutoff_hz=cutoff)
        y_label = "Pressure (kPa)"
        title_suffix = f"Butterworth Filter ({cutoff} Hz Cutoff)"
        file_suffix = f"butterworth_{cutoff}hz"

    elif method == "ema":
        alpha = float(param) if param is not None else 0.1
        filtered_channels = apply_ema(raw_channels, alpha=alpha)
        y_label = "Pressure (kPa)"
        title_suffix = f"EMA Filter (alpha={alpha})"
        file_suffix = f"ema_{alpha}"

    elif method == "savgol":
        win = int(param) if param is not None else 21
        filtered_channels = apply_savgol(raw_channels, window_length=win)
        y_label = "Pressure (kPa)"
        title_suffix = f"Savitzky-Golay Filter (Window={win})"
        file_suffix = f"savgol_win{win}"

    else:
        print(f"Error: Unknown filtering method '{method}'.")
        return

    # 3. Save output CSV
    base, ext = os.path.splitext(csv_filepath)
    if save_output:
        out_csv = f"{base}_{file_suffix}{ext}"
        unit_header = "std_kPa" if method == "turbulence" else "kPa"
        
        out_df = pd.DataFrame({time_col: times})
        for i, col_name in enumerate(channel_cols):
            clean_name = col_name.split("_")[0]  # Extracts ch0, ch1, etc.
            out_df[f"{clean_name}_{unit_header}"] = filtered_channels[i]

        out_df.to_csv(out_csv, index=False)
        print(f"Filtered CSV saved: {out_csv}")

    # 4. Generate Plot
    fig, axis = plt.subplots(figsize=(11, 5))
    for i, col_name in enumerate(channel_cols):
        clean_name = col_name.split("_")[0]
        axis.plot(times, filtered_channels[i], label=clean_name, linewidth=1.2)

    axis.set_xlabel("Time (s)")
    axis.set_ylabel(y_label)
    axis.grid(alpha=0.2)
    axis.set_title(f"Offline Filtered Data — {title_suffix}", fontweight="bold")
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=len(channel_cols), frameon=False)

    plt.tight_layout()

    if save_output:
        out_png = f"{base}_{file_suffix}.png"
        fig.savefig(out_png, dpi=300, bbox_inches="tight")
        print(f"Graph saved:        {out_png}")

    if show_plot:
        plt.show()


# -----------------------------------------------------------------------------
# Command Line Interface
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply signal filtering to a pressure sensor CSV file.")
    parser.add_argument("file", type=str, help="Path to input CSV file")
    parser.add_argument("--method", type=str, default="turbulence", 
                        choices=["fourier", "turbulence", "butterworth", "ema", "savgol"], 
                        help="Filtering method (default: turbulence)")
    parser.add_argument("--param", type=float, default=None, 
                        help="Parameter value for single-value filters (window sec for turbulence, cutoff Hz for butterworth, alpha for ema, win length for savgol)")
    parser.add_argument("--low", type=float, default=0.5, 
                        help="Low cutoff frequency in Hz for Fourier bandpass (default: 0.5)")
    parser.add_argument("--high", type=float, default=1.5, 
                        help="High cutoff frequency in Hz for Fourier bandpass (default: 1.5)")

    args = parser.parse_args()
    process_file(args.file, method=args.method, param=args.param, low_cutoff=args.low, high_cutoff=args.high)