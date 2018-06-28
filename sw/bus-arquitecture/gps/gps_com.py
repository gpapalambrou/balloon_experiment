#!/usr/bin/python

__author__ = 'gdiaz'

# GPS ZMQ COM INTERFACE

"""Provides a high level interface over ZMQ for data exchange.
"""

"""Description
    GPS comunication: node1

    console:  send data to node1

    data[gps]-->console[PUB]-> node1

"""

import zmq
import sys
import time
import re
import argparse
import codecs
import math

from threading import Thread
from time import sleep
from gps import *

sys.path.append('../')

from nodes.node_list import NODE_GPS, NODE_OBC, CSP_PORT_APPS

#define commands
GET_DATA = 5

class GpsComInterface:
    def __init__(self):
        # gps arguments
        self.gps_handler = gps(mode=WATCH_ENABLE) #starting the stream of info
        
        self.latitude = 0           #float
        self.longitude = 0          #float
        self.time_utc = 0           #str
        self.fix_time = 0           #float
        self.altitude = 0           #float
        self.speed_horizontal = 0   #float
        self.speed_vertical = 0     #float
        #com args
        self.node = chr(int(NODE_GPS)).encode("ascii", "replace")
        self.node_dest = NODE_OBC
        self.port_csp = CSP_PORT_APPS
        self.prompt = "[node({}) port({})] <message>: "

    def check_nan(self, num, id):
        #print(type(num))
        try:
            if math.isnan(num):
                return -1
        except:
            #print num, id
            return num

    def update_data(self):
        while True:
            self.latitude = self.check_nan(self.gps_handler.fix.latitude, 1)
            self.longitude = self.check_nan(self.gps_handler.fix.longitude, 2)
            self.time_utc = self.gps_handler.utc
            self.fix_time = self.check_nan(self.gps_handler.fix.time, 3)
            self.altitude = self.check_nan(self.gps_handler.fix.altitude, 4)
            self.speed_horizontal = self.check_nan(self.gps_handler.fix.speed, 5)
            self.speed_vertical = self.check_nan(self.gps_handler.fix.climb, 6)
            #print(self.gps_handler.utc, self.gps_handler.fix.time)
            time.sleep(0.1)
            self.gps_handler.next()

    def console(self, ip="localhost", in_port_tcp=8002, out_port_tcp=8001):
        """ Send messages to node """
        ctx = zmq.Context()
        pub = ctx.socket(zmq.PUB)
        sub = ctx.socket(zmq.SUB)
        sub.setsockopt(zmq.SUBSCRIBE, self.node)
        pub.connect('tcp://{}:{}'.format(ip, out_port_tcp))
        sub.connect('tcp://{}:{}'.format(ip, in_port_tcp))
        print('Start GPS Intreface as node: {}'.format(int(codecs.encode(self.node, 'hex'), 16)))

        while True:
            frame = sub.recv_multipart()[0] 
            header_a = []
            for byte in frame[1:5]:
                byte_int = int(codecs.encode(byte, 'hex'), 16)
                byte_hex = hex(byte_int)
                header_a.append(byte_hex[2:])

            #header_a = ["{:02x}".format(int(i)) for i in frame[1:5]]
            header = "0x"+"".join(header_a[::-1])
            data = frame[5:]
            try:
                csp_header = parse_csp(header)
            except:
                csp_header = ""
            print('\nMON:', frame)
            print('\tHeader: {},'.format(csp_header))
            print('\tData: {}'.format(data))
            cmd = int(data)

            if cmd == GET_DATA:
                #update data
                print('\nMeasurements:')
                print('\tLatitude: {},'.format(self.latitude))
                print('\tLongitude: {}'.format(self.longitude))
                print('\tTime_utc: {}'.format(self.time_utc))
                print('\tFix_time: {}'.format(self.fix_time))
                print('\tAltitude: {}'.format(self.altitude))
                print('\tSpeed_horizontal: {}'.format(self.speed_horizontal))
                print('\tSpeed_vertical: {}'.format(self.speed_vertical))
                # build msg
                #          Prio   SRC   DST    DP   SP  RES HXRC
                header_ = "{:02b}{:05b}{:05b}{:06b}{:06b}00000000"

                prompt = self.prompt.format(self.node_dest, self.port_csp)
                # Get CSP header_ and data
                hdr = header_.format(1, int(codecs.encode(self.node, 'hex'), 16), self.node_dest, self.port_csp, 63)

                # Build CSP message
                hdr_b = re.findall("........",hdr)[::-1]
                # print("con:", hdr_b, ["{:02x}".format(int(i, 2)) for i in hdr_b])
                hdr = bytearray([int(i,2) for i in hdr_b])
                # join data
                data_ = " ".join([str(self.latitude), str(self.longitude), str(self.time_utc), str(self.fix_time), str(self.altitude), str(self.speed_horizontal), str(self.speed_vertical)])
                msg = bytearray([int(self.node_dest),]) + hdr + bytearray(data_, "ascii")
                # send data to OBC node
                try:
                    pub.send(msg)
                except Exception as e:
                    pass
            cmd = -1

def get_parameters():
    """ Parse command line parameters """
    parser = argparse.ArgumentParser()

    parser.add_argument("-n", "--node", default=10, help="Node address")
    parser.add_argument("-d", "--ip", default="localhost", help="Hub IP address")
    parser.add_argument("-i", "--in_port", default="8001", help="Hub Input port")
    parser.add_argument("-o", "--out_port", default="8002", help="Hub Output port")
    parser.add_argument("--nmon", action="store_false", help="Disable monitor task")
    parser.add_argument("--ncon", action="store_false", help="Disable console task")

    return parser.parse_args()

if __name__ == '__main__':
    # Get arguments
    args = get_parameters()

    gps = GpsComInterface()

    tasks = []

    # Create a update data thread
    data_th = Thread(target=gps.update_data)
    # data_th.daemon = True
    tasks.append(data_th)
    data_th.start()

    if args.ncon:
        # Create a console socket
        console_th = Thread(target=gps.console, args=(args.ip, args.out_port, args.in_port))
        # console_th.daemon = True
        tasks.append(console_th)
        console_th.start()

    for th in tasks:
        th.join()
