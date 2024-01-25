#!/usr/bin/env python3
import subprocess

#	0C:61:CF:26:54:01	MyndBand
#{'service-classes': ['00001101-0000-1000-8000-00805F9B34FB'], 
# 'profiles': [('1101', 256)], 'name': 'Bluetooth Serial Port', 'description': None, 'provider': None, 'service-id': None, 'protocol': 'RFCOMM', 'port': 5, 'host': '0C:61:CF:26:54:01'}
#{'service-classes': ['1800'], 'profiles': [], 'name': None, 'description': None, 'provider': None, 'service-id': None, 'protocol': 'L2CAP', 'port': 31, 'host': '0C:61:CF:26:54:01'}
#{'service-classes': ['180A'], 'profiles': [], 'name': None, 'description': None, 'provider': None, 'service-id': None, 'protocol': 'L2CAP', 'port': 31, 'host': '0C:61:CF:26:54:01'}
#{'service-classes': ['039AFFF0-2C94-11E3-9E06-0002A5D5C51B'], 'profiles': [], 'name': None, 'description': None, 'provider': None, 'service-id': None, 'protocol': 'L2CAP', 'port': 31, 'host': '0C:61:CF:26:54:01'}
import pprint
pp = pprint.PrettyPrinter(indent=4)

import bluetooth
import socket
def getsocket(addr, port): 
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    s.connect((addr, port))
    #print(str(s.recv(1024)))
    return s

def scanbash():
    a = subprocess.Popen(["hcitool", "scan"], stdout = subprocess.PIPE).communicate()[0].split()[2:]
    if a == []:
        return "ERROR"
    else:
        return a

#scanbash()

def getservice():
    socket = None
    while socket is None:
        print("scanning...")
        scan_results = bluetooth.discover_devices(lookup_names=True)

        for addr, name in scan_results:
            print(addr, name)
            if name == "MyndBand":
                print("eeg found: " + str(addr))
                
                services = bluetooth.find_service(address=addr)
                if len(services) > 0:
                    print("found services")
                    for svc in services:
                        print("---")
                        print(svc)
                        if svc['protocol'] == 'RFCOMM':
                            socket = getsocket(addr, svc["port"])
                            return socket

                else:
                    print("no services found, very weird")

socket = getservice()

while True:
    pp.pprint(socket.read(1024))
    

