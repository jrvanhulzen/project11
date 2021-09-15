import logging
import sys

# Create basic logger
logger = logging.getLogger('power_monitor')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s : %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)


# Using a multimeter, measure the voltage of the receptacle where your 9V AC transformer will plug into. Enter the measured value below.
GRID_VOLTAGE = 232.0
# Using a multimeter, measure the output voltage of your AC transformer. Using the value on the label is not ideal and will lead to greater accuracy in the calculations.
AC_TRANSFORMER_OUTPUT_VOLTAGE = 12.20
AC_voltage_ratio            = (GRID_VOLTAGE / AC_TRANSFORMER_OUTPUT_VOLTAGE) * 11   # This is a rough approximation of the ratio


# Define Variables
ct4_channel = 2             # 3.5mm Input #1        | Subpanel main (leg 2 - bottom)
board_voltage_channel =  3  # Board voltage ~3.3V
v_sensor_channel = 1        # 9V AC Voltage channel


# The values from running the software in "phase" mode should go below!
ct_phase_correction = {

    'ct4' : 1.044,
}

# AFTER phase correction is completed, these values are used in the final calibration for accuracy. See the documentation for more information.
accuracy_calibration = {
    
    'ct4' : 0.0607,
    'AC'  : 1.0765,
}



