#!/usr/bin/env python3

import argparse
import curses
import sys
import threading
import traceback

import serial

should_redraw = threading.Event()
stop_serial = threading.Event()

can_messages = {}
can_messages_lock = threading.Lock()

thread_exception = None


def read_until_newline(serial_device):
    """Read data from `serial_device` until the next newline character."""
    line = serial_device.readline()
    while len(line) == 0 or line[-1:] != b'\n':
        line = line + serial_device.readline()

    return line.strip()


def serial_run_loop(serial_device, blacklist):
    """Background thread for serial reading."""
    try:
        while not stop_serial.is_set():
            line = read_until_newline(serial_device)

            # Sample frame from Arduino: FRAME:ID=246:LEN=8:8E:62:1C:F6:1E:63:63:20
            # Split it into an array (e.g. ['FRAME', 'ID=246', 'LEN=8', '8E', '62', '1C', 'F6', '1E', '63', '63', '20'])
            frame = line.split(b':')

            try:
                frame_id = int(frame[1][3:])  # get the ID from the 'ID=246' string

                if frame_id in blacklist:
                    continue

                frame_length = int(frame[2][4:])  # get the length from the 'LEN=8' string

                data = [int(byte, 16) for byte in frame[3:]]  # convert the hex strings array to an integer array
                data = [byte for byte in data if byte >= 0 and byte <= 255]  # sanity check

                if len(data) != frame_length:
                    # Wrong frame length or invalid data
                    continue

                # Add the frame to the can_messages dict and tell the main thread to refresh its content
                with can_messages_lock:
                    can_messages[frame_id] = data
                    should_redraw.set()
            except:
                # Invalid frame
                continue
    except:
        if not stop_serial.is_set():
            # Only log exception if we were not going to stop the thread
            # When quitting, the main thread calls close() on the serial device
            # and read() may throw an exception. We don't want to display it as
            # we're stopping the script anyway
            global thread_exception
            thread_exception = sys.exc_info()


def init_window(stdscr):
    """Init a window filling the entire screen with a border around it."""
    stdscr.clear()
    stdscr.refresh()

    max_y, max_x = stdscr.getmaxyx()
    root_window = stdscr.derwin(max_y, max_x, 0, 0)

    root_window.box()

    return root_window


def format_data_hex(data):
    """Convert the bytes array to an hex representation."""
    # Bytes are separated by spaces.
    return ' '.join('%02X' % byte for byte in data)


def format_data_ascii(data):
    """Try to make an ASCII representation of the bytes.

    Non printable characters are replaced by '?' except null character which
    is replaced by '.'.
    """
    msg_str = ''
    for byte in data:
        char = chr(byte)
        if char == '\0':
            msg_str = msg_str + '.'
        elif ord(char) < 32 or ord(char) > 126:
            msg_str = msg_str + '?'
        else:
            msg_str = msg_str + char
    return msg_str


def main(stdscr, serial_thread):
    """Main function displaying the UI."""
    # Don't print typed character
    curses.noecho()
    curses.cbreak()
    curses.curs_set(0) # set cursor state to invisible

    # Set getch() to non-blocking
    stdscr.nodelay(True)

    win = init_window(stdscr)

    while True:
        # should_redraw is set by the serial thread when new data is available
        if should_redraw.is_set():
            max_y, max_x = win.getmaxyx()

            column_width = 50
            id_column_start = 2
            bytes_column_start = 13
            text_column_start = 38

            # Compute row/column counts according to the window size and borders
            row_start = 3
            lines_per_column = max_y - (1 + row_start)
            num_columns = (max_x - 2) // column_width

            # Setting up column headers
            for i in range(0, num_columns):
                win.addstr(1, id_column_start + i * column_width, 'ID')
                win.addstr(1, bytes_column_start + i * column_width, 'Bytes')
                win.addstr(1, text_column_start + i * column_width, 'Text')

            win.addstr(3, id_column_start, "Press 'q' to quit")

            row = row_start + 2  # The first column starts a bit lower to make space for the 'press q to quit message'
            current_column = 0

            # Make sure we don't read the can_messages dict while it's being written to in the serial thread
            with can_messages_lock:
                for frame_id in sorted(can_messages.keys()):
                    msg = can_messages[frame_id]

                    msg_bytes = format_data_hex(msg)

                    msg_str = format_data_ascii(msg)

                    # print frame ID in decimal and hex
                    win.addstr(row, id_column_start + current_column * column_width, '%s' % str(frame_id).ljust(5))
                    win.addstr(row, id_column_start + 5 + current_column * column_width, '%X'.ljust(5) % frame_id)

                    # print frame bytes
                    win.addstr(row, bytes_column_start + current_column * column_width, msg_bytes.ljust(23))

                    # print frame text
                    win.addstr(row, text_column_start + current_column * column_width, msg_str.ljust(8))

                    row = row + 1

                    if row >= lines_per_column + row_start:
                        # column full, switch to the next one
                        row = row_start
                        current_column = current_column + 1

                        if current_column >= num_columns:
                            break

            win.refresh()

            should_redraw.clear()

        c = stdscr.getch()
        if c == ord('q') or not serial_thread.is_alive():
            break
        elif c == curses.KEY_RESIZE:
            win = init_window(stdscr)
            should_redraw.set()


def parse_ints(string_list):
    int_set = set()
    for line in string_list:
        try:
            int_set.add(int(line, 0))
        except ValueError:
            continue
    return int_set


def run():
    parser = argparse.ArgumentParser(description='Process CAN data from a serial device.')
    parser.add_argument('serial_device', type=str)
    parser.add_argument('baud_rate', type=int, default=115200,
                        help='Serial baud rate in bps (default: 115200)')

    parser.add_argument('--blacklist', '-b', nargs='+', metavar='BLACKLIST', help="Ids that must be ignored")
    parser.add_argument(
        '--blacklist-file',
        '-bf',
        metavar='BLACKLIST_FILE',
        help="File containing ids that must be ignored",
    )

    args = parser.parse_args()

    serial_device = None
    serial_thread = None

    # --blacklist-file prevails over --blacklist
    if args.blacklist_file:
        with open(args.blacklist_file) as f_obj:
            blacklist = parse_ints(f_obj)
    elif args.blacklist:
        blacklist = parse_ints(args.blacklist)
    else:
        blacklist = set()

    try:
        # Open serial device with non-blocking read() (timeout=0)
        serial_device = serial.Serial(args.serial_device, args.baud_rate, timeout=0)

        # Start the serial reading background thread
        serial_thread = threading.Thread(target=serial_run_loop, args=(serial_device, blacklist,))
        serial_thread.start()

        # Make sure to draw the UI the first time even if there is no serial data
        should_redraw.set()

        # Start the main loop
        curses.wrapper(main, serial_thread)
    finally:
        # Cleanly stop serial thread before exiting
        if serial_thread:
            stop_serial.set()

            if serial_device:
                serial_device.close()

            serial_thread.join()

            # If the thread returned an exception, print it
            if thread_exception:
                traceback.print_exception(*thread_exception)
                sys.stderr.flush()

if __name__ == '__main__':
    run()
