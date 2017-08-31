from binascii import unhexlify

import serial


class InvalidFrame(Exception):
    pass


class SourceHandler:
    """Base class for classes reading CAN messages.

    This serves as a kind of interface for all classes reading CAN messages,
    whatever the source of these messages: serial port, text file etc.
    """

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def get_message(self):
        """Get CAN id and CAN data.

        Returns:
            A tuple containing the id (int) and data (bytes)

        Raises:
            InvalidFrame
        """
        raise NotImplementedError


class SerialHandler(SourceHandler):

    def __init__(self, device_name, baudrate=115200):
        self.device_name = device_name
        self.baudrate = baudrate
        self.serial_device = None

    def open(self):
        self.serial_device = serial.Serial(self.device_name, self.baudrate, timeout=0)

    def close(self):
        if self.serial_device:
            self.serial_device.close()

    def get_message(self):
        line = self._read_until_newline()
        return self._parse(line)

    def _read_until_newline(self):
        """Read data from `serial_device` until the next newline character."""
        line = self.serial_device.readline()
        while not line.endswith(b'\n'):
            line = line + self.serial_device.readline()

        return line.strip()

    @staticmethod
    def _parse(line):
        # Sample frame from Arduino: FRAME:ID=246:LEN=8:8E:62:1C:F6:1E:63:63:20

        # Split it into an array
        # (e.g. ['FRAME', 'ID=246', 'LEN=8', '8E:62:1C:F6:1E:63:63:20'])
        frame = line.split(b':', maxsplit=3)

        try:
            frame_id = int(frame[1][3:])  # get the ID from the 'ID=246' string

            frame_length = int(frame[2][4:])  # get the length from the 'LEN=8' string

            hex_data = frame[3].replace(b':', b'')
            data = unhexlify(hex_data)

        except Exception as exc:
            raise InvalidFrame("Invalid frame {}".format(line)) from exc

        if len(data) != frame_length:
            raise InvalidFrame("Wrong frame length or invalid data: {}".format(line))

        return frame_id, data
