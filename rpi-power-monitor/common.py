# This module contains functions that are used in both the main power-monitor code and the calibration code.

from datetime import datetime
from math import sqrt
from config import ct_phase_correction, ct4_channel, board_voltage_channel, v_sensor_channel, logger, accuracy_calibration, AC_voltage_ratio 
import spidev
import subprocess
import sys
from time import sleep
from textwrap import dedent

#Create SPI
spi = spidev.SpiDev()
spi.open(0, 0)
#spi.max_speed_hz =  1953125         # 1ghz core clock /512
spi.max_speed_hz =  1953125         # 1ghz core clock /512
spi.no_cs = False

def readadc(adcnum):
    # read SPI data from the MCP3008, 8 channels in total
    r = spi.xfer2([1, 8 + adcnum << 4, 0])
    data = ((r[1] & 3) << 8) + r[2]
    return data

def collect_data(numSamples):
  
    samples = []
    ct4_data = [None]*numSamples
    v_data = [None]*numSamples
    temp_data = [None]*numSamples
    r = [None]*3
    r2= [None]*3
    r3= [None]*3
    r3 = spi.xfer([1, 8 + 7 << 4, 0]) # 3 bytes to send, temp channel =8
    tempMeasurement  = ((r3[1] & 3) << 8) + r3[2]
        
    for i in range(numSamples):
        
        r = spi.xfer([1, 8 + 2 << 4, 0]) # 3 bytes to send, ct4 channgel = 2
        ct4_data[i]   = ((r[1] & 3) << 8) + r[2]
        r2 = spi.xfer([1, 8 + 1 << 4, 0]) # 3 bytes to send, vAC channel =1
        v_data[i]     = ((r2[1] & 3) << 8) + r2[2]  
        temp_data[i]  = tempMeasurement
        
        #r = spi.xfer([1, 8 + 7 << 4, 0]) # 3 bytes to send, then speed, then CS flag
        #ct5_data[i]   = ((r[1] & 3) << 8) + r[2]
        
        #r = spi.xfer2([1, 8 + 5 << 4, 0]) # 3 bytes to send, vAC channel =5
    
        
        #ct4_data.append(readadc(ct4_channel))
        #r = spi.xfer([1, 8 + 6 << 4, 0],1953125) # 3 bytes to send, then speed, then CS flag
        #ct4_data[i] = ((r[1] & 3) << 8) + r[2]
        #readadc(ct4_channel)
        #ct5_data.append(readadc(ct5_channel))

        
        ##readadc(ct5_channel)

        
        #v_data[i]   =  readadc(5)
        
    samples = {
        'ct4' : ct4_data,
        'voltage' : v_data,
        'pitemp' : temp_data,
    }
    return samples

def rebuild_waves(samples, PHASECAL_4):

    # The following empty lists will hold the phase corrected voltage wave that corresponds to each individual CT sensor.

    wave_4 = []
    voltage_samples = samples['voltage']
    tempAdc = samples['pitemp'][1]
    temp_degrees = tempAdc/1024*3300/20
    wave_4.append(voltage_samples[0])
    previous_point = voltage_samples[0]
    
    for current_point in voltage_samples[1:]:
        
        new_point_4 = previous_point + PHASECAL_4 * (current_point - previous_point)
        wave_4.append(new_point_4)
        previous_point = current_point

    rebuilt_waves = {

        'v_ct4' : wave_4,
          
        'voltage' : voltage_samples,
        'pitemp' : temp_degrees,
        'ct4' : samples['ct4'],
 
    }

    return rebuilt_waves

def calculate_power(samples, board_voltage):

    ct4_samples = samples['ct4']        # current samples for CT4


    v_samples_4 = samples['v_ct4']      # phase-corrected voltage wave specifically for CT4   
   

    # Variable Initialization    

    sum_inst_power_ct4 = 0


    sum_squared_current_ct4 = 0

    sum_raw_current_ct4 = 0
    
    sum_squared_voltage_4 = 0

    sum_raw_voltage_4 = 0
   

    # Scaling factors
    vref = board_voltage / 1024
    ct4_scaling_factor = vref * 100 * accuracy_calibration['ct4']
    voltage_scaling_factor = vref * AC_voltage_ratio * accuracy_calibration['AC']
    

    num_samples = len(v_samples_4)
    
    for i in range(0, num_samples):

        ct4 = (int(ct4_samples[i]))


        voltage_4 = (int(v_samples_4[i]))
       

        # Process all data in a single function to reduce runtime complexity
        # Get the sum of all current samples individually

        sum_raw_current_ct4 += ct4


        sum_raw_voltage_4 += voltage_4



        # Calculate instant power for each ct sensor

        inst_power_ct4 = ct4 * voltage_4
       
        sum_inst_power_ct4 += inst_power_ct4
      

        # Squared voltage

        squared_voltage_4 = voltage_4 * voltage_4
     

        sum_squared_voltage_4 += squared_voltage_4
      
        # Squared current

        sq_ct4 = ct4 * ct4
       
        

        sum_squared_current_ct4 += sq_ct4
     


    avg_raw_current_ct4 = sum_raw_current_ct4 / num_samples
    

    avg_raw_voltage_4 = sum_raw_voltage_4 / num_samples
    

    real_power_4 = ((sum_inst_power_ct4 / num_samples) - (avg_raw_current_ct4 * avg_raw_voltage_4))  * ct4_scaling_factor * voltage_scaling_factor 
   


    mean_square_current_ct4 = sum_squared_current_ct4 / num_samples 
   

    mean_square_voltage_4 = sum_squared_voltage_4 / num_samples
    

    rms_current_ct4 = sqrt(mean_square_current_ct4 - (avg_raw_current_ct4 * avg_raw_current_ct4)) * ct4_scaling_factor
    
    rms_voltage_4     = sqrt(mean_square_voltage_4 - (avg_raw_voltage_4 * avg_raw_voltage_4)) * voltage_scaling_factor
 

    # Power Factor

    apparent_power_4 = rms_voltage_4 * rms_current_ct4
     
    try:
        power_factor_4 = real_power_4 / apparent_power_4
    except ZeroDivisionError:
        power_factor_4 = 0
 
       
    results = {                           
        'ct4' : {                                   
            'power'     : real_power_4,
            'current'   : rms_current_ct4,
            'voltage'   : rms_voltage_4,
            'pf'        : power_factor_4
        },
        'voltage' : rms_voltage_4,
        'pitemp' : samples['pitemp'],
    }

    return results

def get_board_voltage():
    # Take 10 sample readings and return the average board voltage from the +3.3V rail. 
    samples = []
    while len(samples) <= 10:
        data = readadc(board_voltage_channel)
        samples.append(data)

    avg_reading = sum(samples) / len(samples)
    board_voltage = (avg_reading / 1024) * 3.31 * 2
    board_voltage = 3.22
    return board_voltage

