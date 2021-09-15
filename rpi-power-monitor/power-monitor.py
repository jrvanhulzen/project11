#!/usr/bin/python
import time as timelib
import timeit
import csv
import sys
from datetime import datetime
from plotting import plot_data, webroot
import pickle
import os
from socket import socket, AF_INET, SOCK_DGRAM
import fcntl
from prettytable import PrettyTable
import logging
from config import logger, ct_phase_correction, ct4_channel, board_voltage_channel, v_sensor_channel, GRID_VOLTAGE, AC_TRANSFORMER_OUTPUT_VOLTAGE, accuracy_calibration 
from calibration import check_phasecal, rebuild_wave, find_phasecal
from textwrap import dedent
from common import collect_data, readadc, rebuild_waves, calculate_power, get_board_voltage
from shutil import copyfile

from digi.xbee.devices import DigiMeshDevice, RemoteXBeeDevice, XBeeDevice , ZigBeeDevice
from digi.xbee.io import IOLine
from digi.xbee.models.address import XBee64BitAddress
from digi.xbee.models.mode import APIOutputModeBit

os.system("sudo systemctl stop serial-getty@ttyS0.service")

def openDatafile(dataFilename):
    try:
        open(f"{webroot}/{dataFilename}.csv",'x')
        logger.info(f" file doesnt exist, Creating file {dataFilename}.csv in webroot of pi")
        with open(f"{webroot}/{dataFilename}.csv", 'w') as f:
            writer = csv.writer(f)
            headers = ["Date", "Time", "power", "current", "voltage", "power factor" , "Temp", "tempKoelkast"]
            writer.writerow(headers)
    except Exception as e:
        print(e)
        logger.info(f"{dataFilename}.csv exists in webroot, appending with new data.")
    f = open(f"{webroot}/{dataFilename}.csv",'a',1)
    return f

def run_main():
    logger.info("... Starting Raspberry Pi Power Monitor")
    logger.info("Press Ctrl-c to quit...")
    print ("opening zigbee device ")
    device = ZigBeeDevice('/dev/ttyS0',9600)
    try:
        device.open()
        print ("opened")
    except Exception as e:
        print(e)
        print ("failed to open Xbee")
    try:   
        print("Address = " + str(device.get_64bit_addr()))
        print("Hardware version = " + str(device.get_hardware_version()))
        print("Protocol is " + str(device.get_protocol()))
        #show node identification
        NI_param = device.get_parameter("NI")
        print("Node Identification is " + str(NI_param))

        '''      
        print("Discovering zigbee network")
        zbnet = device.get_network()
        zbnet.start_discovery_process()
        while zbnet.is_discovery_running():
            timelib.sleep(0.5)

        # Get the list of the nodes in the network.
        print("Network is "+ str(zbnet))
        
        nodes = zbnet.get_devices()
        #print(nodes[0].get_64bit_addr())
        print(str(nodes))
        print(zbnet.get_connections())
        '''
        api_mode = device.get_api_output_mode_value()
        print("API Output Mode is "+ str(api_mode))
        device.set_api_output_mode_value(APIOutputModeBit.calculate_api_output_mode_value(device.get_protocol(), {APIOutputModeBit.EXPLICIT}))
        api_mode = device.get_api_output_mode_value()
        print("API Output Mode is "+ str(api_mode))
    
        try:
            xbee_message = device.read_expl_data(5)
            print("message = ")
            print(xbee_message)
            print(datetime.utcfromtimestamp(xbee_message.timestamp).strftime('%Y-%m-%d %H:%M:%S'))
            readoutA0 = xbee_message.data[4] << 8 | xbee_message.data[5]
            print(readoutA0)
            mvTempK = (readoutA0)
            print(mvTempK)
            tempK = (mvTempK)/10
            print(tempK)
  
            for x in xbee_message.data: 
                print(x)
             
        except Exception as e:
            print("error")
            print(e)
            
    except Exception as e:
        print(e)
        print ("error in xbee network & status discovery")
    logger.info("Opening data file")
    csvWriter = csv.writer(openDatafile('data'))
    for i in range(6):
        csvWriter.writerow(['Starting new measurement ',0,0,0,0,0])
    # The following empty dictionaries will hold the respective calculated values at the end of each polling cycle, which are then averaged prior to storing the value to the DB.
    home_load_values = dict(power=[], pf=[], current=[])
    net_power_values = dict(power=[], current=[])

    ct4_dict = dict(power=[], pf=[], current=[])
    rms_voltages = []
    i = 0   # Counter for aggregate function
    
    # first sample collection and plot creation
    start = timeit.default_timer()
    samples = collect_data(1000)
    stop = timeit.default_timer()
    duration = stop - start

    # Calculate Sample Rate in Kilo-Samples Per Second.
    sample_count = sum([ len(samples[x]) for x in samples.keys() if type(samples[x]) == list ])
    
    print(f"sample count is {sample_count}")
    sample_rate = round((sample_count / duration) / 1000, 2)
    logger.debug(f"Finished Collecting Samples. Sample Rate: {sample_rate} KSPS")

    ct4_samples = samples['ct4']
    v_samples = samples['voltage']
    temp_samples = samples['pitemp']
    # Save samples to disk
    with open('data/samples/last-debug.pkl', 'wb') as f:
        pickle.dump(samples, f)
    title = "debug_plot"
    logger.debug("Building plot.")
    plot_data(samples, title, sample_rate=sample_rate)
    ip = get_ip()
    if ip:
        logger.info(f"Chart created! Visit http://{ip}/{title}.html to view the chart. Or, simply visit http://{ip} to view all the charts created using 'debug' and/or 'phase' mode.")
    else:
        logger.info("Chart created! I could not determine the IP address of this machine. Visit your device's IP address in a webrowser to view the list of charts you've created using 'debug' and/or 'phase' mode.")
        

    
    
    
    
    
    
    
    
    
    
    
    
    while True:        
        try:
            board_voltage = get_board_voltage()    
            samples = collect_data(2000)
            poll_time = datetime.now           

            ct4_samples = samples['ct4']
            v_samples = samples['voltage']
            rebuilt_waves = rebuild_waves(samples, ct_phase_correction['ct4'])
            results = calculate_power(rebuilt_waves, board_voltage) 

           # Prepare values for database storage 

            grid_4_power = results['ct4']['power']    # CT4 Real Power



            grid_4_current = results['ct4']['current']  # CT4 Current
   

            voltage = results['voltage']
            try:
                xbee_message = device.read_expl_data(0.5)
                print("message = ")
                print(xbee_message)
                print(datetime.utcfromtimestamp(xbee_message.timestamp).strftime('%Y-%m-%d %H:%M:%S'))
                readoutA0 = xbee_message.data[4] << 8 | xbee_message.data[5]
                print(readoutA0)
                mvTempK = (readoutA0)
                print(mvTempK)
                tempK = (mvTempK)/10
                print(tempK)
      
                #for x in xbee_message.data: 
                #    print(x)
            except Exception as e:
                print(e)            
                tempK=0
                
                                 
            date = datetime.now().strftime('%Y-%m-%d')
            time = datetime.now().strftime('%H:%M:%S')
            measurement= [date, time, round(results['ct4']['power'], 2), round(results['ct4']['current'], 2),round(results['voltage'], 2),round(results['ct4']['pf'], 2),round(results['pitemp'], 2),tempK]                       
            print(measurement)
            csvWriter.writerow(measurement)
            
            ct4_dict = dict(power=[], pf=[], current=[])
       
            rms_voltages = []
            i = 0
      
  
            if logger.handlers[0].level == 10:
                t = PrettyTable(['', 'Readouts'])
                t.add_row(['Watts', round(results['ct4']['power'],3)])
                t.add_row(['Current', round(results['ct4']['current'], 3)])
                t.add_row(['P.F.', round(results['ct4']['pf'], 3)])
                t.add_row(['Voltage', round(results['voltage'], 3)])
                t.add_row(['Temp power monitor', round(results['pitemp'], 3)])
                t.add_row(['Temp Koelkast', round(tempK, 3)])
                s = t.get_string()
                logger.debug('\n' + s)

            #sleep(0.1)
            
        except KeyboardInterrupt:

            sys.exit()

def print_results(results):
    t = PrettyTable(['', 'CT4'])
    t.add_row(['Watts',  round(results['ct4']['power'],3)])
    t.add_row(['Current', round(results['ct4']['current'],3)])
    t.add_row(['P.F.', round(results['ct4']['pf'], 3)])
    t.add_row(['Voltage', round(results['voltage'], 3), '', '', '', '', ''])
    s = t.get_string()
    logger.debug(s)


def get_ip():
    # This function acquires your Pi's local IP address for use in providing the user with a copy-able link to view the charts.
    # It does so by trying to connect to a non-existent private IP address, but in doing so, it is able to detect the IP address associated with the default route.
    s = socket(AF_INET, SOCK_DGRAM)
    try:
        s.connect(('10.25.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = None
    finally:
        s.close()
    return IP


if __name__ == '__main__':

    if len(sys.argv) > 1:
        MODE = sys.argv[1]
        if MODE == 'debug' or MODE == 'phase':
            try:
                title = sys.argv[2]
            except IndexError:
                title = None
        # Create the data/samples directory:
        try:
            os.makedirs('data/samples/')
        except FileExistsError:
            pass
    else:
        MODE = None

    if not MODE:
        logger.setLevel(logging.DEBUG)
        logger.handlers[0].setLevel(logging.DEBUG)      
        run_main()

    else:
        # Program launched in one of the non-main modes. Increase logging level.
        logger.setLevel(logging.DEBUG)
        logger.handlers[0].setLevel(logging.DEBUG)      
        if 'help' in MODE.lower() or '-h' in MODE.lower():

            logger.info("See the project Wiki for more detailed usage instructions: https://github.com/David00/rpi-power-monitor/wiki")
            logger.info(dedent("""Usage:
                Start the program:                                  python3 power-monitor.py

                Collect raw data and build an interactive plot:     python3 power-monitor.py debug "chart title here" 

                Launch interactive phase correction mode:           python3 power-monitor.py phase

                Start the program like normal, but print all        python3 power-monitor.py terminal
                readings to the terminal window
                """))
        if MODE.lower() == 'clearfiles':
            list( map( os.unlink, (os.path.join(f"{webroot}",f) for f in os.listdir(f"{webroot}")) ) )
            
            
        if MODE.lower() == 'debug':
            # This mode is intended to take a look at the raw CT sensor data.  It will take 2000 samples from each CT sensor, plot them to a single chart, write the chart to an HTML file located in /var/www/html/, and then terminate.
            # It also stores the samples to a file located in ./data/samples/last-debug.pkl so that the sample data can be read when this program is started in 'phase' mode.

            # Time sample collection
            start = timeit.default_timer()
            samples = collect_data(2000)
            stop = timeit.default_timer()
            duration = stop - start

            # Calculate Sample Rate in Kilo-Samples Per Second.
            sample_count = sum([ len(samples[x]) for x in samples.keys() if type(samples[x]) == list ])
            
            print(f"sample count is {sample_count}")
            sample_rate = round((sample_count / duration) / 1000, 2)

            logger.debug(f"Finished Collecting Samples. Sample Rate: {sample_rate} KSPS")

            ct4_samples = samples['ct4']
            v_samples = samples['voltage']
            temp_samples = samples['pitemp']
            # Save samples to disk
            with open('data/samples/last-debug.pkl', 'wb') as f:
                pickle.dump(samples, f)

            if not title:
                title = input("Enter the title for this chart: ")
            
            title = title.replace(" ","_")
            logger.debug("Building plot.")
            plot_data(samples, title, sample_rate=sample_rate)
            ip = get_ip()
            if ip:
                logger.info(f"Chart created! Visit http://{ip}/{title}.html to view the chart. Or, simply visit http://{ip} to view all the charts created using 'debug' and/or 'phase' mode.")
            else:
                logger.info("Chart created! I could not determine the IP address of this machine. Visit your device's IP address in a webrowser to view the list of charts you've created using 'debug' and/or 'phase' mode.")
                

        if MODE.lower() == 'phase':
            # This mode is intended to be used for correcting the phase error in your CT sensors. Please ensure that you have a purely resistive load running through your CT sensors - that means no electric fans and no digital circuitry!

            PF_ROUNDING_DIGITS = 3      # This variable controls how many decimal places the PF will be rounded

            while True:
                try:    
                    ct_num = int(input("\nWhich CT number are you calibrating? Enter the number of the CT label [0 - 5]: "))
                    if ct_num not in range(0, 6):
                        logger.error("Please choose from CT numbers 0, 1, 2, 3, 4, or 5.")
                    else:
                        ct_selection = f'ct{ct_num}'
                        break
                except ValueError:
                    logger.error("Please enter an integer! Acceptable choices are: 0, 1, 2, 3, 4, 5.")

            
            cont = input(dedent(f"""
                #------------------------------------------------------------------------------#
                # IMPORTANT: Make sure that current transformer {ct_selection} is installed over          #
                #            a purely resistive load and that the load is turned on            #
                #            before continuing with the calibration!                           #
                #------------------------------------------------------------------------------#

                Continue? [y/yes/n/no]: """))
                

            if cont.lower() in ['n', 'no']:
                logger.info("\nCalibration Aborted.\n")
                sys.exit()

            samples = collect_data(2000)
            rebuilt_wave = rebuild_wave(samples[ct_selection], samples['voltage'], ct_phase_correction[ct_selection])
            board_voltage = get_board_voltage()
            results = check_phasecal(rebuilt_wave['ct'], rebuilt_wave['new_v'], board_voltage)

            # Get the current power factor and check to make sure it is not negative. If it is, the CT is installed opposite to how it should be.
            pf = results['pf']
            initial_pf = pf  
            if pf < 0:
                logger.info(dedent('''
                    Current transformer is installed backwards. Please reverse the direction that it is attached to your load. \n
                    (Unclip it from your conductor, and clip it on so that the current flows the opposite direction from the CT's perspective) \n
                    Press ENTER to continue when you've reversed your CT.'''))
                input("[ENTER]")
                # Check to make sure the CT was reversed properly by taking another batch of samples/calculations:
                samples = collect_data(2000)
                rebuilt_wave = rebuild_wave(samples[ct_selection], samples['voltage'], 1)
                board_voltage = get_board_voltage()
                results = check_phasecal(rebuilt_wave['ct'], rebuilt_wave['new_v'], board_voltage)
                pf = results['pf']
                if pf < 0:
                    logger.info(dedent("""It still looks like the current transformer is installed backwards.  Are you sure this is a resistive load?\n
                        Please consult the project documentation on https://github.com/david00/rpi-power-monitor/wiki and try again."""))
                    sys.exit()

            # Initialize phasecal values
            new_phasecal = ct_phase_correction[ct_selection]
            previous_pf = 0
            new_pf = pf

            samples = collect_data(2000)
            board_voltage = get_board_voltage()
            best_pfs = find_phasecal(samples, ct_selection, PF_ROUNDING_DIGITS, board_voltage)
            avg_phasecal = sum([x['cal'] for x in best_pfs]) / len([x['cal'] for x in best_pfs])
            logger.info(f"Please update the value for {ct_selection} in ct_phase_correction in config.py with the following value: {round(avg_phasecal, 8)}")
            logger.info("Please wait... building HTML plot...")
            # Get new set of samples using recommended phasecal value
            samples = collect_data(2000)
            rebuilt_wave = rebuild_wave(samples[ct_selection], samples['voltage'], avg_phasecal)

            report_title = f'CT{ct_num}-phase-correction-result'
            plot_data(rebuilt_wave, report_title, ct_selection)
            logger.info(f"file written to {report_title}.html")

        if MODE.lower() == "terminal":
            # This mode will read the sensors, perform the calculations, and print the wattage, current, power factor, and voltage to the terminal.
            # Data is stored to the database in this mode!
                
            run_main()


