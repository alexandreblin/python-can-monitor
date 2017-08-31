"""Tests for source_hanlder.py"""

import unittest

import serial

from canmonitor.source_handler import InvalidFrame, SerialHandler


class SerialHandlerTestCase(unittest.TestCase):
    """Test case for source_handler.SerialHandler."""

    def setUp(self):
        self.serial_handler = SerialHandler("LOOP FOR TESTS")  # device_name will not be used
        self.serial_handler.serial_device = serial.serial_for_url('loop://')

    def tearDown(self):
        self.serial_handler.close()

    def test_get_message(self):
        normal_frame = b"FRAME:ID=246:LEN=8:8E:62:1C:F6:1E:63:63:20\n"
        self.serial_handler.serial_device.write(normal_frame)
        frame_id, data = self.serial_handler.get_message()
        self.assertEqual(246, frame_id)
        self.assertEqual(b'\x8e\x62\x1c\xf6\x1e\x63\x63\x20', data)

        no_data_frame = b"FRAME:ID=246:LEN=0:\n"
        self.serial_handler.serial_device.write(no_data_frame)
        frame_id, data = self.serial_handler.get_message()
        self.assertEqual(246, frame_id)
        self.assertEqual(b'', data)

        wrong_length_frame = b"FRAME:ID=246:LEN=9:00:01:02:03:04:05:06:07\n"
        self.serial_handler.serial_device.write(wrong_length_frame)
        self.assertRaises(InvalidFrame, self.serial_handler.get_message)

        three_digit_data_frame = b"FRAME:ID=246:LEN=1:012\n"
        self.serial_handler.serial_device.write(three_digit_data_frame)
        self.assertRaises(InvalidFrame, self.serial_handler.get_message)

        one_digit_data_frame = b"FRAME:ID=246:LEN=1:0\n"
        self.serial_handler.serial_device.write(one_digit_data_frame)
        self.assertRaises(InvalidFrame, self.serial_handler.get_message)

        missing_id_frame = b"FRAME:LEN=1:8E\n"
        self.serial_handler.serial_device.write(missing_id_frame)
        self.assertRaises(InvalidFrame, self.serial_handler.get_message)

        missing_length_frame = b"FRAME:ID=246:8E\n"
        self.serial_handler.serial_device.write(missing_length_frame)
        self.assertRaises(InvalidFrame, self.serial_handler.get_message)
