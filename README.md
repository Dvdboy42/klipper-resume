# klipper-resume
Adds the ability to recover a print after a firmware shutdown or complete power loss, using a single command

# Where to put everything
I would suggest making a folder in your config called plr_resume
(can be named anything but make sure to change the default file paths in the scripts)

plr_resume.py, resume_gcode.cfg  -  /printer_data/config/plr_resume
(dont forget to include resume_gcode.cfg, add "[include plr_resume/resume_gcode.cfg]" into printer.cfg

plr_logger.py (logger, not resume)  -  /klipper/klippy/extras


# Todo soon™
- better defaults
- adaptive byte offset (based on print speed, speed multiplier, gcode resolution)
- settings documentation 
- more flexible parameter management (ex: various fans)
- install script
