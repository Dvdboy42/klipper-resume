#!/usr/bin/env python3
"""
plr_resume.py - Prepare a resume-ready gcode file after power loss.

Reads the PositionLogger state JSON, truncates the original gcode file
to the last known position, and prepends a RESUME_PRINT macro call
with the saved position/temp/fan values. The result is written directly
into the gcodes folder under a fixed filename, so a macro can
immediately print it without the user picking a file.
If a previous recovery file already exists, it is backed up first.
The original gcode file is never modified.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime

# ---------------------------------------------------------------------
# Editable defaults
# ---------------------------------------------------------------------

STATE_FILE = "/home/klipper/printer_data/config/plr_resume/printer_state/printer_state.json"
GCODES_DIR = "/home/klipper/printer_data/gcodes"
OFFSET = 1000
READ_CHUNK_SIZE = 65536
COPY_CHUNK_SIZE = 1024 * 1024
OUTPUT_FILENAME = "plr_recovery.gcode" # MUST match what you set at the end of your resume gcode macro under RESUME_GCODE_MACRO_NAME
RESUME_GCODE_MACRO_NAME = "PLR_RESUME_START_GCODE" # MUST match
BACKUP_DIR = "/home/klipper/printer_data/gcodes/plr_backups"

# ---------------------------------------------------------------------


def find_next_line_start(f, position, file_size):
    """Return the byte offset of the start of the next complete line
    at or after `position`. If already at a line boundary, returns it
    unchanged."""
    if position <= 0:
        return 0
    if position >= file_size:
        return file_size

    f.seek(position - 1)
    if f.read(1) == b'\n':
        return position

    f.seek(position)
    offset = position
    while True:
        chunk = f.read(READ_CHUNK_SIZE)
        if not chunk:
            return file_size
        idx = chunk.find(b'\n')
        if idx != -1:
            return offset + idx + 1
        offset += len(chunk)


def backup_existing(output_file, backup_dir):
    """If a previous recovery file exists, move it aside with a
    timestamped name before it gets overwritten."""
    if not os.path.isfile(output_file):
        return None

    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(os.path.basename(output_file))
    backup_path = os.path.join(backup_dir, f"{base}_{stamp}{ext}")
    shutil.move(output_file, backup_path)
    return backup_path


def main():
    parser = argparse.ArgumentParser(
        description="Truncate a gcode file to the last known print position "
                     "and prepend a gcode macro call, for power-loss recovery."
    )
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')
    args = parser.parse_args()

    state_file = STATE_FILE
    output_dir = GCODES_DIR
    offset = OFFSET

    if not os.path.isfile(state_file):
        sys.exit(f"Error: log file not found: {state_file}")

    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)

    print_info = state.get('print', {})
    file_position = print_info.get('file_position')
    file_path = print_info.get('file_path')

    if file_position is None:
        sys.exit(f"Error: 'print.file_position' missing in {state_file}")
    if not file_path:
        sys.exit(f"Error: 'print.file_path' missing in {state_file}")
    if not os.path.isfile(file_path):
        sys.exit(f"Error: input gcode file not found: {file_path}")

    toolhead = state['toolhead']
    pos = toolhead['position']
    extruder = state['extruder']
    bed = state['heater_bed']

    fan = state.get('fan', {})
    fan_speed = int(fan.get('speed', 0.0) * 255)

    exhaust_fan = state.get('temperature_fan', {})
    exhaust_temp = int(exhaust_fan.get('temperature', 0.0))

    resume_line = (
        f"{RESUME_GCODE_MACRO_NAME} "
        f"X={pos['x']} Y={pos['y']} Z={pos['z']} E={pos['e']} "
        f"BED_TEMP={bed.get('target', 0.0)} "
        f"EXTRUDER_TEMP={extruder.get('target', 0.0)} "
        f"EXHAUST_TEMP={exhaust_temp} "
        f"FAN_SPEED={fan_speed}\n"
    )

    file_size = os.path.getsize(file_path)
    target_position = max(0, min(file_position + offset, file_size))

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, OUTPUT_FILENAME)
    temp_file = output_file + ".tmp"

    # ------------------------------------------------------------
    # 1) Read the input file and write to a temporary file
    # ------------------------------------------------------------
    with open(file_path, 'rb') as f_in:
        start_pos = find_next_line_start(f_in, target_position, file_size)

        if args.verbose:
            print(f"Input file:      {file_path}")
            print(f"File size:       {file_size} bytes")
            print(f"file_position:   {file_position}")
            print(f"Offset applied:  {offset}")
            print(f"Rounded to line: {start_pos}")
            print(f"Output file:     {output_file}")
            print(f"Resume line:     {resume_line.strip()}")

        f_in.seek(start_pos)
        with open(temp_file, 'wb') as f_out:
            f_out.write(resume_line.encode('utf-8'))
            while True:
                chunk = f_in.read(COPY_CHUNK_SIZE)
                if not chunk:
                    break
                f_out.write(chunk)

    # ------------------------------------------------------------
    # 2) Backup any existing recovery file (may be the same as input)
    #    Now it's safe because we already read the input.
    # ------------------------------------------------------------
    backup_path = backup_existing(output_file, BACKUP_DIR)
    if args.verbose and backup_path:
        print(f"Existing recovery file backed up to: {backup_path}")

    # ------------------------------------------------------------
    # 3) Atomically replace the output file with the temp
    # ------------------------------------------------------------
    os.rename(temp_file, output_file)

    output_size = os.path.getsize(output_file)
    print(f"Resume file saved to: {output_file}")
    print(f"Original gcode kept from byte {start_pos} of {file_size} "
          f"({output_size} bytes written, resume line included)")

if __name__ == '__main__':
    main()
