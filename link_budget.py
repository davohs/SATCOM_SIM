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
                 p_out, 
                 sigma_i, 
                 r0, 
                 eta_rx,
                 Rx_treshold,
                 n_nom,
                 attenuator,
                 omit=False,
                 link="down",
                 ):
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
        self.p_out = p_out  # Scintillation outage probability
        self.sigma_i = sigma_i  # Scintillation index
        self.r0 = r0  # Fried parameter (coherence length)
        self.D_spot = self.L * self.theta_div # Beam spot size (m)
        self.eta_rx = eta_rx # reciever efficiency
        self.Rx_treshold = Rx_treshold # Receiver treshold in watt
        self.n_nom = n_nom # nominal coupling efficiency in wafefront error
        self.attenuator = attenuator # attenuator loss
        self.omit = omit # Omit atmospheric/turbulence induces losses
        self.link = link

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
        return -np.abs(10 * np.log10((1 + (self.D_spot / self.r0) ** (5/3)) ** (-5/6)) * self.n_nom)

    @property
    def wavefront_loss(self):
        """Wavefront Loss"""
        return -np.abs(10 * np.log10((1 + (self.D_spot / self.r0) ** (5/3)) ** (-5/6)) * self.n_nom)

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
        Grx = self.rx_gain
        optics_loss = self.total_optics_loss
        Lfs = self.free_space_loss
        atmos_loss = self.atmos_loss
        L_static = self.static_pointing_loss
        L_jitter = self.jitter_loss
        L_scint = self.scintillation_loss
        atten_loss = self.attenuator

        if self.link == "up":
            L_spread = self.beam_spread_loss
            L_wave = 0
        elif self.link == "down":
            L_spread = 0
            L_wave = self.wavefront_loss

        Rx_treshold_db = 10 * np.log10(self.Rx_treshold * 1000)

        total_gain = Gtx + Grx
        if self.omit == False:
            total_losses = optics_loss + Lfs + atmos_loss + L_static + L_jitter + L_scint + L_spread + L_wave + total_gain + atten_loss
        elif self.omit == True:
            L_scint, L_spread, L_wave = 0, 0, 0
            total_losses = optics_loss + Lfs + atmos_loss + L_static + L_jitter + L_scint + L_spread + L_wave + total_gain + atten_loss

        P_tx_db = 10 * np.log10(self.Tx_power * 1000)
        link_margin = total_losses + P_tx_db - Rx_treshold_db

        P_rx_db = P_tx_db + total_losses
        P_rx = (10 ** (P_rx_db / 10)) / 1000

        sigma2_thermal = 1.38e-23 * (273.15 + self.temp) / 50  # Thermal noise
        I_d = P_rx / (1.6e-19 * 0.99)  # Assume quantum efficiency of 0.99
        sigma2_shot = 2 * 1.6e-19 * I_d  # Shot noise
        sigma2 = sigma2_thermal + sigma2_shot  # Total noise power
        snr = P_rx /sigma2
        snr_db = 10 * np.log10(snr)

        return {
            "Transmit laser power [dBm]": P_tx_db,
            "Tx Antenna gain [dB]": Gtx,
            "Tx/Rx transmission loss [dB]": optics_loss,

            "Free space loss [dB]": Lfs,
            "Atmospheric loss [dB]": atmos_loss,
            
            "Systematic pointing loss [dB]": L_static,
            "Pointing jitter loss [dB]": L_jitter,
            "Scintillation loss [dB]": L_scint,
            "Beam Spread loss [dB]": L_spread,
            "Wavefront error loss [dB]": L_wave,
            
            "Rx Antenna gain [dB]": Grx,

            "Total losses [dB]": total_losses,
            "Link margin [dB]": link_margin,
            "Rx treshold [dBm]": Rx_treshold_db,
            "SNR (dB)": snr_db,
        }

# From lecture-17 slides - downlink budget:
optical_link = OpticalLinkBudget(
    Tx_power=1,  # Laser transmitter power (W)
    T_atmos=0.5, # Atmospheric transmission factor
    theta_div=20e-6,  # Beam divergence angle (radians)
    sigma_pj=1e-6,  # Pointing jitter (radians)
    optics_array=0.302, # Optical efficiency (12 steps)
    Dr=0.5,  # 3 cm receiver aperture (TBR)
    wave=1.55e-6,  # 1.55 μm wavelength (m)
    L=1000e3,  # Distance Tx to Rx (meters)
    temp=20,  # Temperature in Celsius
    r=10,  # Static pointing error radius (m)
    p_out=1e-3,  # Scintillation outage probability
    sigma_i=0.45,  # Scintillation index
    r0=0.2,  # Fried parameter
    eta_rx = 1, # Reciever efficiency
    Rx_treshold=1e-6, # Receiver Treshold
    n_nom=0.8, #nominal coupling efficiency as provided for wafefront error
    attenuator=0 #receiver attenuation in dB
)

print(f'Lecture example: within 2-4 db of example, with assumptions on efficiency and atmospheric losses for up or downlink')
link_budget = optical_link.compute_link_budget()
for key in link_budget.keys():
    print(f"{key}: {link_budget[key]:.4f}")

optical_link = OpticalLinkBudget(
    Tx_power=80e-3,  # Laser transmitter power (W)
    T_atmos=0.5,  # Atmospheric transmission factor
    theta_div=10e-6,  # Beam divergence angle (radians)
    sigma_pj=2e-6,  # Pointing jitter (radians)
    # Modulator, L1, M1, BS1, ND, M3, ND, BS1, M2, BS2, M4, L3 
    optics_array= [0.125, 0.95, 0.96, 0.5, 1.0, 0.96, 1.0, 0.5, 0.96, 0.5, 0.96, 0.95],  # Optical efficiency (12 steps)
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
    attenuator=-10 #receiver attenuation in dB
)

print(f'Our design example: with assumptions on efficiency and atmospheric losses for up or downlink')
link_budget = optical_link.compute_link_budget()
for key in link_budget.keys():
    print(f"{key}: {link_budget[key]:.4f}")

# # Define parameter variation
# wavelength_values = np.linspace(1.5e-6, 1.6e-6, 2)  # Wavelength range from 0.8µm to 1.6µm
# L_values = np.linspace(10, 50, 5)  # Distance from 10m to 50m

# # Dictionary to store SNR values for each distance
# snr_results = {}

# # Iterate over different distances
# for L in L_values:
#     optical_link.L = L  # Update the distance parameter
#     snr_vals = []

#     # Iterate over different wavelengths
#     for wave in wavelength_values:
#         optical_link.wave = wave  # Update the wavelength parameter
        
#         # Compute the link budget and get the SNR (dB)
#         link_budget = optical_link.compute_link_budget()
#         snr_vals.append(link_budget['SNR (dB)'])

#         # Print intermediate results for debugging
#         print(f"Distance: {L} m, Wavelength: {wave*1e6} µm, SNR (dB): {link_budget['SNR (dB)']}, {link_budget['P_rx (W)']}, {link_budget['Noise Total (W)']}")
    
#     # Store results for this distance
#     snr_results[L] = snr_vals

# #Plot the results
# plt.figure(figsize=(8, 6))
# for L, snr_values in snr_results.items():
#     plt.plot(wavelength_values * 1e6, snr_values, marker='o', linestyle='-', label=f'L = {L} m')

# plt.xlabel("Wavelength (µm)")
# plt.ylabel("SNR (dB)")
# plt.title("SNR vs. Wavelength for Different Distances")
# plt.legend()
# plt.grid(True)
# plt.show()
