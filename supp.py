import numpy as np
import matplotlib.pyplot as plt

x_f = 0.3
y_f = 0.7
lam = 1550 * 10**(-9)  # [m]
theta_div = 20 * 10**(-6)  # [rad]
n = 1   # [-]




def calc_coords(mean, std, la):
    theta_x = np.random.normal(mean, std)
    theta_y = np.random.normal(mean, std)
    x = np.tan(theta_x) * la
    y = np.tan(theta_y) * la
    return x, y

def filter_coords(x,y):
    return x_f, y_f

def calc_jit_loss(x_f, y_f, lam, theta_div, n):
    r = np.sqrt(x_f*2 + y_f*2)
    w_0 = lam / (theta_div * np.pi * n)
    z_R = np.pi * w_0**2 * n / lam
    w = w_0 * np.sqrt(1 + (z / z_R)**2)
    L_pj = (w_0 / w)*2 * np.exp(-2 * r2 / w*2)
    return L_pj

x, y = calc_coords(mean, std, la)
x_f, y_f = filter_coords(x, y)
L_pj = calc_jit_loss(x_f, y_f, lam, theta_div, n)
