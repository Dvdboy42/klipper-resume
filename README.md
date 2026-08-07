# klipper_plr_resume
Adds the ability to recover a print after a firmware shutdown or complete power loss, using a single command

# Where to put everything
I would suggest making a folder in your config called plr_resume
(can be named anything but make sure to change the default file paths in the scripts)

**plr_resume.py**, **resume_gcode.cfg**  -  /printer_data/config/**plr_resume**

(dont forget to include resume_gcode.cfg, add `[include plr_resume/resume_gcode.cfg]` to printer.cfg)

**plr_logger.py** (logger, not resume)  -  /klipper/klippy/extras


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
