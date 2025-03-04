# Import needed packages
from os import link
import numpy as np
import matplotlib.pyplot as plt
import scipy.signal as signal

# Import from other files
from link_budget import OpticalLinkBudget as lb


#####=- Functions -=#####
# Convert dB to linear scale
def db_2_lin(val):
    lin_val = 10 ** (val / 10)
    return lin_val


# Generate PRBS signal
def gen_prbs(n_bits):
    seed_size = 5
    taps = [5, 2]  # Feedback taps positions (e.g., [5, 2] for x^5 + x^2 + 1)
    seed = np.random.choice([0, 1], size=(seed_size))

    state = np.array(seed, dtype=int)
    taps = np.array(taps) - 1  # Convert to zero-based indexing
    signal = []

    for _ in range(n_bits):
        new_bit = np.bitwise_xor.reduce(state[taps])  # XOR the tapped bits
        signal.append(state[-1])  # Output the last bit
        state = np.roll(state, -1)  # Shift left
        state[-1] = new_bit  # Insert new bit

    return signal


# Calculate time-variant loss: jitter-induced scintillation
def sample_xy(std, la, len):
    theta_x = np.random.normal(0, std, len)
    theta_y = np.random.normal(0, std, len)
    x = np.tan(theta_x) * la
    y = np.tan(theta_y) * la
    return x, y


def butt_filt(fs, fc, x, y):
    # FILTER #
    # Normalize frequency
    Wn = fc / (fs / 2)  # Normalize by Nyquist frequency

    # Design a second-order Butterworth filter
    b, a = signal.butter(N=2, Wn=Wn, btype='low', analog=False, output='ba')

    # Apply filter
    x_f = signal.lfilter(b, a, x)
    y_f = signal.lfilter(b, a, y)
    return x_f, y_f


def intensity_function(x_f, y_f):
    # Substitute in intensity function
    r = np.sqrt(x_f ** 2 + y_f ** 2)
    w_0 = lam / (theta_div * np.pi * n)
    z_R = np.pi * w_0 ** 2 * n / lam
    w = w_0 * np.sqrt(1 + (z / z_R) ** 2)
    L_pj = (w_0 / w) ** 2 * np.exp(-2 * r ** 2 / w ** 2)
    return L_pj


# Generate AWGN noise for given SNR
def gen_awgn(signal, snr_db):
    signal_power = np.mean(signal ** 2)  # Compute signal power
    snr_linear = db_2_lin(snr_db)  # Convert SNR from dB to linear scale
    noise_power = signal_power / snr_linear  # Compute noise power
    noise = np.random.normal(0, np.sqrt(noise_power), signal.shape)  # Generate Gaussian noise

    return noise


###--- Simulation Input ---####
random = False  # Switch: if False, use seed 0
R_f = 10  # Frequency ratio: ratio between transmitter frequency and random frequency (visual)

# PRBS
bitrate = 50  # Transmitted bits per second [-]
t_end = 1  # Signal duration [s]

# Transmitter
P_l = 0.08  # Transmitter laser power [W]
lam = 1550 * 10 ** (-9)  # Laser wavelength [m]
theta_div = 10 * 10 ** (-6)  # Laser divergence [rad]
sigma_pj = 200 * 10 ** (-6)  # Jitter RMS [rad]          #Has to be within receiver range
fs = 3e14
fc = 1e14  # dependend on system?

# Environment
z = 50  # Optical path length [m]
n = 1  # Air refractive index [-]

# Receiver
p_0 = 0.1  # Outage probability [-]
snr = 5  # Signal-to-noise ratio [dB]
L_c = 0.5

# Link budget calculation
optical_link = lb(
    Tx_power=80e-3,  # Laser transmitter power (W)
    T_atmos=0.5,  # Atmospheric transmission factor
    theta_div=10e-6,  # Beam divergence angle (radians)
    sigma_pj=2e-6,  # Pointing jitter (radians)
    # Modulator, L1, M1, BS1, M3, BS1, M2, BS2, M4, L3
    optics_array=[0.125, 0.95, 0.96, 0.5, 0.96, 0.96, 0.95],  # Optical efficiency (7 steps)
    Dr=3e-3,  # 3 cm receiver aperture
    wave=1.55e-6,  # Wavelength
    L=50,  # Distance
    temp=20,  # Temperature in Celsius
    r=2e-5,  # Static pointing error radius, based on div
    p_out=0.01,  # Scintillation outage probability
    sigma_i=0.45,  # Scintillation index
    r0=0.02,  # Fried parameter
    eta_rx=0.7,  # Receiver efficiency
    Rx_treshold=1e-6,
    n_nom=0.8,
    omit=True,
    attenuator=-10  # receiver attenuation in dB
)

print(f'Our design example: with assumptions on efficiency and atmospheric losses for up or downlink')
link_budget = optical_link.compute_link_budget()
for key in link_budget.keys():
    print(f"{key}: {link_budget[key]:.4f}")

# Losses
L_c = 10 ** ((link_budget["Total losses [dB]"] - link_budget[
    "Pointing jitter loss [dB]"]) / 10)  # Constant loss: all link budget losses except for (jitter-induced) scintillation [dB]
print(L_c)

#####=- Calculations -=#####
if random == False:
    np.random.seed(0)

# Generate PRBS transmitter signal
n_bits = bitrate * t_end
tx_bits = gen_prbs(n_bits)  # PRBS generator
tx_signal = np.multiply(np.repeat(tx_bits, R_f), P_l)  # Transmitted signal
t = np.linspace(0, t_end, len(tx_signal))  # Time steps

# Attenuate signal: include losses
# Pointing jitter loss [dB]
array = sample_xy(sigma_pj, z, len(t))
array_f = butt_filt(fs, fc, array[0], array[1])
L_pj = intensity_function(array_f[0], array_f[1])
L_tot = db_2_lin(L_c) * L_pj  # Total loss [-]
tx_signal_loss = L_tot * tx_signal
print(L_pj)

# Add Gaussian noise (AWGN)
awgn = gen_awgn(tx_signal_loss, snr)
rx_signal = (tx_signal_loss + awgn)

# Apply on-off keying
#rx_mean = []
#for i in range(0, len(tx_signal), R_f):
#    rx_mean.append(np.mean(rx_signal[i:(i + R_f)]))
#
#threshold = np.mean(rx_mean)
#rx_bits = (rx_mean > threshold).astype(int)
#bit_errors = np.sum(tx_bits != rx_bits)
#BER = bit_errors / n_bits
#print("BER: " + str(BER))

threshold = np.mean(rx_signal[::R_f])
rx_bits = (rx_signal[::R_f] > threshold).astype(int)
bit_errors = np.sum(tx_bits != rx_bits)
BER = bit_errors / n_bits
print("BER: " + str(BER))


#####=- Plotter -=#####
# Create figure for plots
plt.figure(figsize=(12, 9))

# Plot 1: Received signals
plt.subplot(3, 1, 1)
plt.step(t, tx_signal_loss, where='post', label="Attenuated signal", linewidth=2, alpha=0.7)
plt.step(t, rx_signal, where='post', label="Noisy signal: SNR = "+str(snr)+" dB", linewidth=1, alpha=0.7)
#plt.plot(t, rx_signal, label="Noisy signal", linewidth=1, alpha=0.7)
plt.scatter(t[::R_f], rx_signal[::R_f], label="Receiver sampling", s=15)
plt.step(t, np.repeat(rx_signal[::R_f], R_f), where='post', label="Received signal", linewidth=2, alpha=0.7)
plt.axhline(threshold, color='r', linestyle='dashed', label="Decision Threshold = "+str(round(threshold,4)))
plt.xlabel("Time [s]")
plt.ylabel("Power [W]")
plt.title("Attenuated, noisy and received signals")
plt.grid(True)
plt.legend()

# Plot 2: Transmitted and received binary signals
plt.subplot(3, 1, 2)
plt.step(t, np.repeat(tx_bits, R_f), where='post', label="Transmitted binary signal", linewidth=3, alpha=0.7)
plt.step(t, np.repeat(rx_bits, R_f), where='post', label="Received binary signal", linewidth=3, alpha=0.7)
plt.xlabel("Time [s]")
plt.ylabel("Voltage [V]")
plt.title("Transmitted and received binary signals: bitrate = "+str(bitrate)+str(" bps")+", BER = "+str(BER))
plt.grid(True)
plt.legend()

# Plot 3: Histogram of received signal
plt.subplot(3, 1, 3)
plt.hist(rx_signal[::R_f], bins=10, density=True, alpha=0.6, color='b', edgecolor='black')
plt.axvline(threshold, color='r', linestyle='dashed', label="Decision Threshold = "+str(round(threshold,4)))
plt.xlabel("Power [W]")
plt.ylabel("Probability density [-]")
plt.title("Histogram of received power")
plt.legend()
plt.grid(True)

# Show all plots
plt.tight_layout()
plt.show()

