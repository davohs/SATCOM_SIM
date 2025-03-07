# This program provides a test/calibration interface for the FSM Digial Interface Module (DIM)
# It allows setting the 4 DAC values with a slider, set EEPROM values, draw a full range square/bow-tie, and read and display the 4 sensor ADC inputs
# This program works best if the DIM is set to "Blue" feedback mode, where all setpoints from this Client to the DAC are feedback as confirmation
# That gives maximum transparency on whats going on and potential de-bugging if something is not working
# Refer to the DIM software for further operation option comments

# This GUI program is not aimed at getting maximum transmission speed. The GUI package and routines do not allow that
# Run the seperate speed test program instead for that which is bare bones and measure with an osciloscope.

# The 4 DAC's and 4 ADC's together make 8 analog 'channels'
# The DAC's are 16 bit with the output referenced to Vref, which is typically connetced to 5V Vcc
# The ADC's are 10 bit referenced to 5V Vcc. Their values are bit shifted 6x by the DIM so that the range matches that of the DAC's
# The ADC's measure the P1-P4 pins. Two options: 
#   - Install the jumpers so that these become X/Ypos and X/Yerr, but do NOT connect anything to the external pins
#   - Do not install the jumpers and connect some 0-5V signal on the external pins
# The 16 bit integer values are non-signed, hence 0 <-> 0V and 65535 <-> Vref/Vcc
# The 0-Vref DAC output is converted to -10V to +10V output to the FSM via an op-amp
# The -10V to +10V outut of the DIM for X/Ypos and X/Yerr is converted to 0-Vcc via a resistor network for the ADC inputs

# First the USB ports are scanned. Select the port that is connected to the DIM from the window that pops-up
#   - If there is only 1 port detected then the program assumes that is the port to use and the selection window closes automatically
# Make sure that the USB adaptor has:
#   - the 'U' jumper REMOVED
#   - the U-wire disconnected
#   - the TX,RX, and G wired to the DIM 'Main' port. The G wire is only necessary if the DIM is NOT powered via the USB as that would already connect the G

# This program needs the following software to run:
# Install Microsoft Visual Studio Code (VSC) from: https://visualstudio.microsoft.com/
# Install Python from https://www.python.org/downloads/windows/ ("download windows installer 32 bit", tick check box "Add Python to Path")
# Open the windows command prompt and type: "pip install pysimplegui" and "pip install time"


####   FreeSimpleGUI   is the new name for the pysimplegui as they closed the project and now your require a license for it.
####   Run "pip install FreeSimpleGUI" instead

#Communication protocol:

#Each channel needs 3 bytes to receive/transmit (1 data "packet"):
#- 1st: <0cccmmdd>, c=channel number, m=mode, d=data bit 15 and 14
#- 2nd: <1ddddddd>, d=data bit 13 to 7
#- 3rd: <1ddddddd>, d=data bit 0 to 6 
#Hence the packet synchronisation is done via the first byte with bit 7 = 0
#This protocal gives the highest possible data transfer rate.

#Channel number ccc:
#- 000=0: DAC out X,  16 bit, Vref
#- 001=1: DAC out Y,  16 bit, Vref
#- 010=2: DAC out 3,  External DAC C pin, 16 bit, Vref
#- 011=3: DAC out 4,  External DAC D pin, 16 bit, Vref
#- 100=4: ADC in  P1, jumper to X-pos otherwise external P1 pin, 10 bit, Vcc
#- 101=5: ADC in  P2, jumper to Y-pos otherwise external P2 pin, 10 bit, Vcc
#- 110=6: ADC in  P3, jumper to X-err otherwise external P3 pin, 10 bit, Vcc 
#- 111=7: ADC in  P4, jumper to Y-err otherwise external P4 pin, 10 bit, Vcc  

#Mode number mm:
#- 00=0: load DAC channel, do not yet update DAC output of this channel
#- 01=1: load DAC channel and update the DAC output of this channel
#- 10=2: load DAC channel and update the DAC output of ALL channels, this allows synchronous updates

#Commands to DIM:
#The DIM responds to additional command instructions when receiving packets addressed to channel 7, which is an non-existing DAC.
#The combination of received m and d values on channel define the instruction.
# There are currently only 2 instructions::
#  - m=0, d=irrelevant: Initialise the DIM to its power-up state.
#    - Set DAC's to their EEPROM values, send these to the Client, set the operation mode to "Green"
#  - m=1, d=irrelevant: Save the last setpoints of all 4 DACs to EEPROM for next power-up.
#    - This can be uselful if the FSM is in a fixed calibrated position related to lenses, etc. 
#    - Once calibrated it should then always power-up on that angle.

import FreeSimpleGUI as sg
import serial.tools.list_ports
import time

# initialise variables

portSelected=False
# create list of connected COM ports
ports=serial.tools.list_ports.comports()
portList=[]
for portScan in ports:
    print(portScan.name," : ",portScan)
    portList.append(portScan.name)

logging = False # set to True to log data, avoid memory issues

if logging:
    xs=[]
    ys=[]
    a0s=[]
    a1s=[]
    a2s=[]
    a3s=[]
    xpos_rels = []
    ypos_rels = []
else :
    class nop():
        def append(self, x):
            pass
    xs = nop()
    ys = nop()
    a0s = nop()
    a1s = nop()
    a2s = nop()
    a3s = nop()
    xpos_rels = nop()
    ypos_rels = nop()

def saveData():
    data_pairs = [("xs", xs), ("ys", ys), ("a0s", a0s), ("a1s", a1s), ("a2s", a2s), ("a3s", a3s), ("xpos_rels", xpos_rels), ("ypos_rels", ypos_rels)]
    for name, data in data_pairs:
        with open(name + ".txt", "w") as f:
            for item in data:
                f.write(f"{item[0]}, {item[1]}\n")


packetReady=False
byteNumber=0
packet=bytearray(3)

r=[
    ["0","X DAC","?"],
    ["1","Y DAC","?"],
    ["2","C DAC","?"],
    ["3","D DAC","?"],
    ["4","Xpos / P1 ADC","?"],
    ["5","Ypos / P2 ADC","?"],
    ["6","Xerr / P3 ADC","?"],
    ["7","Yerr / P4 ADC","?"],
    ["A0","Quad-Cell A0","?"],
    ["A1","Quad-Cell A1","?"],
    ["A2","Quad-Cell A2","?"],
    ["A3","Quad-Cell A3","?"],
    ["12", "XPOS requested", "?"],
    ["13", "YPOS requested", "?"],
    ]
def updateR(d,channel,mode):
    r[channel][2]=d
    window['r'].update([r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],r[9],r[10],r[11],r[12],r[13]])

t0 = time.time()

def readByte():
    global byteNumber
    global packetReady
    global packet
    while fsmPort.inWaiting(): 
        b=ord(fsmPort.read(1))
        #print (byteNumber,' ',bin(b))
        if byteNumber==2: 
            packet[2]=b
            packetReady=True
        if byteNumber==1: 
            packet[1]=b
            byteNumber=2
        if byteNumber==0: 
            if (b & 0b10000000)==0: 
                packet[0]=b
                byteNumber=1
        if packetReady: 
            packetReady=False
            byteNumber=0
            #print(bin(packet[0]),' ',bin(packet[1]),' ',bin(packet[2]))
            d=packet[0] & 0b00000011
            d=(d<<7)|(packet[1]&0b01111111)
            d=(d<<7)|(packet[2]&0b01111111)
            mode=(packet[0]>>2)&0b0000011
            channel=(packet[0]>>4)&0b00000111
            # print ('d=',d,' channel=',channel,' mode=',mode, ' time=', time.time()-t0)
            updateR(d,channel,mode)
            

def sendDAC(d,channel, mode):
    #print(d,' ',channel,' ',mode)
    packet[2]=(d & 0xFF)|0b10000000
    packet[1]=((d>>7) & 0xFF)|0b10000000
    packet[0]=(d>>14) & 0x03
    packet[0]|=(channel<<4)
    packet[0]|=(mode<<2)
    fsmPort.write(packet)
    #print (bin(packet[0]),' ',bin(packet[1]),' ',bin(packet[2]))
    updateR(d,channel,mode)
    window['d'].update(d)
    window['c'].update(channel)
    window['m'].update(mode)

drawOption=0 #0=direct, 1=square, 2=bow tie
drawStep=0
updateTarget=False
movesRemaining=False
moveTimer=time.time()
Xa=0
Ya=0

def moveToTarget(Xt,Yt):
    global r
    global movesRemaining
    global Xa
    global Ya   
    stepSize=0xFF
    moveX=False
    moveY=False
    if Xt!=Xa: moveX=True
    if Xt>Xa: Xa=Xa+min(stepSize,Xt-Xa)
    if Xt<Xa: Xa=Xa-min(stepSize,Xa-Xt)
    if Yt!=Ya: moveY=True
    if Yt>Ya: Ya=Ya+min(stepSize,Yt-Ya)
    if Yt<Ya: Ya=Ya-min(stepSize,Ya-Yt)
    if moveX and moveY: # synchronous update mode, sends 2 packets
        sendDAC(Xa,0,0)
        sendDAC(Ya,1,2)
    else:               # single channel update mode, sends 1 packet
        if moveX:sendDAC(Xa,0,1)
        if moveY:sendDAC(Ya,1,1)
    #print (Xa,' ',Ya)
    movesRemaining= moveX or moveY   # True means not yet on target

def initDraw(option):
    global drawOption
    global Xa
    global Ya
    drawOption=option
    Xa=0x7FFF
    Ya=0x7FFF


sg.theme('DarkAmber')   # Add a touch of color
# All the stuff inside your window.
fsmConnection=[[sg.Text('Select USB port for FSM', key='USB'), sg.Listbox(portList, change_submits=True, no_scrollbar=False,  s=(15,2), key='COM-FSM')]]
quadConnection=[[sg.Text('Select USB port for Quad-Cell', key='USB'), sg.Listbox(portList, change_submits=True, no_scrollbar=False,  s=(15,2), key='COM-QUAD')]]


# Create the Window
window = sg.Window('FSM connection', fsmConnection)

windowLayout=[
            [sg.Text('FSM DIM channels - received values', key='channel')],
            [sg.Button('Initialise', key='init'),     sg.Text('Initiliase DIM. This will load the EEPROM values to all 4 DACs, update Client with those, and set the DIM mode to "Green"')],
            [sg.Text('> Select DAC > Use slider to update it > DIM will feedback that value as confirmation only if its mode is set to "Blue"')],
            [sg.Table([r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7]], ['Ch','Description','Value'], change_submits=True, num_rows=len(r), key='r'),
             sg.Text('DAC is 16 bit on Vref - ADC is 10 bit on Vcc (shifted 6 bits to match DAC scale)')],
            [sg.Text('Slider is on DAC channel '), sg.Text('0', key='selectedDAC'), ],
            [sg.Slider(range=(0,0xFFFF), default_value=0x7FFF,  change_submits=True, orientation='h', s=(100,10), key='coarse'), sg.Text('Full scale'), ],
            [sg.Slider(range=(-300,300), default_value=0,  change_submits=True, orientation='h', s=(100,10), key='fine'), sg.Text('Fine tuning'), ],
            [sg.Button('Direct  ', key='direct'),   sg.Text('Direct, adjust channel with slider'), sg.Button('EEPROM', key='EEPROM'),   sg.Text('Set this position for next power-up'),],
            [sg.Button('Square', key='square'),     sg.Text('Draw full range, start in middle')],
            [sg.Button('Bow tie', key='bow'),       sg.Text('Draw full range, start in middle')],
            [sg.Button('Quad-Cell Steered', key='quad'), sg.Text('Read Quad-Cell and steer DACs')], 
            [sg.Button('Save Quad-Cell', key='save'), sg.Text('Save Quad-Cell readings')], 
            [sg.Text('Drawing functions: step size is 255 every 10 ms or 257 steps to cover a full range track')],
            [sg.Text('Sends 2 packets for synchronous X/Y DAC update in case both X and Y are updated, sends 1 packet if only 1 channel is updated')],
            [sg.Text('This is not maximum speed as the GUI does not allow that, run speed test program for that')],
            [sg.Text('Last packet sent (data, channel, mode): '), sg.Text('?', key='d'), sg.Text('?', key='c'), sg.Text('?', key='m')],
        ]

valueCoarse=0x7FFF
valueFine=0
value=0
DACn=0

def readQuadCell():
    try:
        while quadPort.inWaiting(): 
            msg = quadPort.readline().decode('ascii').strip()
            match msg[0:2]:
                case 'A0':
                    updateR(int(msg[3:]),8,0)
                    a0s.append((time.time()-t0, int(msg[3:])))
                case 'A1':
                    updateR(int(msg[3:]),9,0)
                    a1s.append((time.time()-t0, int(msg[3:])))
                case 'A2':
                    updateR(int(msg[3:]),10,0)
                    a2s.append((time.time()-t0, int(msg[3:])))
                case 'A3':
                    updateR(int(msg[3:]),11,0)
                    a3s.append((time.time()-t0, int(msg[3:])))
    except:
        pass


# Event Loop to process "events" and get the "values" of the inputs
while True:
    event, values = window.read(timeout=10) # 10 ms interval to check for new data coming in or to make drawing moves
    if event==sg.WIN_CLOSED: break
    if event=='COM-FSM' and not portSelected:
        fsmPort=serial.Serial(values['COM-FSM'][0],460800)
        print("Connected FSM to",values['COM-FSM'][0])
        window.close()
        window = sg.Window('QUAD-CELL connection', quadConnection)
        
    
    if event=='COM-QUAD' and not portSelected:
        portSelected=True
        quadPort=serial.Serial(values['COM-QUAD'][0], 1000000)
        print("Connected Quad-cell to",values['COM-QUAD'][0])
        window.close()
        window = sg.Window('FSM DIM - GUI', windowLayout, finalize=True)
        sendDAC(0x7FFF,0,1)
        sendDAC(0x7FFF,1,1)
        sendDAC(0x7FFF,2,1)
        sendDAC(0x7FFF,3,1)



    if portSelected: 
        readByte()
        readQuadCell()

    if event=='r': 
        if values['r']!=[]: 
            if values['r'][0]<4:
                DACn=values['r'][0]
                window['selectedDAC'].update(str(DACn)) 
                window['coarse'].update(r[DACn][2])
                valueCoarse=r[DACn][2]
                window['fine'].update(0)
                valueFine=0

    if event=='coarse': 
        valueCoarse=int(values['coarse'])
        window['fine'].update(0x00)
        value=valueCoarse
        updateTarget=True

    if event=='fine': 
        valueFine=int(values['fine'])
        if (valueCoarse+valueFine)>0xFFFF: valueCoarse=0xFFFF-valueFine
        if (valueCoarse+valueFine)<0x0000: valueCoarse=0x0000+valueFine
        value=valueCoarse+valueFine
        window['coarse'].update(value) 
        updateTarget=True

    if event=='direct'  : initDraw(0)
    if event=='square'  : initDraw(1)
    if event=='bow'     : initDraw(2)
    if event=='quad'    : 
        initDraw(3)
        xpos = 0x7FFF
        ypos = 0x7FFF

    if event=='init'    : sendDAC(0,7,0)    #this is a non-existing DAC, this channel is a command channel for the DIM
    if event=='EEPROM'  : sendDAC(0,7,1)    #this is a non-existing DAC, this channel is a command channel for the DIM
    if event=='save'    : saveData()

    if updateTarget and drawOption==0: 
        updateTarget=False
        sendDAC(value,DACn,1)

    if drawOption==1:
        if drawStep==0: moveToTarget(0,0)
        if drawStep==1: moveToTarget(0xFFFF,0)
        if drawStep==2: moveToTarget(0xFFFF,0xFFFF)
        if drawStep==3: moveToTarget(0,0xFFFF)
        if not movesRemaining: drawStep=(drawStep+1)%4

    if drawOption==2:
        if drawStep==0: moveToTarget(0,0)
        if drawStep==1: moveToTarget(0,0xFFFF)
        if drawStep==2: moveToTarget(0xFFFF,0)
        if drawStep==3: moveToTarget(0xFFFF,0xFFFF)
        if not movesRemaining: drawStep=(drawStep+1)%4

    if drawOption==3:
        PFACTOR = 500
        sum = r[8][2]+r[9][2]+r[10][2]+r[11][2]
        if(sum != 0):
            xpos_rel = (r[8][2]+r[9][2]-r[10][2]-r[11][2])/sum
            ypos_rel = (r[8][2]+r[10][2]-r[9][2]-r[11][2])/sum
            
            xpos_rels.append((time.time()-t0, xpos_rel))
            ypos_rels.append((time.time()-t0, ypos_rel))
            
            ypos = ypos - int(ypos_rel*PFACTOR)
            xpos = xpos - int(xpos_rel*PFACTOR)
            
            if xpos > 0xFFFF: xpos = 0xFFFF
            if xpos < 0: xpos = 0
            if ypos > 0xFFFF: ypos = 0xFFFF
            if ypos < 0: ypos = 0
            xs.append((time.time()-t0, xpos))
            ys.append((time.time()-t0, ypos))
            updateR(xpos,12,0)
            updateR(ypos,13,0)
            sendDAC(xpos,0,0)
            sendDAC(ypos,1,2)

window.close()


