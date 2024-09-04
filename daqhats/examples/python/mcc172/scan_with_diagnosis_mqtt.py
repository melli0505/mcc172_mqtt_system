#!/usr/bin/env python
#  -*- coding: utf-8 -*-

"""
    MCC 172 Functions Demonstrated:
        mcc172.iepe_config_write
        mcc172.a_in_clock_config_write
        mcc172.a_in_clock_config_read
        mcc172.a_in_scan_start
        mcc172.a_in_scan_read
        mcc172.a_in_scan_stop
        mcc172.a_in_scan_cleanup

    Purpose:
        Performa a continuous acquisition on 1 or more channels.

    Description:
        Continuously acquires blocks of analog input data for a
        user-specified group of channels until the acquisition is
        stopped by the user.  The RMS voltage for each channel
        is displayed for each block of data received from the device.
"""
from __future__ import print_function
from sys import stdout, version_info
from time import sleep
from math import sqrt
import csv
from daqhats import mcc172, OptionFlags, SourceType, HatIDs, HatError
from daqhats_utils import select_hat_device, enum_mask_to_string, \
    chan_list_to_mask

from diagnosis import preprocessing, load_model, diagnosis
from sklearn.preprocessing import MinMaxScaler
import numpy as np

import time
from threading import Lock, Thread
from paho.mqtt import client as mqtt

READ_ALL_AVAILABLE = -1

CURSOR_BACK_2 = '\x1b[2D'
ERASE_TO_END_OF_LINE = '\x1b[0K'

broker_address =  "SERVER_ADDRESS"
client = mqtt.Client("motor_diag")
client.connect(broker_address, 1883)

def get_iepe():
    """
    Get IEPE enable from the user.
    """

    while True:
        # Wait for the user to enter a response
        print("IEPE enabled. ")
        response = 'y'

        # Check for valid response
        if (response == "y") or (response == "Y"):
            return 1
        elif (response == "n") or (response == "N"):
            return 0
        else:
            # Ask again.
            print("Invalid response.")

def main(): # pylint: disable=too-many-locals, too-many-statements
    """
    This function is executed automatically when the module is run directly.
    """

    # Store the channels in a list and convert the list to a channel mask that
    # can be passed as a parameter to the MCC 172 functions.

    channels = [0]#, 1]
    channel_mask = chan_list_to_mask(channels)
    num_channels = len(channels)

    samples_per_channel = 0

    options = OptionFlags.CONTINUOUS

    scan_rate = 10240.0


    try:
        # Select an MCC 172 HAT device to use.
        address = select_hat_device(HatIDs.MCC_172)
        hat = mcc172(address)

        print('\nSelected MCC 172 HAT device at address', address)

        # Turn on IEPE supply?
        iepe_enable = get_iepe()

        for channel in channels:
            hat.iepe_config_write(channel, iepe_enable)

        # Configure the clock and wait for sync to complete.
        hat.a_in_clock_config_write(SourceType.LOCAL, scan_rate)

        synced = False
        while not synced:
            (_source_type, actual_scan_rate, synced) = hat.a_in_clock_config_read()
            if not synced:
                sleep(0.005)

        print('\nMCC 172 continuous scan example')
        print('    Functions demonstrated:')
        print('         mcc172.iepe_config_write')
        print('         mcc172.a_in_clock_config_write')
        print('         mcc172.a_in_clock_config_read')
        print('         mcc172.a_in_scan_start')
        print('         mcc172.a_in_scan_read')
        print('         mcc172.a_in_scan_stop')
        print('         mcc172.a_in_scan_cleanup')
        print('    IEPE power: ', end='')
        if iepe_enable == 1:
            print('on')
        else:
            print('off')
        print('    Channels: ', end='')
        print(', '.join([str(chan) for chan in channels]))
        print('    Requested scan rate: ', scan_rate)
        print('    Actual scan rate: ', actual_scan_rate)
        print('    Options: ', enum_mask_to_string(OptionFlags, options))


# ------------------------Diagnosis Normalization---------------------------
        nor = []
        normal1 = csv.reader(open("/home/raspberry/diagnosis_data/test/1/normal1.csv", "r"), delimiter=",")
        for row in normal1:
            nor.extend(row)
        nor = np.array(nor, dtype=np.float32)

        scaler = MinMaxScaler()
        scaler.fit(nor.reshape(-1, 1))
# --------------------------------------------------------------------------



        # Configure and start the scan.
        # Since the continuous option is being used, the samples_per_channel
        # parameter is ignored if the value is less than the default internal
        # buffer size (10000 * num_channels in this case). If a larger internal
        # buffer size is desired, set the value of this parameter accordingly.
        hat.a_in_scan_start(channel_mask, samples_per_channel, options)

        print('Starting scan ... Press Ctrl-C to stop\n')

        # Display the header row for the data table.
        

        try:
            read_and_display_data(hat, num_channels, scaler)

        except KeyboardInterrupt:
            # Clear the '^C' from the display.
            print(CURSOR_BACK_2, ERASE_TO_END_OF_LINE, '\n')
            print('Stopping')

            hat.a_in_scan_stop()
            hat.a_in_scan_cleanup()

            # Turn off IEPE supply
            for channel in channels:
                hat.iepe_config_write(channel, 0)

    except (HatError, ValueError) as err:
        print('\n', err)

def calc_rms(data, channel, num_channels, num_samples_per_channel):
    """ Calculate RMS value from a block of samples. """
    value = 0.0
    index = channel
    for _i in range(num_samples_per_channel):
        value += (data[index] * data[index]) / num_samples_per_channel
        index += num_channels

    return sqrt(value)

def read_and_display_data(hat, num_channels, scaler):
    """
    Reads data from the specified channels on the specified DAQ HAT devices
    and updates the data on the terminal display.  The reads are executed in a
    loop that continues until the user stops the scan or an overrun error is
    detected.

    Args:
        hat (mcc172): The mcc172 HAT device object.
        num_channels (int): The number of channels to display.

    Returns:
        None

    """
    total_samples_read = 0
    read_request_size = READ_ALL_AVAILABLE

    # When doing a continuous scan, the timeout value will be ignored in the
    # call to a_in_scan_read because we will be requesting that all available
    # samples (up to the default buffer size) be returned.
    timeout = 5.0
    
# --------------------Diagnosis----------------------
    interpreter, input_details, output_details = load_model("/home/raspberry/daqhats/examples/python/mcc172/diagnosis/norm_q.tflite")
    period_timer = time.time()
    now = time.time()
# ---------------------------------------------------

    
# ----------------Temperature Timer------------------
    temp_period_timer = time.time()
    temp_now = time.time()
# ---------------------------------------------------

    data = []
    
    data_lock = Lock()

    print('\nSamples Read    Scan Count', end='')
    for chan, item in enumerate([0,1]):
        print('       Channel ', item, sep='', end='')
    print('')

    # Read all of the available samples (up to the size of the read_buffer which
    # is specified by the user_buffer_size).  Since the read_request_size is set
    # to -1 (READ_ALL_AVAILABLE), this function returns immediately with
    # whatever samples are available (up to user_buffer_size) and the timeout
    # parameter is ignored.
    while True:
        read_result = hat.a_in_scan_read(read_request_size, timeout)

        # Check for an overrun error
        if read_result.hardware_overrun:
            print('\n\nHardware overrun\n')
            break
        elif read_result.buffer_overrun:
            print('\n\nBuffer overrun\n')
            break

        samples_read_per_channel = int(len(read_result.data) / num_channels)
        total_samples_read += samples_read_per_channel

        print('\r{:12}'.format(samples_read_per_channel),
              ' {:12} '.format(total_samples_read), end='')

        # Display the RMS voltage for each channel.
        if samples_read_per_channel > 0:
            for i in range(num_channels):
                value = calc_rms(read_result.data, i, num_channels,
                                 samples_read_per_channel)
                now_loop = time.time()
                if now_loop - period_timer < 60 and len(data) < 102400:
                    data_lock.acquire()
                    data.extend(read_result.data[:samples_read_per_channel])
                    data_lock.release()
                elif now_loop - period_timer >= 60 and len(data) >= 102400:
                    data_lock.acquire()
                    th3 = Thread(target=diagnosis_motor, args=(3, interpreter, input_details, output_details, data, scaler))
                    th3.start()
                    data = []
                    period_timer = now_loop
                    data_lock.release()
                print('{:10.5f}'.format(value), 'Vrms ',
                      end='')
            stdout.flush()

            sleep(0.1)

    print('\n')

def diagnosis_motor(motor, interpreter, input_details, output_details, data, scaler):
    now = time.time()
    data = preprocessing(data, 3200, scaler)
    result = diagnosis(data, interpreter, input_details, output_details, 3200)

    category = ["normal", "misalignment", "unbalance", "damaged bearing"]
    client.publish("motor_diag_status", str(result+1))
    print("\n* diagnosis_result: ", category[result])


if __name__ == '__main__':
    main()
