
import os
import time
from datetime import datetime


from digi.xbee.devices import DigiMeshDevice, RemoteXBeeDevice, XBeeDevice , ZigBeeDevice
from digi.xbee.io import IOLine
from digi.xbee.models.address import XBee64BitAddress
from digi.xbee.models.mode import APIOutputModeBit

os.system("sudo systemctl stop serial-getty@ttyS0.service")


# Instantiate an XBee device object
print ("starting")
device = ZigBeeDevice('/dev/ttyS0',9600)
print ("opening")

device.open()


try:

    
    print("Address = " + str(device.get_64bit_addr()))
    print("Hardware version = " + str(device.get_hardware_version()))
    print("Protocol is " + str(device.get_protocol()))
    #show node identification
    NI_param = device.get_parameter("NI")
    print("Node Identification is " + str(NI_param))
    
    # Show the XBee network
    zbnet = device.get_network()
    
    zbnet.start_discovery_process()
    while zbnet.is_discovery_running():
        time.sleep(0.5)

    # Get the list of the nodes in the network.
    print("Network is "+ str(zbnet))
 
    
    # Show API mode
    api_mode = device.get_api_output_mode_value()
    print("API Output Mode is "+ str(api_mode))
    device.set_api_output_mode_value(APIOutputModeBit.calculate_api_output_mode_value(device.get_protocol(), {APIOutputModeBit.EXPLICIT}))
    api_mode = device.get_api_output_mode_value()
    print("API Output Mode is "+ str(api_mode))

    for x in range(1000):
        try:
            xbee_message = device.read_expl_data(5)
            print("message = ")
            print(xbee_message)
            print(datetime.utcfromtimestamp(xbee_message.timestamp).strftime('%Y-%m-%d %H:%M:%S'))
            readoutA0 = xbee_message.data[4] << 8 | xbee_message.data[5]
            print(readoutA0)
            mvTempK = (readoutA0)
            tempK = (mvTempK)/10
            print(tempK)
  
            for x in xbee_message.data: 
                print(x)
                
        except Exception as e:
            print("error")
            print(e)
       
    
except Exception as e:

    print(e)

exit(0)


