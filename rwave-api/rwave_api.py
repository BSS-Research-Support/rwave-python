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
    AMPL1_0 = 13 # byte 13, 16 bit amplitude (lsb), channel 1
    AMPL1_1 = 14 # byte 14, 16 bit amplitude (msb), channel 1
    FTW2_0 = 15 # byte 15, 32 bit frequency tuning word (lsb), channel 2
    FTW2_1 = 16 # byte 16, ,,
    FTW2_2 = 17 # byte 17, ,,
    FTW2_3 = 18 # byte 18, 32 bit frequency tuning word (msb), channel 2
    PH2_0 = 19 # byte 19, 16 bit phase offset (lsb), channel 2
    PH2_1 = 20 # byte 20, 16 bit phase offset (msb), channel 2
    AMPL2_0 = 21 # byte 21, 16 bit amplitude (lsb), channel 2
    AMPL2_1 = 22 # byte 22, 16 bit amplitude (msb), channel 2
    PH2_START_0 = 23 # byte 23, 16 bit start phase (lsb) for channel 2 in units of PH1
    PH2_START_1 = 24 # byte 24, 16 bit start phase (msb) for channel 2 in units of PH1
    PH2_STOP_0 = 25 # byte 25, 16 bit stop phase (lsb) for channel 2 in units of PH1
    PH2_STOP_1 = 26 # byte 26, 16 bit stop phase (msb) for channel 2 in units of PH1
    FTW3_0 = 27 # byte 27, 32 bit frequency tuning word (lsb), channel 3
    FTW3_1 = 28 # byte 28
    FTW3_2 = 29 # byte 29
    FTW3_3 = 30 # byte 30, 32 bit frequency tuning word (msb), channel 3
    PH3_0 = 31 # byte 31, 16 bit phase offset (lsb), channel 3
    PH3_1 = 32 # byte 32, 16 bit phase offset (msb), channel 3
    AMPL3_0 = 33 # byte 33, 16 bit amplitude (lsb), channel 3
    AMPL3_1 = 34 # byte 34, 16 bit amplitude (msb), channel 3
    PH3_START_0 = 35 # byte 35, 16 bit start phase (lsb) for channel 3 in units of PH1
    PH3_START_1 = 36 # byte 36, 16 bit start phase (msb) for channel 3 in units of PH1
    PH3_STOP_0 = 37 # byte 37, 16 bit stop phase (lsb) for channel 3 in units of PH1
    PH3_STOP_1 = 38 # byte 38, 16 bit stop phase (msb) for channel 3 in units of PH1		
    INV_OUTP = 39 # byte 39, 0=normal, 1=inverted output polarity
    ENVELOPE = 40 # byte 40, 0=additive, 1=modulation
    RAMP_PROFILE = 41 # byte 41, 0=linear, 1=
    NRAMP_PER = 42 # byte 42, ramping in whole number of channel 1 periods, 0 is no ramping.    
    
class Command(IntEnum):
    """HID command codes for the rWave device."""
    WAVE_STOP = 0
    WAVE_START = 1


class rWave:
    """Class for communicating with the rWave device over HID."""

    RX_BUF_SIZE = 64  # bytes
    RX_TIME_OUT = 20  # ms
    HZ = 10000        # system sample rate in Hz

    FREQ_MIN = 0      # frequency range
    FREQ_MAX = 200
    PHASE_MIN = 0     # phase range
    PHASE_MAX = 360
    AMPL_MIN = 0
    AMPL_MAX = 4095

    def __init__(self, log_level: int = logging.CRITICAL):
        """Initialize rWave."""
        self.device: hid.device | None = None
        self.hid_out_pkg: list[int] = [0x00] * 64
        logging.basicConfig(stream=sys.stderr, level=log_level)

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS (PRIVATE)
    # -------------------------------------------------------------------------

    def _set_16bit_param(self, base: Param, value: int) -> None:
        """Write a 16-bit int into hid_out_pkg (little-endian)."""
        if not (0 <= value < 2**16):
            raise ValueError(f"16-bit value {value} out of range (0..65535)")
        self.hid_out_pkg[base] = value & 0xFF
        self.hid_out_pkg[base + 1] = (value >> 8) & 0xFF

    def _set_12bit_param(self, base: Param, value: int) -> None:
        """Write a 12-bit int into hid_out_pkg (little-endian)."""
        if not (0 <= value < 2**12):
            raise ValueError(f"12-bit value {value} out of range (0..4095)")
        self.hid_out_pkg[base] = value & 0xFF
        self.hid_out_pkg[base + 1] = (value >> 8) & 0x0F

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

    # --- Misc ---
    @requires_device
    def _set_invert_output(self, invert: int) -> None:
        if invert not in (0, 1):
            raise ValueError("invert must be 0 (normal) or 1 (inverted)")
        self.hid_out_pkg[Param.INV_OUTP] = invert

    @requires_device
    def _set_envelope(self, envelope: int) -> None:
        if envelope not in (0, 1):
            raise ValueError("envelope must be 0 (additive) or 1 (modulation)")
        self.hid_out_pkg[Param.ENVELOPE] = envelope

    @requires_device
    def _set_ramping_profile(self, profile: int) -> None:
        if profile not in (0, 1):
            raise ValueError("ramping_profile must be 0 (linear) or 1 (...)")
        self.hid_out_pkg[Param.RAMP_PROFILE] = profile

    @requires_device
    def _set_no_ramping_periods(self, periods: int) -> None:
        self._set_16bit_param(Param.NRAMP_PER, periods)

    # -------------------------------------------------------------------------
    # PUBLIC WRITERS (HIGH-LEVEL API)
    # -------------------------------------------------------------------------

    @requires_device
    def write_freq_theta(self, frequency: float) -> None:
        """Set frequency for theta wave in Hz."""
        if not (self.FREQ_MIN <= frequency <= self.FREQ_MAX):
            raise ValueError(f"Frequency {frequency} Hz out of range ({self.FREQ_MIN}..{self.FREQ_MAX})")
        ftw = round(2**32 * frequency / self.HZ)
        self._set_freq_tuning_word_w1(ftw)

    @requires_device
    def write_freq_gamma1(self, frequency: float) -> None:
        """Set frequency for gamma1 wave in Hz."""
        if not (self.FREQ_MIN <= frequency <= self.FREQ_MAX):
            raise ValueError(f"Frequency {frequency} Hz out of range ({self.FREQ_MIN}..{self.FREQ_MAX})")
        ftw = round(2**32 * frequency / self.HZ)
        self._set_freq_tuning_word_w2(ftw)

    @requires_device
    def write_freq_gamma2(self, frequency: float) -> None:
        """Set frequency for gamma2 wave in Hz."""
        if not (self.FREQ_MIN <= frequency <= self.FREQ_MAX):
            raise ValueError(f"Frequency {frequency} Hz out of range ({self.FREQ_MIN}..{self.FREQ_MAX})")
        ftw = round(2**32 * frequency / self.HZ)
        self._set_freq_tuning_word_w3(ftw)

    def write_phase_theta(self, phase_angle: float) -> None:
        """Set phase angle for theta in degrees."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Phase {phase_angle}° out of range ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_w1(value)

    def write_phase_gamma1(self, phase_angle: float) -> None:
        """Set phase angle for gamma1 in degrees."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Phase {phase_angle}° out of range ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_w2(value)

    def write_phase_gamma2(self, phase_angle: float) -> None:
        """Set phase angle for gamma2 in degrees."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Phase {phase_angle}° out of range ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_w3(value)

    def write_start_phase_gamma1(self, phase_angle: float) -> None:
        """Set start phase of gamma1 in degrees of theta."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Start phase {phase_angle}° out of range ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_start_w2(value)

    def write_start_phase_gamma2(self, phase_angle: float) -> None:
        """Set start phase of gamma2 in degrees of theta."""
        if not (self.PHASE_MIN <= phase_angle <= self.PHASE_MAX):
            raise ValueError(f"Start phase {phase_angle}° out of range ({self.PHASE_MIN}..{self.PHASE_MAX})")
        value = round(phase_angle * (2**16 / 360.0))
        self._set_phase_start_w3(value)
