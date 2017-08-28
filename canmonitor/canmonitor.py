#!/usr/bin/env python3

import argparse
import curses
import sys
import threading
import traceback

from .source_handler import CandumpHandler, InvalidFrame, SerialHandler


should_redraw = threading.Event()
stop_reading = threading.Event()

can_messages = {}
can_messages_lock = threading.Lock()

thread_exception = None


def reading_loop(source_handler, blacklist):
    """Background thread for reading."""
    try:
        while not stop_reading.is_set():
            try:
                frame_id, data = source_handler.get_message()
            except InvalidFrame:
                continue
            except EOFError:
                break

            if frame_id in blacklist:
                continue

            # Add the frame to the can_messages dict and tell the main thread to refresh its content
            with can_messages_lock:
                can_messages[frame_id] = data
                should_redraw.set()

        stop_reading.wait()

    except:
        if not stop_reading.is_set():
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


def main(stdscr, reading_thread):
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

            # Make sure we don't read the can_messages dict while it's being written to in the reading thread
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
        if c == ord('q') or not reading_thread.is_alive():
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
    parser = argparse.ArgumentParser(description='Process CAN data from a serial device or from a file.')
    parser.add_argument('serial_device', type=str, nargs='?')
    parser.add_argument('baud_rate', type=int, default=115200, nargs='?',
                        help='Serial baud rate in bps (default: 115200)')
    parser.add_argument('-f', '--candump-file', metavar='CANDUMP_FILE', help="File (of 'candump' format) to read from")

    parser.add_argument('--blacklist', '-b', nargs='+', metavar='BLACKLIST', help="Ids that must be ignored")
    parser.add_argument(
        '--blacklist-file',
        '-bf',
        metavar='BLACKLIST_FILE',
        help="File containing ids that must be ignored",
    )

    args = parser.parse_args()

    # checks arguments
    if not args.serial_device and not args.candump_file:
        print("Please specify serial device or file name")
        print()
        parser.print_help()
        return
    if args.serial_device and args.candump_file:
        print("You cannot specify a serial device AND a file name")
        print()
        parser.print_help()
        return

    # --blacklist-file prevails over --blacklist
    if args.blacklist_file:
        with open(args.blacklist_file) as f_obj:
            blacklist = parse_ints(f_obj)
    elif args.blacklist:
        blacklist = parse_ints(args.blacklist)
    else:
        blacklist = set()

    if args.serial_device:
        source_handler = SerialHandler(args.serial_device, baudrate=args.baud_rate)
    elif args.candump_file:
        source_handler = CandumpHandler(args.candump_file)

    reading_thread = None

    try:
        # If reading from a serial device, it will be opened with timeout=0 (non-blocking read())
        source_handler.open()

        # Start the reading background thread
        reading_thread = threading.Thread(target=reading_loop, args=(source_handler, blacklist,))
        reading_thread.start()

        # Make sure to draw the UI the first time even if no data has been read
        should_redraw.set()

        # Start the main loop
        curses.wrapper(main, reading_thread)
    finally:
        # Cleanly stop reading thread before exiting
        if reading_thread:
            stop_reading.set()

            if source_handler:
                source_handler.close()

            reading_thread.join()

            # If the thread returned an exception, print it
            if thread_exception:
                traceback.print_exception(*thread_exception)
                sys.stderr.flush()

if __name__ == '__main__':
    run()
