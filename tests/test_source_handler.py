"""Tests for source_hanlder.py"""

from os import path
import unittest

import serial

from canmonitor.source_handler import CandumpHandler, InvalidFrame, SerialHandler


TEST_DATA_DIR = path.abspath(path.join(path.dirname(__file__), 'data'))


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


class CandumpHandlerTestCase(unittest.TestCase):
    """Test case for source_handler.CandumpHandler."""

    maxDiff = None

    def setUp(self):
        file_path = path.join(TEST_DATA_DIR, 'test_data.log')
        self.candump_handler = CandumpHandler(file_path)
        self.candump_handler.open()

    def tearDown(self):
        self.candump_handler.close()

    def test_get_message(self):
        messages = [self.candump_handler.get_message() for _ in range(7)]

        expected_messages = [
            (0x000, b""),
            (0x000, b"\x00\x00\x00\x00\x00\x00\x00\x00"),
            (0xFFF, b"\xff\xff\xff\xff\xff\xff\xff\xff"),
            (0x001, b"\x00\x00\x00\x00\x00\x00\x00\x01"),
            (0x100, b"\x10\x00\x00\x00\x00\x00\x00\x00"),
            (0xABC, b"\x12\xaf\x49"),
            (0x743, b"\x9f\x20\xa1\x20\x78\xbc\xea\x98"),
        ]

        self.assertEqual(expected_messages, messages)

        self.assertRaises(InvalidFrame, self.candump_handler.get_message)
        self.assertRaises(EOFError, self.candump_handler.get_message)
