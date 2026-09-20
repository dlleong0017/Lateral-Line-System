import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def analyze_csv_fft(csv_file_path):
    # Load the CSV data
    df = pd.read_csv(csv_file_path)

    # Extract time array and determine sampling parameters
    time = df['time_s'].values
    dt = np.mean(np.diff(time))  # Time step / sampling interval
    fs = 1.0 / dt                # Sampling frequency (Hz)
    N = len(time)                # Total number of samples

    # Frequency axis for single-sided FFT spectrum
    freqs = np.fft.rfftfreq(N, d=dt)

    # Extract channel names (excluding the time column)
    channel_cols = [col for col in df.columns if col != 'time_s']
    num_channels = len(channel_cols)

    # 1. Provide ample vertical space per row (1.8 inches per row, minimum 12 inches total)
    fig_height = max(12, 1.8 * num_channels)
    fig, axes = plt.subplots(
        num_channels, 2, 
        figsize=(12, fig_height), 
        sharex='col',
        constrained_layout=True  # Handles subplots, labels, and titles cleanly
    )

    # Ensure axes is 2D array even if single row
    if num_channels == 1:
        axes = np.expand_dims(axes, axis=0)

    for i, col in enumerate(channel_cols):
        signal = df[col].values

        # Compute Real FFT (rfft) for real-valued signals
        fft_spectrum = np.fft.rfft(signal)
        
        # Calculate Magnitude Spectrum (scaled by number of samples N)
        magnitude = np.abs(fft_spectrum) * (2.0 / N)

        # Plot Time-Domain Signal
        axes[i, 0].plot(time, signal, color='tab:blue')
        axes[i, 0].set_ylabel(f'{col}', fontsize=8)
        axes[i, 0].grid(True, linestyle='--', alpha=0.5)
        axes[i, 0].tick_params(axis='both', labelsize=8)

        # Plot Frequency-Domain Spectrum
        axes[i, 1].plot(freqs, magnitude, color='tab:red')
        axes[i, 1].set_ylabel('Amplitude', fontsize=8)
        axes[i, 1].grid(True, linestyle='--', alpha=0.5)
        axes[i, 1].tick_params(axis='both', labelsize=8)

    # 2. Set Column Titles on top axes without suptitle collision
    axes[0, 0].set_title('Time Domain', fontsize=12, fontweight='bold', pad=12)
    axes[0, 1].set_title('Frequency Domain (FFT Magnitude)', fontsize=12, fontweight='bold', pad=12)

    # 3. Bottom X-Axis Labels
    axes[-1, 0].set_xlabel('Time (s)', fontsize=10, fontweight='bold')
    axes[-1, 1].set_xlabel('Frequency (Hz)', fontsize=10, fontweight='bold')

    # 4. Overall Figure Title at the top
    fig.suptitle('Time Domain Signals & Fourier Transform Spectrums', fontsize=14, fontweight='bold')

    plt.show()

if __name__ == '__main__':
    # Robust path relative to script location
    SCRIPT_DIR = Path(__file__).resolve().parent
    csv_filename = SCRIPT_DIR / 'Data' / '9-17-2026Testing' / '5.csv'

    analyze_csv_fft(csv_filename)