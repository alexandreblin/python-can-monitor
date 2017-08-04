"""Tests for canmonitor.py"""


from os import path
import unittest

from canmonitor import canmonitor


TEST_DATA_DIR = path.abspath(path.join(path.dirname(__file__), 'data'))


class CanmonitorTestCase(unittest.TestCase):
    """Test case for canmonitor.py."""

    def test_parse_ints(self):
        with open(path.join(TEST_DATA_DIR, 'ids.txt')) as f_obj:
            int_set = canmonitor.parse_ints(f_obj)
        self.assertEqual(int_set, {1, 2, 15, 3, 4, 57, 7})
