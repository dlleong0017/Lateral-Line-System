import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import welch
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

        # Subtract the mean (DC component) from the signal
        signal_detrended = signal - np.mean(signal)

        # Compute Real FFT (rfft) for real-valued signals
        fft_spectrum = np.fft.rfft(signal_detrended)
        
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

def analyze_csv_fft_overlaid(csv_file_path):
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

    # Create a 1x2 subplot layout for overlaid signals
    fig, axes = plt.subplots(
        1, 2, 
        figsize=(14, 6), 
        constrained_layout=True
    )

    # Color palette cycle for distinct channel colors
    colors = plt.cm.tab10(np.linspace(0, 1, len(channel_cols)))

    for col, color in zip(channel_cols, colors):
        signal = df[col].values

        # Subtract the mean (DC component) from the signal
        signal_detrended = signal - np.mean(signal)

        # Compute Real FFT (rfft) for real-valued signals
        fft_spectrum = np.fft.rfft(signal_detrended)
        
        # Calculate Magnitude Spectrum (scaled by 2 / N)
        magnitude = np.abs(fft_spectrum) * (2.0 / N)

        # Plot Time-Domain Signal on left subplot
        axes[0].plot(time, signal, label=col, color=color, alpha=0.8, linewidth=1.2)

        # Plot Frequency-Domain Spectrum on right subplot
        axes[1].plot(freqs, magnitude, label=col, color=color, alpha=0.8, linewidth=1.2)

    # Time Domain Formatting
    axes[0].set_title('Time Domain (Overlaid)', fontsize=12, fontweight='bold', pad=10)
    axes[0].set_xlabel('Time (s)', fontsize=10, fontweight='bold')
    axes[0].set_ylabel('Signal Value', fontsize=10, fontweight='bold')
    axes[0].grid(True, linestyle='--', alpha=0.5)
    axes[0].legend(loc='upper right', fontsize=8)

    # Frequency Domain Formatting
    axes[1].set_title('Frequency Domain (FFT Magnitude)', fontsize=12, fontweight='bold', pad=10)
    axes[1].set_xlabel('Frequency (Hz)', fontsize=10, fontweight='bold')
    axes[1].set_ylabel('Amplitude', fontsize=10, fontweight='bold')
    axes[1].grid(True, linestyle='--', alpha=0.5)
    axes[1].legend(loc='upper right', fontsize=8)

    # Overall Figure Title
    fig.suptitle('Fourier Transform, verified sine data', fontsize=14, fontweight='bold')

    plt.show()

def analyze_csv_psd(csv_file_path):
    # Load the CSV data
    df = pd.read_csv(csv_file_path)

    # Extract time array and determine sampling parameters
    time = df['time_s'].values
    dt = np.mean(np.diff(time))  # Time step / sampling interval
    fs = 1.0 / dt                # Sampling frequency (Hz)

    # Extract channel names (excluding the time column)
    channel_cols = [col for col in df.columns if col != 'time_s']
    num_channels = len(channel_cols)

    # Provide ample vertical space per row
    fig_height = max(12, 1.8 * num_channels)
    fig, axes = plt.subplots(
        num_channels, 2, 
        figsize=(12, fig_height), 
        sharex='col',
        constrained_layout=True
    )

    # Ensure axes is 2D array even if single row
    if num_channels == 1:
        axes = np.expand_dims(axes, axis=0)

    for i, col in enumerate(channel_cols):
        signal = df[col].values

        # Subtract the mean (DC component) from the signal
        signal_detrended = signal - np.mean(signal)

        # Compute Power Spectral Density using Welch's method
        # nperseg defines window length (defaults to 256, set relative to length)
        nperseg = min(len(signal), 1024)
        freqs, psd = welch(signal_detrended, fs=fs, nperseg=nperseg)

        # Plot Time-Domain Signal
        axes[i, 0].plot(time, signal, color='tab:blue')
        axes[i, 0].set_ylabel(f'{col}', fontsize=8)
        axes[i, 0].grid(True, linestyle='--', alpha=0.5)
        axes[i, 0].tick_params(axis='both', labelsize=8)

        # Plot Power Spectral Density (PSD)
        axes[i, 1].plot(freqs, psd, color='tab:red')
        axes[i, 1].set_ylabel('PSD (V²/Hz)', fontsize=8)
        axes[i, 1].grid(True, linestyle='--', alpha=0.5)
        axes[i, 1].tick_params(axis='both', labelsize=8)

    # Set Column Titles
    axes[0, 0].set_title('Time Domain', fontsize=12, fontweight='bold', pad=12)
    axes[0, 1].set_title('Power Spectral Density (PSD)', fontsize=12, fontweight='bold', pad=12)

    # Bottom X-Axis Labels
    axes[-1, 0].set_xlabel('Time (s)', fontsize=10, fontweight='bold')
    axes[-1, 1].set_xlabel('Frequency (Hz)', fontsize=10, fontweight='bold')

    # Overall Figure Title
    fig.suptitle('Time Domain Signals & Power Spectral Density', fontsize=14, fontweight='bold')

    plt.show()

def analyze_csv_psd_overlaid(csv_file_path):
    # Load the CSV data
    df = pd.read_csv(csv_file_path)

    # Extract time array and determine sampling parameters
    time = df['time_s'].values
    dt = np.mean(np.diff(time))  # Time step / sampling interval
    fs = 1.0 / dt                # Sampling frequency (Hz)

    # Extract channel names (excluding the time column)
    channel_cols = [col for col in df.columns if col != 'time_s']

    # Create a 1x2 subplot layout for overlaid signals
    fig, axes = plt.subplots(
        1, 2, 
        figsize=(14, 6), 
        constrained_layout=True
    )

    # Color palette cycle for distinct channel colors
    colors = plt.cm.tab10(np.linspace(0, 1, len(channel_cols)))

    for col, color in zip(channel_cols, colors):
        signal = df[col].values

        # Subtract the mean (DC component) from the signal
        signal_detrended = signal - np.mean(signal)

        # Compute Power Spectral Density using Welch's method
        nperseg = min(len(signal), 1024)
        freqs, psd = welch(signal_detrended, fs=fs, nperseg=nperseg)

        # Plot Time-Domain Signal on left subplot
        axes[0].plot(time, signal, label=col, color=color, alpha=0.8, linewidth=1.2)

        # Plot PSD on right subplot
        axes[1].plot(freqs, psd, label=col, color=color, alpha=0.8, linewidth=1.2)

    # Time Domain Formatting
    axes[0].set_title('Time Domain (Overlaid)', fontsize=12, fontweight='bold', pad=10)
    axes[0].set_xlabel('Time (s)', fontsize=10, fontweight='bold')
    axes[0].set_ylabel('Signal Value', fontsize=10, fontweight='bold')
    axes[0].grid(True, linestyle='--', alpha=0.5)
    axes[0].legend(loc='upper right', fontsize=8)

    # PSD Formatting
    axes[1].set_title('Power Spectral Density (Overlaid)', fontsize=12, fontweight='bold', pad=10)
    axes[1].set_xlabel('Frequency (Hz)', fontsize=10, fontweight='bold')
    axes[1].set_ylabel('PSD (V²/Hz)', fontsize=10, fontweight='bold')
    axes[1].grid(True, linestyle='--', alpha=0.5)
    axes[1].legend(loc='upper right', fontsize=8)

    # Overall Figure Title
    fig.suptitle('Power Spectral Density, verified sine data', fontsize=14, fontweight='bold')

    plt.show()

if __name__ == '__main__':
    # Robust path relative to script location
    SCRIPT_DIR = Path(__file__).resolve().parent
    csv_filename = SCRIPT_DIR / 'Data' / 'VerifiedTesting' / 'multi_sine_data.csv'

    # analyze_csv_fft(csv_filename)          # fourier rows
    # analyze_csv_psd(csv_filename)          # power spectial rows

    analyze_csv_fft_overlaid(csv_filename)          # fourier combined
    # analyze_csv_psd_overlaid(csv_filename)          # power spectral combined
