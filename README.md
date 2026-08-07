# klipper_plr_resume
Adds the ability to recover a print after a firmware shutdown or complete power loss, using a single command

# Where to put everything
I would suggest making a folder in your config called plr_resume
(can be named anything but make sure to change the default file paths in the scripts)

**plr_resume.py**, **resume_gcode.cfg**  -  /printer_data/config/**plr_resume**

(dont forget to include resume_gcode.cfg, add `[include plr_resume/resume_gcode.cfg]` to printer.cfg)

**plr_logger.py** (logger, not resume)  -  /klipper/klippy/extras


# Usage
After a power loss, simply run the `PLR_RESUME` macro.

# How it works
While a print is running, `plr_logger.py` saves the current state of the printer in a p`rinter_state.json` file on every interval, configured in seconds.

`plr_resume.py` truncates the file that was previously printing using the information in the `printer_state.json` file. It also prepends the `PLR_RESUME_START_GCODE` macro and parses parameters from the printer_state file to it.

When running `PLR_RESUME`, it first triggers `plr_resume.py` and then starts printing the truncated file.
The `PLR_RESUME_START_GCODE` macro can be very easily edited to fit your needs. Whatever is inside runs before the actual print, similar to a `PRINT_START` macro, but specific to recovery.

# Todo soon™
- better defaults
- adaptive byte offset (based on print speed, speed multiplier, gcode resolution)
- settings documentation 
- more flexible parameter management (ex: various fans)
- install script

# Feel free to contribute!
If you have any ideas, please consider adding an issue, be it a bug or a suggestion, or directly submit a PR.

# Use of AI
AI was used in the making of this code, but mostly because of my lack of syntax knowledge (and laziness)

Almost all of the logic was thought out by me
