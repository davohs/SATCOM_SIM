import numpy as np
import matplotlib.pyplot as plt
import scipy.signal as signal

# Sampling frequency and cutoff frequency
fs = 1000  # Hz
fc = 100    # Hz (Cutoff frequency)

# Normalize frequency
Wn = fc / (fs / 2)  # Normalize by Nyquist frequency

# Design a second-order Butterworth filter
b, a = signal.butter(N=2, Wn=Wn, btype='low', analog=False, output='ba')

# Create a test signal (10 Hz sine wave + 100 Hz noise)
t = np.linspace(0, 1, fs, endpoint=False)                           # Time vector
x = np.sin(2 * np.pi * 10 * t) + 0.5 * np.sin(2 * np.pi * 100 * t)  # Signal with noise

# Apply the filter
y = signal.lfilter(b, a, x)

# Compute Frequency Response
w, h = signal.freqz(b, a, worN=1024)  # Compute frequency response
frequencies = w * fs / (2 * np.pi)  # Convert to Hz

# Plot both time-domain and frequency response
plt.figure(figsize=(12, 6))

# Subplot 1: Time Domain Signal
plt.subplot(2, 1, 1)
plt.plot(t, x, label='Original Signal')
plt.plot(t, y, label='Filtered Signal', linewidth=2)
plt.legend()
plt.xlabel("Time [seconds]")
plt.ylabel("Amplitude")
plt.title("Time Domain: Original vs. Filtered Signal")
plt.grid()

# Subplot 2: Frequency Response
plt.subplot(2, 1, 2)
plt.plot(frequencies, 20 * np.log10(abs(h)), 'b')  # Convert magnitude to dB
plt.axvline(fc, color='r', linestyle='--', label=f'Cutoff Frequency ({fc} Hz)')
plt.xlabel("Frequency [Hz]")
plt.ylabel("Magnitude [dB]")
plt.title("Frequency Response of Butterworth Filter")
plt.legend()
plt.grid()

plt.tight_layout()
plt.show()
