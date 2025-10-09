import sys
import time
import logging
import hid
from enum import IntEnum
from functools import wraps


def requires_device(func):
    """Decorator to ensure an HID device is attached before calling the method."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.device:
            logging.warning("No device attached.")
            return False
        return func(self, *args, **kwargs)
    return wrapper

class Param(IntEnum):
    """HID byte interpretations from the rWave device."""
    CMD_CODE = 0 # byte 0, command code
    DC_OFFS_0 = 1 # byte 1, 16 bit dc offset (lsb)
    DC_OFFS_1 = 2 # byte 2, 16 bit dc offset (msb)
    NPERW1_0 = 3 # byte 3, duration in whole number of FTW1 periods (lsb)
    NPERW1_1 = 4 # byte 4
    NPERW1_2 = 5 # byte 5
    NPERW1_3 = 6 # byte 6, duration in whole number of FTW1 periods (msb)
    FTW1_0 = 7 # byte 7, 32 bit frequency tuning word (lsb), channel 1
    FTW1_1 = 8 # byte 8, ,,
    FTW1_2 = 9 # byte 9, ,,
    FTW1_3 = 10 # byte 10, 32 bit frequency tuning word (msb), channel 1
    PH1_0 = 11 # byte 11, 16 bit phase offset (lsb), channel 1
    PH1_1 = 12 # byte 12, 16 bit phase offset (msb), channel 1
    AMPL1_0 = 13 # byte 13, 12 bit amplitude (lsb), channel 1
    AMPL1_1 = 14 # byte 14, 12 bit amplitude (msb), channel 1
    FTW2_0 = 15 # byte 15, 32 bit frequency tuning word (lsb), channel 2
    FTW2_1 = 16 # byte 16, ,,
    FTW2_2 = 17 # byte 17, ,,
    FTW2_3 = 18 # byte 18, 32 bit frequency tuning word (msb), channel 2
    PH2_0 = 19 # byte 19, 16 bit phase offset (lsb), channel 2
    PH2_1 = 20 # byte 20, 16 bit phase offset (msb), channel 2
    AMPL2_0 = 21 # byte 21, 12 bit amplitude (lsb), channel 2
    AMPL2_1 = 22 # byte 22, 12 bit amplitude (msb), channel 2
    MIDX2_0 = 23 # byte 23, 16 bit modulation index (lsb), channel 2
    MIDX2_1 = 24 # byte 24, 16 bit modulation index (msb), channel 2
    PH2_START_0 = 25 # byte 25, 16 bit start phase (lsb) for channel 2 in units of PH1
    PH2_START_1 = 26 # byte 26, 16 bit start phase (msb) for channel 2 in units of PH1
    PH2_STOP_0 = 27 # byte 27, 16 bit stop phase (lsb) for channel 2 in units of PH1
    PH2_STOP_1 = 28 # byte 28, 16 bit stop phase (msb) for channel 2 in units of PH1
    FTW3_0 = 29 # byte 29, 32 bit frequency tuning word (lsb), channel 3
    FTW3_1 = 30 # byte 30, ,,
    FTW3_2 = 31 # byte 31, ,,
    FTW3_3 = 32 # byte 32, 32 bit frequency tuning word (msb), channel 3
    PH3_0 = 33 # byte 33, 16 bit phase offset (lsb), channel 3
    PH3_1 = 34 # byte 34, 16 bit phase offset (msb), channel 3
    AMPL3_0 = 35 # byte 35, 12 bit amplitude (lsb), channel 3
    AMPL3_1 = 36 # byte 36, 12 bit amplitude (msb), channel 3
    MIDX3_0 = 37 # byte 37, 16 bit modulation index (lsb), channel 3
    MIDX3_1 = 38 # byte 38, 16 bit modulation index (msb), channel 3
    PH3_START_0 = 39 # byte 39, 16 bit start phase (lsb) for channel 3 in units of PH1
    PH3_START_1 = 40 # byte 40, 16 bit start phase (msb) for channel 3 in units of PH1
    PH3_STOP_0 = 41 # byte 41, 16 bit stop phase (lsb) for channel 3 in units of PH1
    PH3_STOP_1 = 42 # byte 42, 16 bit stop phase (msb) for channel 3 in units of PH1		
    INV_OUTP = 43 # byte 43, 0=normal, 1=inverted output polarity
    ENVELOPE = 44 # byte 44, 0=additive, 1=modulation
    RAMP_PROFILE = 45 # byte 45, 0=linear, 1=
    TRAMP_SEC = 46 # byte 46, ramping in whole seconds. 0=no ramping.    
    
class Command(IntEnum):
    """HID command codes for the rWave device."""
    WAVE_STOP = 0
    WAVE_START = 1


class RemoteWave:
    """Class for communicating with the rWave device over HID."""

    RX_BUF_SIZE = 64    # bytes
    RX_TIME_OUT = 20    # ms
    HZ = 10000    # system sample rate in Hz

    FREQ_MIN = 0    # frequency range
    FREQ_MAX = 200
    PHASE_MIN = 0    # phase range
    PHASE_MAX = 360
    AMPL_MIN = 0    # amplitude [mA]
    AMPL_MAX = 4.0
    CURR_MIN = -4.0    # output current [mA]
    CURR_MAX = 4.0
    MDEPTH_MIN = 0
    MDEPTH_MAX = 100.0
    RMPINTERV_MIN = 0
    RMPINTERV_MAX = 255

    def __init__(self, log_level: int = logging.CRITICAL):
        """Initialize rWave."""
        self.device: hid.device | None = None
        self.hid_out_pkg: list[int] = [0x00] * 64
        logging.basicConfig(stream=sys.stderr, level=log_level)

    # -------------------------------------------------------------------------
    # DEVICE MANAGEMENT
    # -------------------------------------------------------------------------

    def scan(self, matching_key="TinyUSB Device"):
        """Scan for plugged-in rWave devices.

        Args:
            matching_key (str): Substring to match in product name.

        Returns:
            list[dict]: Matching HID device info.
        """
        devices = hid.enumerate()
        found = [
            d for d in devices
            if matching_key.lower() in (d.get("product_string") or "").lower()
        ]
        for d in found:
            logging.info(
                "Device found: %s (s/n: %s)",
                d.get("product_string"), d.get("serial_number")
            )
        return found

    def attach(self, matching_key="TinyUSB Device"):
        """Attach rWave device by matching part of its product name."""
        for d in hid.enumerate():
            if matching_key.lower() in (d.get("product_string") or "").lower():
                try:
                    self.device = hid.device()
                    self.device.open_path(d["path"])
                    self.device.set_nonblocking(True)
                    logging.info("Attached device: %s (s/n: %s)",
                                 d.get("product_string"), d.get("serial_number"))
                    return True
                except IOError as e:
                    logging.error("Failed to attach device: %s", e)
                    return False
        logging.warning("No device matches the product name '%s'", matching_key)
        return False

    def attach_id(self, path):
        """Attach rWave device by matching its unique path."""
        for d in hid.enumerate():
            if path in d["path"]:
                try:
                    self.device = hid.device()
                    self.device.open_path(d["path"])
                    self.device.set_nonblocking(True)
                    logging.info("Attached device: %s (s/n: %s)",
                                 d.get("product_string"), d.get("serial_number"))
                    return True
                except IOError as e:
                    logging.error("Failed to attach device: %s", e)
                    return False
        logging.warning("No device found with matching path.")
        return False

    @requires_device
    def close(self):
        """Close the currently attached rWave device."""
        self.device.close()
        logging.info("rWave successfully detached.")
        return True

    @requires_device
    def wait_for_ack(self, timeout_ms):
        """Wait for incoming packet based on polling.

        Args:
            timeout_ms (int | None): Timeout in ms (None = infinite).

        Returns:
            tuple[int, int]: (event_code, elapsed_ms) or (-1, elapsed_ms) on timeout.
        """
        t_start = time.time()
        # Poll for event
        while True:
            last_event = self.device.read(self.RX_BUF_SIZE, self.RX_TIME_OUT)
            t_elapsed = int((time.time() - t_start) * 1000)

            if last_event and (last_event[0] == 0xAA):
                return last_event, t_elapsed

            if timeout_ms is not None and t_elapsed >= timeout_ms:
                return -1, t_elapsed

    # -------------------------------------------------------------------------
    # DATA I/O METHODS
    # -------------------------------------------------------------------------

    @requires_device
    def _send_pkg(self):
        """Send hid package to device"""
        try:
            self.device.write([0x00] + self.hid_out_pkg) # no Report ID if first byte is zero.
            return True
        except IOError as e:
            logging.error("Error sending data: %s", e)
            return False

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS (PRIVATE)
    # -------------------------------------------------------------------------

    def _set_8bit_param(self, base: Param, value: int) -> None:
        """Write a single byte into hid_out_pkg (little-endian)."""
        if not (0 <= value < 2**8):
            raise ValueError(f"8-bit value {value} out of range (0..255)")
        self.hid_out_pkg[base] = value & 0xFF

    def _set_12bit_param(self, base: Param, value: int) -> None:
        """Write a 12-bit int into hid_out_pkg (little-endian)."""
        if not (0 <= value < 2**12):
            raise ValueError(f"12-bit value {value} out of range (0..4095)")
        self.hid_out_pkg[base] = value & 0xFF
        self.hid_out_pkg[base + 1] = (value >> 8) & 0x0F

    def _set_16bit_param(self, base: Param, value: int) -> None:
        """Write a 16-bit int into hid_out_pkg (little-endian)."""
        if not (0 <= value < 2**16):
            raise ValueError(f"16-bit value {value} out of range (0..65535)")
        self.hid_out_pkg[base] = value & 0xFF
        self.hid_out_pkg[base + 1] = (value >> 8) & 0xFF

    def _set_32bit_param(self, base: Param, value: int) -> None:
        """Write a 32-bit int into hid_out_pkg (little-endian)."""
        if not (0 <= value < 2**32):
            raise ValueError(f"32-bit value {value} out of range (0..2**32-1)")
        for i, b in enumerate(value.to_bytes(4, "little")):
            self.hid_out_pkg[base + i] = b

    # -------------------------------------------------------------------------
    # PRIVATE LOW-LEVEL SETTERS
    # -------------------------------------------------------------------------
    
    @requires_device
    def _set_cmd_start(self):
        """Set start command"""
        self.hid_out_pkg[Param.CMD_CODE] = Command.WAVE_START

    @requires_device
    def _set_cmd_stop(self):
        """Set stop command"""
        self.hid_out_pkg[Param.CMD_CODE] = Command.WAVE_STOP

    @requires_device
    def _set_dc_offset(self, dc_offset: int) -> None:
        """Set DC offset (16-bit)."""
        self._set_16bit_param(Param.DC_OFFS_0, dc_offset)

    @requires_device
    def _set_wave_number(self, wave_number: int) -> None:
        """Set number of waves to generate (32-bit)."""
        self._set_32bit_param(Param.NPERW1_0, wave_number)

    # --- Wave 1 ---
    @requires_device
    def _set_freq_tuning_word_w1(self, value: int) -> None:
        self._set_32bit_param(Param.FTW1_0, value)

    @requires_device
    def _set_phase_w1(self, value: int) -> None:
        self._set_16bit_param(Param.PH1_0, value)

    @requires_device
    def _set_ampl_w1(self, value: int) -> None:
        self._set_12bit_param(Param.AMPL1_0, value)

    # --- Wave 2 ---
    @requires_device
    def _set_freq_tuning_word_w2(self, value: int) -> None:
        self._set_32bit_param(Param.FTW2_0, value)

    @requires_device
    def _set_phase_w2(self, value: int) -> None:
        self._set_16bit_param(Param.PH2_0, value)

    @requires_device
    def _set_ampl_w2(self, value: int) -> None:
        self._set_12bit_param(Param.AMPL2_0, value)

    @requires_device
    def _set_mod_index_w2(self, value: int) -> None:
        self._set_16bit_param(Param.MIDX2_0, value)        

    @requires_device
    def _set_phase_start_w2(self, value: int) -> None:
        self._set_16bit_param(Param.PH2_START_0, value)

    @requires_device
    def _set_phase_stop_w2(self, value: int) -> None:
        self._set_16bit_param(Param.PH2_STOP_0, value)

    # --- Wave 3 ---
    @requires_device
    def _set_freq_tuning_word_w3(self, value: int) -> None:
        self._set_32bit_param(Param.FTW3_0, value)

    @requires_device
    def _set_phase_w3(self, value: int) -> None:
        self._set_16bit_param(Param.PH3_0, value)

    @requires_device
    def _set_ampl_w3(self, value: int) -> None:
        self._set_12bit_param(Param.AMPL3_0, value)

    @requires_device
    def _set_phase_start_w3(self, value: int) -> None:
        self._set_16bit_param(Param.PH3_START_0, value)

    @requires_device
    def _set_phase_stop_w3(self, value: int) -> None:
        self._set_16bit_param(Param.PH3_STOP_0, value)

    # -------------------------------------------------------------------------
    # PUBLIC WRITERS (HIGH-LEVEL API)
    # -------------------------------------------------------------------------

    @requires_device
    def write_dc_current(self, current: float) -> None:
        """Set dc current in mA's."""
        if not (self.CURR_MIN <= current <= self.CURR_MAX):
            raise ValueError(f"DC-current {current} mA out of range \
                             ({self.CURR_MIN}..{self.CURR_MAX})")
        dac_units = round(511.875*(current+4.0))
        self._set_dc_offset(dac_units)

    @requires_device
    def write_freq_theta(self, frequency: float) -> None:
        """Set frequency for theta wave in Hz."""
        if not (self.FREQ_MIN <= frequency <= self.FREQ_MAX):
            raise ValueError(f"Frequency {frequency} Hz out of range \
                             ({self.FREQ_MIN}..{self.FREQ_MAX})")
        ftw = round(2**32 * frequency / self.HZ)
        self._set_freq_tuning_word_w1(ftw)

    @requires_device
    def write_freq_gamma1(self, frequency: float) -> None:
        """Set frequency for gamma1 wave in Hz."""
        if not (self.FREQ_MIN <= frequency <= self.FREQ_MAX):
            raise ValueError(f"Frequency {frequency} Hz out of range \
                             ({self.FREQ_MIN}..{self.FREQ_MAX})")
        ftw = round(2**32 * frequency / self.HZ)
        self._set_freq_tuning_word_w2(ftw)

    @requires_device
    def write_freq_gamma2(self, frequency: float) -> None:
        """Set frequency for gamma2 wave in Hz."""
        if not (self.FREQ_MIN <= frequency <= self.FREQ_MAX):
            raise ValueError(f"Frequency {frequency} Hz out of range \
                             ({self.FREQ_MIN}..{self.FREQ_MAX})")
        ftw = round(2**32 * frequency / self.HZ)
        self._set_freq_tuning_word_w3(ftw)

    @requires_device
    def write_phase_theta(self, phase_angle: float) -> None:
        """Set phase angle for theta in degrees."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Phase {phase_angle}° out of range \
                             ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_w1(value)

    @requires_device
    def write_phase_gamma1(self, phase_angle: float) -> None:
        """Set phase angle for gamma1 in degrees."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Phase {phase_angle}° out of range \
                             ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_w2(value)

    @requires_device
    def write_phase_gamma2(self, phase_angle: float) -> None:
        """Set phase angle for gamma2 in degrees."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Phase {phase_angle}° out of range \
                             ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_w3(value)

    @requires_device
    def write_start_phase_gamma1(self, phase_angle: float) -> None:
        """Set start phase of gamma1 in degrees of theta."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Start phase {phase_angle}° out of range \
                             ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_start_w2(value)

    @requires_device
    def write_start_phase_gamma2(self, phase_angle: float) -> None:
        """Set start phase of gamma2 in degrees of theta."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Start phase {phase_angle}° out of range \
                             ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_start_w3(value)

    @requires_device
    def write_stop_phase_gamma1(self, phase_angle: float) -> None:
        """Set stop phase of gamma1 in degrees of theta."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Stop phase {phase_angle}° out of range \
                             ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_stop_w2(value)

    @requires_device
    def write_stop_phase_gamma2(self, phase_angle: float) -> None:
        """Set stop phase of gamma2 in degrees of theta."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Stop phase {phase_angle}° out of range \
                             ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_stop_w3(value)

    @requires_device
    def write_ampl_theta(self, amplitude: float) -> None:
        """Set the theta current amplitude in mA's."""
        if not (self.AMPL_MIN <= amplitude <= self.AMPL_MAX):
            raise ValueError(f"theta wave amplitude {amplitude} mA out of range \
                             ({self.AMPL_MIN}..{self.AMPL_MAX})")
        dac_units = round(511.75*(amplitude))
        self._set_ampl_w1(dac_units)

    @requires_device
    def write_ampl_gamma1(self, amplitude: float) -> None:
        """Set the gamma1 current amplitude in mA's."""
        if not (self.AMPL_MIN <= amplitude <= self.AMPL_MAX):
            raise ValueError(f"gamma1 wave amplitude {amplitude} mA out of range \
                             ({self.AMPL_MIN}..{self.AMPL_MAX})")
        dac_units = round(511.75*(amplitude))
        self._set_ampl_w2(dac_units)

    @requires_device
    def write_ampl_gamma2(self, amplitude: float) -> None:
        """Set the gamma2 current amplitude in mA's."""
        if not (self.AMPL_MIN <= amplitude <= self.AMPL_MAX):
            raise ValueError(f"gamma2 wave amplitude {amplitude} mA out of range \
                             ({self.AMPL_MIN}..{self.AMPL_MAX})")
        dac_units = round(511.75*(amplitude))
        self._set_ampl_w3(dac_units)

    @requires_device
    def write_mdepth_gamma1(self, mod_depth: float) -> None:
        """Set the gamma1 modulation depth in %."""
        if not (self.MDEPTH_MIN <= mod_depth <= self.MDEPTH_MAX):
            raise ValueError(f"gamma1 modulation depth {mod_depth} % out of range \
                             ({self.MDEPTH_MIN}..{self.MDEPTH_MAX})")
        dac_units = round(655.35*(mod_depth))
        self._set_mod_index_w2(dac_units)

    @requires_device
    def write_mdepth_gamma2(self, mod_depth: float) -> None:
        """Set the gamma2 modulation depth in %."""
        if not (self.MDEPTH_MIN <= mod_depth <= self.MDEPTH_MAX):
            raise ValueError(f"gamma2 modulation depth {mod_depth} % out of range \
                             ({self.MDEPTH_MIN}..{self.MDEPTH_MAX})")
        mod_index = round(655.35*(mod_depth))
        self._set_mod_index_w2(mod_index)

    @requires_device
    def write_ramping_interval(self, t_ramp: float) -> None:
        """Set the ramping interval in seconds."""
        if not (self.RMPINTERV_MIN <= t_ramp <= self.RMPINTERV_MAX):
            raise ValueError(f"time intrerval {t_ramp} % out of range \
                             ({self.RMPINTERV_MIN}..{self.RMPINTERV_MAX})")
        self._set_8bit_param(Param.TRAMP_SEC, round(t_ramp))

    # --- Control ---
    @requires_device
    def set_output_mode(self, invert: int) -> None:
        """Set output to normal or inverted. Only ac-components are inverted."""
        if invert not in (0, 1):
            raise ValueError("invert must be 0 (normal) or 1 (inverted)")
        self.hid_out_pkg[Param.INV_OUTP] = invert

    @requires_device
    def set_composition(self, envelope: int) -> None:
        """Set wave composition to additive or modulation."""
        if envelope not in (0, 1):
            raise ValueError("envelope must be 0 (additive) or 1 (modulation)")
        self.hid_out_pkg[Param.ENVELOPE] = envelope

    @requires_device
    def set_ramping_profile(self, profile: int) -> None:
        """Set ramping profile."""
        if profile not in (0, 1):
            raise ValueError("ramping_profile 0=no ramping, 1=linear ramping, 2=")
        self.hid_out_pkg[Param.RAMP_PROFILE] = profile

    @requires_device
    def start(self):
        """Set start command and send package out."""
        self._set_cmd_start()
        self._send_pkg()

    @requires_device
    def stop(self):
        """Set stop command and send package out."""
        self._set_cmd_stop()
        self._send_pkg()
