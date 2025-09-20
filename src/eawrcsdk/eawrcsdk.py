import socket
import struct
import json
import os
import logging

logger = logging.getLogger("EAWRCSDK")

class EAWRCSDK(dict):
    def __init__(self, UDP_IP = "127.0.0.1", UDP_PORT = 20777, TIMEOUT_SECONDS = 1):
        self.UDP_IP = UDP_IP
        self.UDP_PORT = UDP_PORT
        self.TIMEOUT_SECONDS = TIMEOUT_SECONDS
        self._frozen = False

        try:
            with open(os.path.expanduser(
                "~/Documents/My Games/WRC/telemetry/readme/udp/wrc.json"
            )) as f:
                self.wrc_packet_structure = json.load(f)
            with open(os.path.expanduser(
                "~/Documents/My Games/WRC/telemetry/readme/channels.json"
            )) as f:
                self._wrc_channels = json.load(f)["channels"]
        except FileNotFoundError:
            print("Telemetry config files not found. Ensure you've run the game once.")
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
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.UDP_PORT))
        self.sock.settimeout(self.TIMEOUT_SECONDS)
        logger.info(f"UDP socket listening on port {self.UDP_PORT}")

    def close(self):
        if self.sock:
            try:
                self.sock.close()
                logger.info(f"UDP socket closed")
            except OSError:
                pass

    def _buffer(self):
        try:
            data, addr = self.sock.recvfrom(2048) # Buffer size for a single packet
        except socket.timeout:
            return None

        if len(data) == struct.calcsize(self._struct_format):
            unpacked_data = struct.unpack(self._struct_format, data)
                        
            for i, channel_id in enumerate(self._session_update_channels):
                self[channel_id] = unpacked_data[i]
        else:
            print(f"Received a packet of unexpected size: {len(data)} bytes. Skipping.")

    def freeze_buffer_latest(self):
        self._buffer()
        self._frozen = True

    def unfreeze(self):
        self._frozen = False
    
    def __getitem__(self, key):
        if not self._frozen:
            self._buffer()
        try:
            return super().__getitem__(key)
        except KeyError:
            print(f"KeyError: Key '{key}' not found.")
            logger.error(f"KeyError: Key '{key}' not found.")
            raise
