import FreeSimpleGUI as sg
import serial.tools.list_ports
import threading
import numpy as np
import time

# Decrease this to make the FSM movement smoother
update_time = 0.0005

ports = serial.tools.list_ports.comports()
portList = [port.name for port in ports]

fsmPort = None

#TODO:implement data logging
logging = False


def sendDAC(d, channel, mode):
    """Function to send the data packets"""
    global fsmPort
    if fsmPort:
        packet = bytearray(3)
        packet[2] = (d & 0xFF) | 0b10000000
        packet[1] = ((d >> 7) & 0xFF) | 0b10000000
        packet[0] = (d >> 14) & 0x03
        packet[0] |= (channel << 4)
        packet[0] |= (mode << 2)
        fsmPort.write(packet)

sg.theme('DarkAmber')

# What is displayed in the GUI
windowLayout = [
    [sg.Text('X Frequency (Hz):'), sg.InputText('1', key='freq_x', size=(5,1)), sg.Text('Amplitude:'), sg.InputText('1', key='amp_x', size=(5,1)), sg.Button('Start X Sine'), sg.Button('Stop X Sine')],
    [sg.Text('Y Frequency (Hz):'), sg.InputText('1', key='freq_y', size=(5,1)), sg.Text('Amplitude:'), sg.InputText('1', key='amp_y', size=(5,1)), sg.Button('Start Y Sine'), sg.Button('Stop Y Sine')],
]

window = sg.Window('FSM DIM - GUI', windowLayout, finalize=True)


# Reading the ports. In my pc the usb port is listed as the last one hence portList[-1]. However this can be changed
try:
    if portList:
        fsmPort = serial.Serial(portList[-1], 460800, timeout=0)
        sendDAC(0x7FFF, 0, 1)
    else:
        sg.popup("No available FSM port detected!")
        fsmPort = None
except IndexError:
    sg.popup("No available FSM port detected!")
    fsmPort = None

running_x = False
running_y = False


def sine_wave_control_x():
    """This is the control function for the sine wave in x"""
    global running_x
    t = 0
    # TODO: implement offset / phase shift
    offset = 0x7FFF

    while running_x:
        try:
            freq_x = float(values['freq_x'])
        except ValueError:
            freq_x = 1
        try:
            amp_x = float(values['amp_x'])
            amp_x = max(0, min(1, amp_x))  # Ensure within range 0 to 1
        except ValueError:
            amp_x = 1
        
        amplitude_x = int(0x7FFF * amp_x)
        sine_value_x = int(offset + amplitude_x * np.sin(2 * np.pi * freq_x * t))
        sine_value_x = max(0, min(0xFFFF, sine_value_x))
        sendDAC(sine_value_x, 0, 1)

        time.sleep(update_time)
        t += update_time

def sine_wave_control_y():
    """This is the control function for the sine wave in y"""
    global running_y
    t = 0
    offset = 0x7FFF
    # TODO: implement offset / phase shift

    while running_y:
        try:
            freq_y = float(values['freq_y'])
        except ValueError:
            freq_y = 1
        try:
            amp_y = float(values['amp_y'])
            amp_y = max(0, min(1, amp_y))  # Ensure within range 0 to 1
        except ValueError:
            amp_y = 1
        
        amplitude_y = int(0x7FFF * amp_y)
        sine_value_y = int(offset + amplitude_y * np.sin(2 * np.pi * freq_y * t))
        sine_value_y = max(0, min(0xFFFF, sine_value_y))
        sendDAC(sine_value_y, 1, 1)

        time.sleep(update_time)
        t += update_time

def start_sine_x():
    """Start button for sine x"""
    global running_x
    if not running_x:
        running_x = True
        threading.Thread(target=sine_wave_control_x, daemon=True).start()

def stop_sine_x():
    """Stop button for sine x"""
    global running_x
    running_x = False

def start_sine_y():
    """Start button for sine y"""
    global running_y
    if not running_y:
        running_y = True
        threading.Thread(target=sine_wave_control_y, daemon=True).start()

def stop_sine_y():
    """Stop button for sine y"""
    global running_y
    running_y = False


# This is the main loop
while True:
    event, values = window.read(timeout=10)
    if event == sg.WIN_CLOSED:
        break
    if event == 'Start X Sine':
        start_sine_x()
    if event == 'Stop X Sine':
        stop_sine_x()
    if event == 'Start Y Sine':
        start_sine_y()
    if event == 'Stop Y Sine':
        stop_sine_y()
    if event == 'coarse':
        valueCoarse = int(values['coarse'])
        sendDAC(valueCoarse, 0, 1)

window.close()
if fsmPort:
    fsmPort.close()
