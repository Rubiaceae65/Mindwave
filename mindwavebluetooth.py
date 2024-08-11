import os
import time
import select
import struct
import datetime
import threading

import pprint
pp = pprint.PrettyPrinter(indent=4)
import bluetooth
import socket

#SAMPLING_RATE = 512
##################
# command byte
##################

# modes lowest four bits
#ATTENTION_OUTPUT = 1
#MEDITATION_OUTPUT = 2
#RAW_OUTPUT = 4
# set for 57.6k, unset for 9600 baud
#BAUD_RATE = 8
###########################
# command bytes, upper four

SEND_BYTE = b'\x0b'

###################
# single Byte codes
###################

POOR_SIGNAL =           b'\x02'
HEART_RATE  =           b'\x03'
ATTENTION =             b'\x04'
MEDITATION =            b'\x05'
#8BIT_RAW =              b'\x06'
RAW_MARKER =            b'\x07'

#########################################
# multi byte codes, extended code level 0
##########################################

# raw wave value, 2 bytes, single big-endian 16-bit two's compliment signed value
#RAW_Wave_Value =        b'\x80'
RAW_VALUE =             b'\x80'

# eeg_power, 32 bytes, eign big-endian 4-byte ieee 754
EEG_POWER_VALUES =       ('delta', 'theta', 'low-alpha', 'hight-alpha', 'low-beta', 'high-beta', 'low-gamma', 'mid-gamma')
EEG_POWER =             b'\x81'

# asic eeg power, 24 bytes, 8 big endian 3-byte unsigned int
ASIC_EEG_POWER_VALUES =        ('delta', 'theta', 'low-alpha', 'hight-alpha', 'low-beta', 'high-beta', 'low-gamma', 'mid-gamma')
ASIC_EEG_POWER =        b'\x83'

# rrinterval, two byt big-endian unsigned int representing the milliseconds between two R-peaks
RRINTERVAL = b'\x86'

#################################################
CONNECT =               b'\xc0'
DISCONNECT =            b'\xc1'
AUTOCONNECT =           b'\xc2'
SYNC =                  b'\xaa'
EXCODE =                b'\x55'

BLINK =                 b'\x16'
HEADSET_CONNECTED =     b'\xd0'
HEADSET_NOT_FOUND =     b'\xd1'
HEADSET_DISCONNECTED =  b'\xd2'
REQUEST_DENIED =        b'\xd3'
STANDBY_SCAN =          b'\xd4'


#\x00e\x18

# [sync] [sync] [plength] [payload] [chksum]
# 1b     1b     1b        max 169b  1b
# \xaa   \xaa   \x04      \x80\x02\x00k\x12
#\xaa\xaa       \x04\x80\x02\x00a\x1c
#\xaa\xaa\x04\x80\x02\x00I4
#\xaa\xaa\x04\x80\x02\x00<A
#\xaa\xaa\x04\x80\x02\x00R+
#\xaa\xaa\x04\x80\x02\x00`\x1d
#\xaa\xaa\x04\x80\x02\x00H5
#\xaa\xaa\x04\x80\x02\x003J
#\xaa\xaa\x04\x80\x02\x003J
#\xaa\xaa\x04\x80\x02\x002K\xaa\xaa\x04\x80\x02\x00\'V\xaa\xaa\x04\x80\x02\x00\'V\xaa\xaa\x04\x80\x02\x00&W\xaa\xaa\x04\x80\x02\x008E\xaa\xaa\x04\x80\x02\x00U(\xaa\xaa\x04\x80\x02\x00h\x15\xaa\xaa\x04\x80\x02\x00q\x0c\xaa\xaa\x04\x80\x02\x00V\'\xaa\xaa\x04\x80\x02\x00%X\xaa\xaa\x04\x80\x02\x00\x06w\xaa\xaa\x04\x80\x02\x00\x17f\xaa\xaa\x04\x80\x02\x00\'V\xaa\xaa\x04\x80\x02\x00\x14i\xaa\xaa\x04\x80\x02\x00\x15h\xaa\xaa\x04\x80\x02\x004I\xaa\xaa\x04\x80\x02\x00R+\xaa\xaa\x04\x80\x02\x00R+\xaa\xaa\x04\x80\x02\x000M\xaa\xaa\x04\x80\x02\x00\x13j\xaa\xaa\x04\x80\x02\x00\x17f\xaa\xaa\x04\x80\x02\x00"[\xaa\xaa\x04\x80\x02\x00(U\xaa\xaa\x04\x80\x02\x00|\x01\xaa\xaa\x04\x80\x02\x00\xb9\xc4\xaa\xaa\x04\x80\x02\x00\x9b\xe2\xaa\xaa\x04\x80\x02\x00V\'\xaa\xaa\x04\x80\x02\x00\x1ca\xaa\xaa\x04\x80\x02\x00(U\xaa\xaa\x04\x80\x02\x00\\!\xaa\xaa\x04\x80\x02\x00m\x10\xaa\xaa\x04\x80\x02\x00T)\xaa\xaa\x04\x80\x02\x002K\xaa\xaa\x04\x80\x02\x00\x11l\xaa\xaa\x04\x80\x02\xff\xeb\x93\xaa\xaa

# DataRow
# (EXCODE]...) [CODE] ([VLENGTH]) [VALUE...]

# Status codes
STATUS_CONNECTED = 'connected'
STATUS_SCANNING = 'scanning'
STATUS_STANDBY = 'standby'


class Headset(object):
    """
    A MindWave Headset
    """
    class DongleListener(threading.Thread):
        """
        Serial listener for dongle device.
        """
        def __init__(self, headset, *args, **kwargs):
            """Set up the listener device."""
            self.headset = headset
            self.counter = 0
            self.valid_packet_counter = 0
            super(Headset.DongleListener, self).__init__(*args, **kwargs)


        def run(self):
            """Run the listener thread."""
            s = self.headset.dongle

            self.headset.running = True

            # Re-apply settings to ensure packet stream
            #s.write(DISCONNECT)
            #d = s.getSettingsDict()
            #for i in range(2):
            #    d['rtscts'] = not d['rtscts']
            #    s.applySettingsDict(d)

            while self.headset.running:
                # Begin listening for packets
                try:
                    if s.recv(1) == SYNC and s.recv(1) == SYNC:
                        # Packet found, determine plength
                        while True:
                            plength = int.from_bytes(s.recv(1), byteorder='big')
                            if plength != 170:
                                break
                        if plength > 170:
                            continue

                        # Read in the payload
                        payload = s.recv(plength)

                        # Verify its checksum
                        val = sum(b for b in payload[:-1])
                        val &= 0xff
                        val = ~val & 0xff
                        chksum = int.from_bytes(s.recv(1), byteorder='big')

                        #if val == chksum:
                        if True:  # ignore bad checksums
                            self.valid_packet_counter += 1
                            #print('valid packet nr: ' + str(self.valid_packet_counter))
                            if self.valid_packet_counter == 1:
                                # first valid packet, send command
                                s.send(SEND_BYTE)
                            self.parse_payload(payload)
                        else: 
                            print('invalid checksum' + str(payload))
                # FIXME
                except TimeoutError:
                    break
                #except serial.SerialException:
                #    break
                #except (select.error, OSError):
                #    break

            print('Closing connection...')
            if s and s.isOpen():
                s.close()

        def parse_payload(self, payload):
            """Parse the payload to determine an action."""
            while payload:
                # Parse data row
                excode = 0
                try:
                    code, payload = payload[0], payload[1:]
                    code_char = struct.pack('B',code)
                    self.headset.count = self.counter
                    self.counter = self.counter + 1
                    if (self.counter >= 100):
                        self.counter = 0
                except IndexError:
                    pass
                while code_char == EXCODE:
                    print('Excode bytes found')
                    # Count excode bytes
                    excode += 1
                    try:
                        code, payload = payload[0], payload[1:]
                    except IndexError:
                        pass
                if code < 0x80:
                    # This is a single-byte code
                    try:
                        value, payload = payload[0], payload[1:]
                    except IndexError:
                        print('indexerror, single-byte-code')
                        value = 0
                        payload = 0
                        pass
                    print('got single byte code: ' + str(code))
                    if code_char == POOR_SIGNAL:
                        # Poor signal
                        old_poor_signal = self.headset.poor_signal
                        self.headset.poor_signal = value
                        if self.headset.poor_signal > 0:
                            if old_poor_signal == 0:
                                for handler in self.headset.poor_signal_handlers:
                                    handler(self.headset,
                                            self.headset.poor_signal)
                        else:
                            if old_poor_signal > 0:
                                for handler in self.headset.good_signal_handlers:
                                    handler(self.headset,
                                            self.headset.poor_signal)
                    elif code_char == ATTENTION:
                        # Attention level
                        self.headset.attention = value
                        for handler in self.headset.attention_handlers:
                            handler(self.headset, self.headset.attention)
                    elif code_char == MEDITATION:
                        # Meditation level
                        self.headset.meditation = value
                        for handler in self.headset.meditation_handlers:
                            handler(self.headset, self.headset.meditation)
                    elif code_char == BLINK:
                        # Blink strength
                        self.headset.blink = value
                        for handler in self.headset.blink_handlers:
                            handler(self.headset, self.headset.blink)
                else:
                    # This is a multi-byte code
                    try:
                        vlength, payload = payload[0], payload[1:]
                    except IndexError:
                        continue
                    value, payload = payload[:vlength], payload[vlength:]
                    #print('got multi byte code_char: ' + str(code) )
                    if code_char == RAW_VALUE and len(value) >= 2:
                        raw = value[0]*256+value[1]
                        if (raw >= 32768):
                            raw = raw-65536
                        self.headset.raw_value = raw
                        print(str(raw), end=' ', flush=True)
                        for handler in self.headset.raw_value_handlers:
                            handler(self.headset, self.headset.raw_value)
                    if code_char == HEADSET_CONNECTED:
                        # Headset connect success
                        run_handlers = self.headset.status != STATUS_CONNECTED
                        self.headset.status = STATUS_CONNECTED
                        self.headset.headset_id = value.encode('hex')
                        if run_handlers:
                            for handler in self.headset.headset_connected_handlers:
                                handler(self.headset)
                    elif code_char == HEADSET_NOT_FOUND:
                        # Headset not found
                        if vlength > 0:
                            not_found_id = value.encode('hex')
                            for handler in self.headset.headset_notfound_handlers:
                                handler(self.headset, not_found_id)
                        else:
                            for handler in self.headset.headset_notfound_handlers:
                                handler(self.headset, None)
                    elif code_char == HEADSET_DISCONNECTED:
                        # Headset disconnected
                        headset_id = value.encode('hex')
                        for handler in self.headset.headset_disconnected_handlers:
                            handler(self.headset, headset_id)
                    elif code_char == REQUEST_DENIED:
                        # Request denied
                        for handler in self.headset.request_denied_handlers:
                            handler(self.headset)
                    elif code_char == STANDBY_SCAN:
                        # Standby/Scan mode
                        try:
                            byte = value[0]
                        except IndexError:
                            byte = None
                        if byte:
                            run_handlers = (self.headset.status != STATUS_SCANNING)
                            self.headset.status = STATUS_SCANNING
                            if run_handlers:
                                for handler in self.headset.scanning_handlers:
                                    handler(self.headset)
                        else:
                            run_handlers = (self.headset.status != STATUS_STANDBY)
                            self.headset.status = STATUS_STANDBY
                            if run_handlers:
                                for handler in self.headset.standby_handlers:
                                    handler(self.headset)
                    elif code_char == ASIC_EEG_POWER:
                        j = 0
                        for i in ['delta', 'theta', 'low-alpha', 'high-alpha', 'low-beta', 'high-beta', 'low-gamma', 'mid-gamma']:
                            try:
                                self.headset.waves[i] = value[j]*255*255+value[j+1]*255+value[j+2]
                            except IndexError:
                                print('IndexError for i: ' + str(i) + 'j: ' + str(j) )
                            print(str(self.headset.waves))
                            j += 3
                        for handler in self.headset.waves_handlers:
                            handler(self.headset, self.headset.waves)

    def __init__(self, device, headset_id=None, open_serial=True):
        """Initialize the headset."""
        # Initialize headset values
        self.dongle = None
        self.listener = None
        self.device = device
        self.headset_id = headset_id
        self.poor_signal = 255
        self.attention = 0
        self.meditation = 0
        self.blink = 0
        self.raw_value = 0
        self.waves = {}
        self.status = None
        self.count = 0
        self.running = False

        # Create event handler lists
        self.poor_signal_handlers = []
        self.good_signal_handlers = []
        self.attention_handlers = []
        self.meditation_handlers = []
        self.blink_handlers = []
        self.raw_value_handlers = []
        self.waves_handlers = []
        self.headset_connected_handlers = []
        self.headset_notfound_handlers = []
        self.headset_disconnected_handlers = []
        self.request_denied_handlers = []
        self.scanning_handlers = []
        self.standby_handlers = []

        # Open the socket
        if open_serial:
            self.bluetooth_open()
            print('bluetooth opened')

    def bluetooth_open(self):
        print("opening device")
        dongle_success = False
        while not dongle_success:
            if not self.dongle or not self.dongle.isOpen(): 
                print('scanning...')
                scan_results = bluetooth.discover_devices(lookup_names=True)
                for addr, name in scan_results:
                    #print(addr, name)
                    if name == "MyndBand":
                        print("eeg found: " + str(addr))
                        
                        services = bluetooth.find_service(address=addr)
                        if len(services) > 0:
                            print("found services")
                            for svc in services:
                                #print("---")
                                #print(svc)
                                if svc['protocol'] == 'RFCOMM':
                                    self.dongle = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                                    pp.pprint(self.dongle)
                                    self.dongle.connect((addr, svc["port"]))
                                    pp.pprint(self.dongle)
                                    try:
                                        self.dongle.setblocking(0)
                                        ready = select.select([self.dongle], [], [], 1)
                                        if ready[0]:
                                            firstdata = self.dongle.recv(1)
                                        else:
                                            print('firstdata timeout, thats the weird bug in the dongle, try sending something')
                                            self.dongle.send(SEND_BYTE)
                                            firstdata = '1'
                                        self.dongle.setblocking(1)


                                    except UnboundLocalError:
                                        dongle_success = False
                                    except TimeoutError:
                                        dongle_success = False
                                   
                                    if firstdata:
                                        pp.pprint(self.dongle)
                                        dongle_success = True
                                    print(firstdata)

                        else:
                            print("no services found, very weird")
        if not self.listener or not self.listener.isAlive():
            print('creating new listener')
            self.listener = self.DongleListener(self)
            self.listener.daemon = True
            self.listener.start()
        else:
            print('self.listener already exists, weird')



    def bluetooth_close():
        self.dongle.close()
    '''
    def serial_open(self):
        """Open the serial connection and begin listening for data."""
        if not self.dongle or not self.dongle.isOpen():
            self.dongle = serial.Serial(self.device, 115200)

        if not self.listener or not self.listener.isAlive():
            self.listener = self.DongleListener(self)
            self.listener.daemon = True
            self.listener.start()

    def serial_close(self):
        """Close the serial connection."""
        self.dongle.close()
    '''
    def stop(self):
        self.running = False
