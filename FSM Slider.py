import FreeSimpleGUI as sg
import serial.tools.list_ports

# Initialise variables
portSelected = False
ports = serial.tools.list_ports.comports()
portList = [port.name for port in ports]

logging = False  # Set to True to log data, avoid memory issues
fsmPort = None  # Define fsmPort globally

if logging:
    xs = []
    ys = []
    
else:
    class nop():
        def append(self, x):
            pass
    xs = nop()
    ys = nop()

def saveData():
    data_pairs = [("xs", xs), ("ys", ys)]
    for name, data in data_pairs:
        with open(name + ".txt", "w") as f:
            for item in data:
                f.write(f"{item[0]}, {item[1]}\n")

packetReady = False
byteNumber = 0
packet = bytearray(3)

r = [
    ["0", "X DAC", "?"],
    ["1", "Y DAC", "?"],
    ["2", "C DAC", "?"],
    ["3", "D DAC", "?"],
]

def updateR(d, channel, mode):
    r[channel][2] = d
    window['r'].update([r[0], r[1], r[2], r[3]])

def readByte():
    global byteNumber, packetReady, packet, fsmPort
    if fsmPort and fsmPort.inWaiting():
        b = ord(fsmPort.read(1))
        if byteNumber == 2:
            packet[2] = b
            packetReady = True
        if byteNumber == 1:
            packet[1] = b
            byteNumber = 2
        if byteNumber == 0:
            if (b & 0b10000000) == 0:
                packet[0] = b
                byteNumber = 1
        if packetReady:
            packetReady = False
            byteNumber = 0
            d = packet[0] & 0b00000011
            d = (d << 7) | (packet[1] & 0b01111111)
            d = (d << 7) | (packet[2] & 0b01111111)
            mode = (packet[0] >> 2) & 0b0000011
            channel = (packet[0] >> 4) & 0b00000111
            updateR(d, channel, mode)

def sendDAC(d, channel, mode):
    global fsmPort
    if fsmPort:
        packet[2] = (d & 0xFF) | 0b10000000
        packet[1] = ((d >> 7) & 0xFF) | 0b10000000
        packet[0] = (d >> 14) & 0x03
        packet[0] |= (channel << 4)
        packet[0] |= (mode << 2)
        fsmPort.write(packet)
        updateR(d, channel, mode)
        window['d'].update(d)
        window['c'].update(channel)
        window['m'].update(mode)

sg.theme('DarkAmber')
windowLayout = [
    [sg.Text('FSM DIM channels - received values', key='channel')],
    [sg.Table(r, ['Ch', 'Description', 'Value'], change_submits=True, num_rows=len(r), key='r')],
    [sg.Text('Slider is on DAC channel '), sg.Text('0', key='selectedDAC')],
    [sg.Slider(range=(0, 0xFFFF), default_value=0x7FFF, change_submits=True, orientation='h', key='coarse')],
    [sg.Slider(range=(-300, 300), default_value=0, change_submits=True, orientation='h', key='fine')],
    [sg.Button('EEPROM', key='EEPROM'), sg.Text('Set this position for next power-up')],
    [sg.Text('Last packet sent (data, channel, mode): '), sg.Text('?', key='d'), sg.Text('?', key='c'), sg.Text('?', key='m')],
]

window = sg.Window('FSM DIM - GUI', windowLayout, finalize=True)

try:
    if portList:
        fsmPort = serial.Serial(portList[-1], 460800)  # Select last available port
        sendDAC(0x7FFF, 0, 1)
        sendDAC(0x7FFF, 1, 1)
    else:
        sg.popup("No available FSM port detected!")
        fsmPort = None
except IndexError:
    sg.popup("No available FSM port detected!")
    fsmPort = None

valueCoarse = 0x7FFF
valueFine = 0
value = 0
DACn = 0

while True:
    event, values = window.read(timeout=10)
    if event == sg.WIN_CLOSED:
        break
    if event == 'r':
        if values['r'] != []:
            if values['r'][0] < 4:
                DACn = values['r'][0]
                window['selectedDAC'].update(str(DACn))
                window['coarse'].update(r[DACn][2])
                valueCoarse = r[DACn][2]
                window['fine'].update(0)
                valueFine = 0
    if event == 'coarse':
        valueCoarse = int(values['coarse'])
        window['fine'].update(0)
        value = valueCoarse
        sendDAC(value, DACn, 1)
    if event == 'fine':
        valueFine = int(values['fine'])
        if (valueCoarse + valueFine) > 0xFFFF:
            valueCoarse = 0xFFFF - valueFine
        if (valueCoarse + valueFine) < 0x0000:
            valueCoarse = 0x0000 + valueFine
        value = valueCoarse + valueFine
        window['coarse'].update(value)
        sendDAC(value, DACn, 1)
    if event == 'EEPROM':
        sendDAC(0, 7, 1)

window.close()
if fsmPort:
    fsmPort.close()
