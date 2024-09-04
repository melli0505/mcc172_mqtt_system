
#!/bin/bash
#!/usr/bin/python
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
from daqhats import mcc172, OptionFlags, SourceType, HatIDs, HatError
from daqhats_utils import select_hat_device, enum_mask_to_string, \
    chan_list_to_mask

import socket
import struct
import datetime, time
import logging
import csv

from threading import Lock, Thread
from paho.mqtt import client as mqtt

READ_ALL_AVAILABLE = -1

CURSOR_BACK_2 = '\x1b[2D'
ERASE_TO_END_OF_LINE = '\x1b[0K'

#server = ('10.0.0.189', 2001)
# server = ('10.0.0.140', 2001)

# socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

c = 0
def get_iepe():
    """
    Get IEPE enable from the user.
    """

    while True:
        # Wait for the user to enter a response
        message = "IEPE enable [y or n]?  "
        response = "y"
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
    channels = [0, 1]
    channel_mask = chan_list_to_mask(channels)
    num_channels = len(channels)

    samples_per_channel = 0

    options = OptionFlags.CONTINUOUS
    
    scan_rate = 25480	


    try:
        # Select an MCC 172 HAT device to use.
        address = select_hat_device(HatIDs.MCC_172)
        hat = mcc172(address)

        logger.info(f'\nSelected MCC 172 HAT device at address {address}')

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

        logger.info('\nMCC 172 continuous scan example')
        logger.info('    Functions demonstrated:')
        logger.info('         mcc172.iepe_config_write')
        logger.info('         mcc172.a_in_clock_config_write')
        logger.info('         mcc172.a_in_clock_config_read')
        logger.info('         mcc172.a_in_scan_start')
        logger.info('         mcc172.a_in_scan_read')
        logger.info('         mcc172.a_in_scan_stop')
        logger.info('         mcc172.a_in_scan_cleanup')
        logger.info(f'    IEPE power: {iepe_enable}')
        if iepe_enable == 1:
            print('on')
        else:
            print('off')
        logger.info(f'    Channels: {str(channels)}')
        print(', '.join([str(chan) for chan in channels]))
        logger.info(f'    Requested scan rate: {scan_rate}')
        logger.info(f'    Actual scan rate: {actual_scan_rate}')
        logger.info(f'    Options: {str(enum_mask_to_string(OptionFlags, options))}')

        # try:
        #     input('\nPress ENTER to continue ...')
        # except (NameError, SyntaxError):
        #    pass


        # Configure and start the scan.
        # Since the continuous option is being used, the samples_per_channel
        # parameter is ignored if the value is less than the default internal
        # buffer size (10000 * num_channels in this case). If a larger internal
        # buffer size is desired, set the value of this parameter accordingly.
        hat.a_in_scan_start(channel_mask, samples_per_channel, options)

        logger.info('Starting scan...\n')

        # Display the header row for the data table.
        print('Samples Read    Scan Count', end='')
        for chan, item in enumerate(channels):
            print('       Channel ', item, sep='', end='')
        print('')

        try:
            read_and_display_data(hat, num_channels)

        except KeyboardInterrupt:
            # Clear the '^C' from the display.
            print(CURSOR_BACK_2, ERASE_TO_END_OF_LINE, '\n')
            logger.info('Stopping due to KeyboardInterrupt.')

            hat.a_in_scan_stop()
            hat.a_in_scan_cleanup()

            # Turn off IEPE supply
            for channel in channels:
                hat.iepe_config_write(channel, 0)
            
    except (HatError, ValueError) as err:
        logger.error('\n {err}')

def calc_rms(data, channel, num_channels, num_samples_per_channel):
    """ Calculate RMS value from a block of samples. """
    value = 0.0
    index = channel
    for _i in range(num_samples_per_channel):
        value += (data[index] * data[index]) / num_samples_per_channel
        index += num_channels

    return sqrt(value)

def read_and_display_data(hat, num_channels):
    global c, control
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
    samples_read_per_second = 0
    read_request_size = READ_ALL_AVAILABLE

    # When doing a continuous scan, the timeout value will be ignored in the
    # call to a_in_scan_read because we will be requesting that all available
    # samples (up to the default buffer size) be returned.
    timeout = 5.0

    
    period_timer = time.time()
    record_timer = time.time()
    now = time.time()

    data3 = []
    data4 = []
    
    data3_lock = Lock()
    data4_lock = Lock()

    file_num = 50
    
    recent = time.time()
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
        samples_read_per_second += samples_read_per_channel
        now = time.time()
        """
        if now - recent >= 1:
            logger.info(f"samples read per second: {samples_read_per_second}")
            samples_read_per_second = 0
            recent = now
        """
        print('\r{:12}'.format(samples_read_per_channel),
                ' {:12} '.format(total_samples_read), end='')
        # Display the RMS voltage for each channel.
        if samples_read_per_channel > 0:
            for i in range(num_channels):
                value = calc_rms(read_result.data, i, num_channels,
                                samples_read_per_channel)
                print('{:10.5f}'.format(value), 'Vrms ',
                      end='')
                if file_num > 0: 
                    if time.time() - period_timer < 60:
                        if len(data3) < 102400:
                            data3_lock.acquire()
                            data3.extend(read_result.data[:samples_read_per_channel])
                            data3_lock.release()
                        if len(data4) < 102400:
                            data4_lock.acquire()
                            data4.extend(read_result.data[:samples_read_per_channel])
                            data4_lock.release()
                    elif time.time() - period_timer > 60:
                        if len(data3) >= 102400:
                            data3_lock.acquire()
                            th3 = Thread(target=recording, args=(3, data3))
                            th3.start()
                        # diagnosis_motor(3, interpreter, input_details, output_details, data3)
                            data3 = []
                            data3_lock.release()
                        if len(data4) >= 102400:
                            data4_lock.acquire()
                            th4 = Thread(target=recording, args=(4, data4))
                            th4.start()
                            # diagnosis_motor(3, interpreter, input_details, output_details, data3)
                            data4 = []
                            data4_lock.release()
                        period_timer = time.time()
                        file_num -= 1

                """
                data_lock.acquire()
                if control == "3" and i == 1:
                     data = struct.pack('%sd' %len(read_result.data[:samples_read_per_channel]), *read_result.data[:samples_read_per_channel])
                    socket.sendto(data, server)
                    c += 1
                elif control == "4" and i == 0:
                    data = struct.pack('%sd' %len(read_result.data[samples_read_per_channel:]), *read_result.data[samples_read_per_channel:])
                    socket.sendto(data, server)
                print('{:10.5f}'.format(value), 'Vrms ',
                    end='')
                data_lock.release()
                """
            stdout.flush()
            sleep(0.1)

    print('\n')


def on_message(client, userdata, message):
    global control
    data_lock.acquire()
    control = str(message.payload.decode("utf-8"))
    logger.info(f'/ - Control Command: {control}\n')
    data_lock.release()
"""
def mqtt_client():
    logger.info("/ - Starting MQTT Service...\n")
    broker_address = "10.0.0.118"
    client = mqtt.Client("motor34")
    client.connect(broker_address, 1883)
    client.subscribe("motor34")
    client.on_message = on_message
    logger.info("/ - Start MQTT Loop\n")
    client.loop_forever()
"""
def recording(motor_num, data):
    n = datetime.datetime.now().strftime('%m%d-%H.%M.%S')
    with open(f"/home/raspberry/diagnosis_data/test/records/{motor_num}_{n}", "w") as f:
        writer = csv.writer(f, delimiter=",")
        writer.writerow(data)

if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%b %d %H:%M:%S')

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # file_handler = logging.FileHandler('/home/raspberry/main.log')
    # file_handler.setFormatter(formatter)
    # logger.addHandler(file_handler)


    data_lock = Lock()
    control = "00"

    # th = Thread(target=mqtt_client, args=())
    # th.start()

    main()
    
    # t = Thread(target=mqtt_client, args=())
    # t.start()
    # sys.exit(app.exec_())
