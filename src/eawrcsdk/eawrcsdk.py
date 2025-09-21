import socket
import struct
import json
import os
import logging
import math

logger = logging.getLogger("EAWRCSDK")

class EAWRCSDK(dict):
    def __init__(self, UDP_IP = "127.0.0.1", UDP_PORT = 20777, TIMEOUT_SECONDS = 1, UDP_PATH = None, CHANNELS_PATH = None):
        """
        Keyword arguments:
        UDP_IP -- IP that UDP socket listens to
        UDP_PORT -- Port that UDP Socket listens to
        TIMEOUT_SECONDS -- Sets timeout for UDP Socket
        UDP_PATH -- Path to .json file containing packet layout
        CHANNELS_PATH -- Path to .json file containing list of channels IDs in order of serialization
        """
        self.UDP_IP = UDP_IP
        self.UDP_PORT = UDP_PORT
        self.TIMEOUT_SECONDS = TIMEOUT_SECONDS
        self._frozen = False
        
        if UDP_PATH:
            self.UDP_PATH = UDP_PATH
        else:
            self.UDP_PATH = os.path.expanduser(
                "~/Documents/My Games/WRC/telemetry/readme/udp/wrc.json"
            )
        if CHANNELS_PATH:
            self.CHANNELS_PATH = CHANNELS_PATH
        else:
            self.CHANNELS_PATH = os.path.expanduser(
                "~/Documents/My Games/WRC/telemetry/readme/channels.json"
            )
        try:
            with open(self.UDP_PATH) as f:
                self.wrc_packet_structure = json.load(f)
        except FileNotFoundError:
            print("UDP config file not found. Ensure you've run the game once.")
            logger.error("Telemetry config files not found. Ensure you've run the game once.")
            exit()

        try:
            with open(self.CHANNELS_PATH) as f:
                self._wrc_channels = json.load(f)["channels"]
        except FileNotFoundError:
            print("Channel config files not found. Ensure you've run the game once.")
            logger.error("Telemetry config files not found. Ensure you've run the game once.")
            exit()
        
        self._channel_map = {
            c['id']: {'type': c['type'], 'units': c['units'], 'description': c['description']}
            for c in self._wrc_channels
        }

        self._session_update_channels = [
            channel
            for packet in self.wrc_packet_structure['packets']
            if packet['id'] == 'session_update'
            for channel in packet['channels']
        ]

        # Struct format string based on channel types
        self._struct_format = "<" 
        for channel_id in self._session_update_channels:
            match self._channel_map[channel_id]['type']:
                case "float32": self._struct_format += "f"
                case "float64": self._struct_format += "d"
                case "int16": self._struct_format += "h"
                case "uint8": self._struct_format += "B"
                case "uint64": self._struct_format += "Q"
                case "boolean": self._struct_format += "?"
                case _:
                    self._struct_format += "x" # padding
                    print(f"Warning: Unknown type for channel '{channel_id}'")
                    logger.warning(f"Warning: Unknown type for channel '{channel_id}'")

        for i, channel_id in enumerate(self._session_update_channels):
                self[channel_id] = None

    def connect(self):
        """Instantiates and connects user configured UDP Socket"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.UDP_PORT))
        self.sock.settimeout(self.TIMEOUT_SECONDS)
        self.sock.setblocking(False)
        logger.info(f"UDP socket listening on port {self.UDP_PORT}")

    def close(self):
        """Closes UDP Socket"""
        if self.sock:
            try:
                self.sock.close()
                logger.info(f"UDP socket closed")
            except OSError:
                pass

    def _buffer(self):
        """Retrieves data from UDP Socket then flushes socket"""
        try:
            data, addr = self.sock.recvfrom(2048) # Buffer size for a single packet
        except socket.error:
            return None
        except socket.timeout:
            return None

        if len(data) == struct.calcsize(self._struct_format):
            unpacked_data = struct.unpack(self._struct_format, data)
                        
            for i, channel_id in enumerate(self._session_update_channels):
                self[channel_id] = unpacked_data[i]
        else:
            print(f"Received a packet of unexpected size: {len(data)} bytes. Skipping.")
        if self._frozen: #Flushes socket
            while True:
                try:
                    data, addr = self.sock.recvfrom(2048)
                except socket.error:
                    break
                except socket.timeout:
                    break
        

    def freeze_buffer_latest(self):
        """Used to freeze telemmetry data so all data retrieved is from the same telemmetry packet"""
        self._buffer()
        if not self._frozen:
            self._frozen = True

    def unfreeze(self):
        """Unfreezes buffer so telemmetry is always retrieved from latest socket data"""
        self._frozen = False
    
    def __getitem__(self, key):
        """If not frozen, retrieves latest socket data before returning key value. Otherwise returns key value immediately"""
        if not self._frozen:
            self._buffer()
        try:
            return super().__getitem__(key)
        except KeyError:
            print(f"KeyError: Key '{key}' not found.")
            logger.error(f"KeyError: Key '{key}' not found.")
            raise

    def get_vehicle_quaternion(self):
        """Set and process vehicle rotation matrix and returns quaternion values"""
        r00 = self['vehicle_left_direction_x']
        r10 = self['vehicle_left_direction_y']
        r20 = self['vehicle_left_direction_z']
        r01 = self['vehicle_up_direction_x']
        r11 = self['vehicle_up_direction_y']
        r21 = self['vehicle_up_direction_z']
        r02 = self['vehicle_forward_direction_x']
        r12 = self['vehicle_forward_direction_y']
        r22 = self['vehicle_forward_direction_z']

        trace = r00 + r11 + r22

        if trace > 0:
            S = math.sqrt(trace + 1.0) * 2  # S=4*qw
            w = 0.25 * S
            x = (r21 - r12) / S
            y = (r02 - r20) / S
            z = (r10 - r01) / S
        elif (r00 > r11) and (r00 > r22):
            S = math.sqrt(1.0 + r00 - r11 - r22) * 2  # S=4*qx
            w = (r21 - r12) / S
            x = 0.25 * S
            y = (r01 + r10) / S
            z = (r02 + r20) / S
        elif r11 > r22:
            S = math.sqrt(1.0 + r11 - r00 - r22) * 2  # S=4*qy
            w = (r02 - r20) / S
            x = (r01 + r10) / S
            y = 0.25 * S
            z = (r12 + r21) / S
        else:
            S = math.sqrt(1.0 + r22 - r00 - r11) * 2  # S=4*qz
            w = (r10 - r01) / S
            x = (r02 + r20) / S
            y = (r12 + r21) / S
            z = 0.25 * S

        return w, x, y, z

