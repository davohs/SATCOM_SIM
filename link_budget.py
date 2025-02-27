import numpy as np
import matplotlib.pyplot as plt
import scipy as sc

class OpticalLinkBudget:
    def __init__(self, 
                 Tx_power, 
                 T_atmos, 
                 theta_div, 
                 sigma_pj, 
                 optics_array, 
                 Dr, 
                 wave, 
                 L, 
                 temp, 
                 r, 
                 p0, 
                 p_out, 
                 sigma_i, 
                 r0, 
                 eta_rx):
        self.Tx_power = Tx_power  # Laser power in W
        self.T_atmos = T_atmos  # Atmospheric transmission factor
        self.theta_div = theta_div  # Beam divergence angle (radians)
        self.sigma_pj = sigma_pj  # Pointing jitter (radians)
        self.optics_array = optics_array  # Optical efficiency
        self.Dr = Dr  # Receiver diameter (m)   
        self.wave = wave  # Wavelength (m)
        self.L = L  # Distance Tx to Rx (m)
        self.temp = temp  # Temperature in Celsius
        self.r = r  # Static pointing error radius (m)
        self.p0 = p0  # Initial pointing probability
        self.p_out = p_out  # Scintillation outage probability
        self.sigma_i = sigma_i  # Scintillation index
        self.r0 = r0  # Fried parameter (coherence length)
        self.D_spot = self.L * self.theta_div # Beam spot size (m)
        self.eta_rx = eta_rx # reciever efficiency

    @property
    def tx_gain(self):
        """Transmitter Gain"""
        G_tx = 8 / (self.theta_div ** 2)
        return 10 * np.log10(G_tx)

    @property
    def rx_gain(self):
        """Receiver Gain"""
        return 10 * np.log10(self.eta_rx*((np.pi * self.Dr) / self.wave) ** 2)

    @property
    def free_space_loss(self):
        """Free space loss using the correct Friis equation"""
        L_fs = (4 * np.pi * self.L / self.wave) ** 2
        return -np.abs(10 * np.log10(L_fs))

    @property
    def total_optics_loss(self):
        """Optical Loss"""
        optics_loss = np.prod(self.optics_array)
        return -np.abs(10 * np.log10(optics_loss))

    @property
    def static_pointing_loss(self):
        """Static Pointing Loss"""
        theta_pe = self.r / self.L
        T_pe = np.exp((-2 * theta_pe ** 2) / self.theta_div**2) 
        T_pe = max(T_pe, 1e-6) # it was throwing inf errors without this
        return -np.abs(10 * np.log10(T_pe))

    @property
    def jitter_loss(self):
        """Jitter Loss"""
        return -np.abs(10 * np.log10(self.theta_div**2 / (self.theta_div**2 + 4 * self.sigma_pj**2) * self.p_out ** ((4 * self.sigma_pj ** 2)/(self.theta_div ** 2))))

    @property
    def beam_spread_loss(self):
        """Beam Spread Loss"""
        return -np.abs(10 * np.log10((1 + (self.D_spot / self.r0) ** (5/3)) ** (-5/6)))

    @property
    def wavefront_loss(self):
        """Wavefront Loss"""
        return -np.abs(10 * np.log10((1 + (self.D_spot / self.r0) ** (5/3)) ** (-5/6)))

    @property
    def scintillation_loss(self):
        """Scintillation Loss"""
        p_out = max(self.p_out, 1e-6)  # Prevent log(0) errors
        return -np.abs((3.3 - 5.77 * np.sqrt(-np.log(p_out))) * self.sigma_i ** (4/5))
    
    @property
    def atmos_loss(self):
        """Atmospheric Loss"""
        return -np.abs(10 * np.log10(self.T_atmos))

    def compute_link_budget(self):
        """Computes the full optical link budget"""

        Gtx = self.tx_gain
        # Gtx = 0
        Grx = self.rx_gain
        # Grx = 0
        optics_loss = self.total_optics_loss
        Lfs = self.free_space_loss
        atmos_loss = self.atmos_loss
        L_static = self.static_pointing_loss
        L_jitter = self.jitter_loss
        L_scint = self.scintillation_loss
        L_spread = self.beam_spread_loss
        L_wave = self.wavefront_loss

        total_losses = optics_loss + Lfs + atmos_loss + L_static + L_jitter + L_scint + L_spread + L_wave
        total_gain = Gtx + Grx

        P_tx_db = 10 * np.log10(self.Tx_power)
        P_rx_db = P_tx_db + total_gain + total_losses
        P_rx = 10 ** (P_rx_db / 10)

        sigma2_thermal = 1.38e-23 * (273.15 + self.temp) / 50  # Thermal noise
        I_d = P_rx / (1.6e-19 * 0.99)  # Assume quantum efficiency of 0.99
        sigma2_shot = 2 * 1.6e-19 * I_d  # Shot noise
        sigma2 = sigma2_thermal + sigma2_shot  # Total noise power
        snr = P_rx /sigma2
        snr_db = 10 * np.log10(snr)

        return {
            "L": self.L,
            "Wavelength (μm)": self.wave*10**6,
            "P_rx (W)": P_rx,
            "P_rx (dB)": P_rx_db,
            "Noise Total (W)": sigma2,
            "SNR": snr,
            "SNR (dB)": snr_db
        }



# # From lecture slides (works):
optical_link = OpticalLinkBudget(
    Tx_power=2.5e-3,  # Laser transmitter power (W)
    T_atmos=1, # Atmospheric transmission factor
    theta_div=10e-6,  # Beam divergence angle (radians)
    sigma_pj=0.5e-6,  # Pointing jitter (radians)
    optics_array=[0.999] * 12, # Optical efficiency (12 steps)
    Dr=0.03,  # 3 cm receiver aperture (TBR)
    wave=1.55e-6,  # 1.55 μm wavelength (m)
    L=1,  # Distance Tx to Rx (meters)
    temp=20,  # Temperature in Celsius
    r=0.20,  # Static pointing error radius
    p0=0.001,  # Initial pointing probability
    p_out=0.01,  # Scintillation outage probability
    sigma_i=1,  # Scintillation index
    r0=1,  # Fried parameter
    eta_rx = 0.7 # Reciever efficiency
)


link_budget = optical_link.compute_link_budget()
for key in link_budget.keys():
    print(f"{key}: {link_budget[key]:.4f}")
# Define parameter variation
wavelength_values = np.linspace(0.8e-6, 1.6e-6, 50)  # Wavelength range from 0.8µm to 1.6µm
L_values = np.linspace(10, 50000, 5)  # Distance from 10m to 50m

# Initialize the OpticalLinkBudget object once
optical_link = OpticalLinkBudget(
    Tx_power=2.5e-3,  # Laser transmitter power (W)
    T_atmos=1,  # Atmospheric transmission factor
    theta_div=10e-6,  # Beam divergence angle (radians)
    sigma_pj=0.5e-6,  # Pointing jitter (radians)
    optics_array=[0.999] * 12,  # Optical efficiency (12 steps)
    Dr=0.03,  # 3 cm receiver aperture
    wave=1.55e-6,  # Placeholder wavelength (will be updated)
    L=1,  # Placeholder distance (will be updated)
    temp=20,  # Temperature in Celsius
    r=0.20,  # Static pointing error radius
    p0=0.001,  # Initial pointing probability
    p_out=0.01,  # Scintillation outage probability
    sigma_i=1,  # Scintillation index
    r0=1,  # Fried parameter
    eta_rx=0.7  # Receiver efficiency
)

# Dictionary to store SNR values for each distance
snr_results = {}

# Iterate over different distances
for L in L_values:
    optical_link.L = L  # Update the distance parameter
    snr_vals = []

    # Iterate over different wavelengths
    for wave in wavelength_values:
        optical_link.wave = wave  # Update the wavelength parameter
        
        # Compute the link budget and get the SNR (dB)
        link_budget = optical_link.compute_link_budget()
        snr_vals.append(link_budget["SNR (dB)"])

        # Print intermediate results for debugging
        print(f"Distance: {L} m, Wavelength: {wave*1e6} µm, SNR (dB): {link_budget["SNR (dB)"]}", link_budget["P_rx (W)"], link_budget["Noise Total (W)"])
    
    # Store results for this distance
    snr_results[L] = snr_vals

# Plot the results
plt.figure(figsize=(8, 6))
for L, snr_values in snr_results.items():
    plt.plot(wavelength_values * 1e6, snr_values, marker='o', linestyle='-', label=f'L = {L} m')

plt.xlabel("Wavelength (µm)")
plt.ylabel("SNR (dB)")
plt.title("SNR vs. Wavelength for Different Distances")
plt.legend()
plt.grid(True)
plt.show()
