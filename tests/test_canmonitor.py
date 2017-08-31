"""Tests for canmonitor.py"""


from os import path
import unittest

from canmonitor import canmonitor


TEST_DATA_DIR = path.abspath(path.join(path.dirname(__file__), 'data'))


class CanmonitorTestCase(unittest.TestCase):
    """Test case for canmonitor.py."""

    def test_format_data_ascii(self):
        # ASCII chars
        decoded_str = canmonitor.format_data_ascii(b"\x20\x7e")
        self.assertEqual(decoded_str, " ~")

        # Null characters
        decoded_str = canmonitor.format_data_ascii(b"\x00\x00")
        self.assertEqual(decoded_str, "..")

        # Non-ASCII chars
        decoded_str = canmonitor.format_data_ascii(b"\x01\x1f\x7f\xff")
        self.assertEqual(decoded_str, "????")

        # Empty data
        decoded_str = canmonitor.format_data_ascii(b"")
        self.assertEqual(decoded_str, "")

    def test_format_data_hex(self):
        formatted_str = canmonitor.format_data_hex(b"\x00\x01\x20\x77\xff")
        self.assertEqual(formatted_str, "00 01 20 77 FF")

        # Empty data
        formatted_str = canmonitor.format_data_hex(b"")
        self.assertEqual(formatted_str, "")

    def test_parse_ints(self):
        with open(path.join(TEST_DATA_DIR, 'ids.txt')) as f_obj:
            int_set = canmonitor.parse_ints(f_obj)
        self.assertEqual(int_set, {1, 2, 15, 3, 4, 57, 7})
