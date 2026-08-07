# /home/klipper/klipper/klippy/extras/position_logger.py

import logging
import threading
import time
import os
import json
from datetime import datetime


class PlrLogger:
    def __init__(self, config):
        self.printer = config.get_printer() # Get main printer object
        name = config.get_name()
        self.name = 'plr_logger' # Config section name, must match what you have in your printer.cfg
        self.log_file = config.get('log_file', default='/home/klipper/printer_data/config/plr_resume/printer_state/printer_state.json') # Get printer state file location
        self.interval = config.getfloat('interval', default=5.0, above=0.0) # Default logging interval

        # Make log dir if it doesnt exist
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        self.reactor = self.printer.get_reactor() # Get reactor event system loop

        self.toolhead = None
        self.extruder = None
        self.heater_bed = None
        self.fan = None
        self.temperature_fan_name = config.get('temperature_fan_name', default=None)
        self.virtual_sdcard = None

        self.running = False
        self.sample_timer = None
        self.write_thread = None
        self.latest_data = None
        self.data_lock = threading.Lock()
        self.has_new_data = threading.Event()

        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.printer.register_event_handler("klippy:shutdown", self._shutdown)

        logging.info("PLR position logger [%s] initialized, waiting for ready", self.name)

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def _handle_ready(self):
        # Get required printer objects – abort if any are missing
        try:
            self.toolhead = self.printer.lookup_object('toolhead')
            self.extruder = self.printer.lookup_object('extruder')
            self.heater_bed = self.printer.lookup_object('heater_bed')
            self.virtual_sdcard = self.printer.lookup_object('virtual_sdcard')
        except Exception:
            logging.exception("plr_logger [%s] failed to get required printer objects", self.name)
            return

        # Optional standard fan – may not exist on all printers
        try:
            self.fan = self.printer.lookup_object('fan')
        except self.printer.config_error:
            self.fan = None
            logging.info("plr_logger [%s] no fan object found", self.name)

        # Optional temperature fan – only if a name was given in the config
        if self.temperature_fan_name is not None:
            try:
                self.temperature_fan = self.printer.lookup_object(
                    f'temperature_fan {self.temperature_fan_name}'
                )
            except self.printer.config_error:
                self.temperature_fan = None
                logging.warning(
                    "plr_logger [%s] temperature_fan %s not found – skipping",
                    self.name, self.temperature_fan_name
                )
        else:
            self.temperature_fan = None

        # Start the background writer thread
        self.running = True
        self.write_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.write_thread.start()

        # Schedule the first data collection immediately, then repeat at `interval`
        self.sample_timer = self.reactor.register_timer(
            self._sample_timer, self.reactor.NOW
        )

        logging.info(
            "plr_logger [%s] logging every %.1fs to %s",
            self.name, self.interval, self.log_file
        )

    # ------------------------------------------------------------------
    # Data collection (runs on the reactor thread)
    # ------------------------------------------------------------------

    def _get_status(self, obj, label):
        """Fetch get_status() from a printer object, logging on failure."""
        if obj is None:
            return {}
        try:
            return obj.get_status(self.reactor.monotonic())
        except Exception:
            logging.exception("plr_logger [%s] failed reading %s status", self.name, label)
            return {}

    def _collect_data(self):
        # Some of these are unused but feel free to uncomment them and add them if needed
        # Gather all statuses with safe defaults
        toolhead_status = self._get_status(self.toolhead, 'toolhead') if self.toolhead else {}
        extruder_status = self._get_status(self.extruder, 'extruder') if self.extruder else {}
        bed_status = self._get_status(self.heater_bed, 'heater_bed') if self.heater_bed else {}
        print_status = self._get_status(self.virtual_sdcard, 'virtual_sdcard') if self.virtual_sdcard else {}
        pos = toolhead_status.get('position', [0.0, 0.0, 0.0, 0.0])

        # Optional standard fan
        fan_status = {}
        if self.fan is not None:
            fan_status = self._get_status(self.fan, 'fan')

        # Optional temperature fan (if configured)
        exhaust_status = {}
        if self.temperature_fan is not None and self.temperature_fan_name:
            exhaust_status = self._get_status(self.temperature_fan, f'temperature_fan {self.temperature_fan_name}')

        # Build the data dictionary
        data = {
            "timestamp": datetime.now().isoformat(),
            "timestamp_unix": time.time(),
            "toolhead": {
                "position": {
                    "x": pos[0],
                    "y": pos[1],
                    "z": pos[2],
                    "e": pos[3] if len(pos) > 3 else 0.0,
                },
                "homed_axes": toolhead_status.get('homed_axes', ''),
                "max_velocity": toolhead_status.get('max_velocity', 0),
                "max_accel": toolhead_status.get('max_accel', 0),
                "print_time": toolhead_status.get('print_time', 0),
            },
            "extruder": {
                "temperature": extruder_status.get('temperature', 0.0),
                "target": extruder_status.get('target', 0.0),
            },
            "heater_bed": {
                "temperature": bed_status.get('temperature', 0.0),
                "target": bed_status.get('target', 0.0),
            },
            "fan": {
                "speed": fan_status.get('speed', 0.0)
            },
            "print": {
                "is_printing": print_status.get('is_active', False),
                "file_position": print_status.get('file_position', 0),
                "file_path": print_status.get('file_path', ''),
                "file_size": print_status.get('file_size', 0),
                "progress": print_status.get('progress', 0.0),
            },
        }

        # Append temperature_fan to data if it exists
        if self.temperature_fan is not None and self.temperature_fan_name:
            data["temperature_fan"] = {
                "temperature": exhaust_status.get('temperature', 0.0),
                "target": exhaust_status.get('target', 0.0),
            }

        return data

    def _sample_timer(self, eventtime):
        try:
            data = self._collect_data()
            is_printing = data['print']['is_printing']

            with self.data_lock:
                if is_printing:
                    self.latest_data = data
                    self.has_new_data.set()
                elif self.latest_data is not None:
                    self.latest_data = None
                    self.has_new_data.clear()

            if is_printing:
                logging.debug("plr_logger [%s] progress=%.2f",
                            self.name, data['print']['progress'])
        except Exception:
            logging.exception("plr_logger [%s] error in sample timer", self.name)

        return self.reactor.monotonic() + self.interval

    # ------------------------------------------------------------------
    # File I/O (runs on the write thread)
    # ------------------------------------------------------------------

    def _atomic_write(self, data):
        temp_file = self.log_file + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)   # data is a dict, serializes to JSON
        os.rename(temp_file, self.log_file)

    def _write_loop(self):
        consecutive_failures = 0
        max_backoff = 30.0

        while self.running:
            if not self.has_new_data.wait(timeout=1.0):
                continue
            if not self.running:
                break

            with self.data_lock:
                data = self.latest_data
                self.has_new_data.clear()

            if data is None:
                continue

            try:
                self._atomic_write(data)
                consecutive_failures = 0
            except Exception:
                consecutive_failures += 1
                logging.exception("plr_logger [%s] write error (failure #%d)",
                                   self.name, consecutive_failures)
                temp_file = self.log_file + ".tmp"
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
                if consecutive_failures >= 3:
                    backoff = min(max_backoff, 2 ** consecutive_failures)
                    logging.warning("plr_logger [%s] backing off %.0fs after repeated failures",
                                     self.name, backoff)
                    time.sleep(backoff)

        logging.debug("plr_logger [%s] write loop exited", self.name)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _shutdown(self):
        logging.info("plr_logger [%s] shutting down", self.name)
        self.running = False

        if self.sample_timer is not None:
            self.reactor.unregister_timer(self.sample_timer)
            self.sample_timer = None

        with self.data_lock:
            final_data = self.latest_data

        if final_data is not None:
            try:
                self._atomic_write(final_data)
                logging.info("plr_logger [%s] wrote final data on shutdown", self.name)
            except Exception:
                logging.exception("plr_logger [%s] failed to write final data", self.name)

        self.has_new_data.set()  # wake the write thread so it can exit
        if self.write_thread is not None and self.write_thread.is_alive():
            self.write_thread.join(timeout=2.0)
            if self.write_thread.is_alive():
                logging.warning("plr_logger [%s] write thread did not exit cleanly", self.name)

        logging.info("plr_logger [%s] shutdown complete", self.name)


def load_config(config):
    return PlrLogger(config)
