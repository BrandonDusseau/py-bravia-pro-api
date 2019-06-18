import re
from enum import Enum
from .errors import HttpError, BraviaApiError
from .util import coalesce_none_or_empty
from pprint import pprint


# Error code definitions
class ErrorCode(object):
    ILLEGAL_ARGUMENT = 3
    ILLEGAL_STATE = 7
    TARGET_NOT_SUPPORTED = 40800
    VOLUME_OUT_OF_RANGE = 40801


class AudioOutputs(Enum):
    UNKNOWN = 0
    SPEAKER = 1
    SPEAKER_HDMI = 2
    HDMI = 3
    AUDIO_SYSTEM = 4


class TvPosition(Enum):
    UNKNOWN = 0
    TABLE_TOP = 1
    WALL_MOUNT = 2


class SubwooferPhase(Enum):
    UNKNOWN = 0
    NORMAL = 1
    REVERSE = 2


class VolumeDevice(Enum):
    UNKNOWN = 0
    SPEAKERS = 1
    HEADPHONES = 2


class Audio(object):
    def __init__(self, bravia_client, http_client):
        self.bravia_client = bravia_client
        self.http_client = http_client

    def get_sound_settings(self):
        self.bravia_client.initialize()

        try:
            response = self.http_client.request(
                endpoint="audio",
                method="getSoundSettings",
                params={"target": "outputTerminal"},
                version="1.1"
            )
        except HttpError as err:
            if err.error_code == ErrorCode.ILLEGAL_ARGUMENT:
                # The requested target does not exist, but that's not necessarily a fatal error
                return None
            else:
                raise BraviaApiError("An unexpected error occurred: {0}".format(str(err)))

        if type(response) is not list or len(response) > 1:
            raise BraviaApiError("API returned unexpected response format for getSoundSettings")

        output_terminal = response[0]

        output_modes = {
            "speaker": AudioOutputs.SPEAKER,
            "speaker_hdmi": AudioOutputs.SPEAKER_HDMI,
            "hdmi": AudioOutputs.HDMI,
            "audioSystem": AudioOutputs.AUDIO_SYSTEM
        }
        current_output = output_modes.get(output_terminal.get("currentValue"), AudioOutputs.UNKNOWN)

        if current_output == AudioOutputs.UNKNOWN:
            raise BraviaApiError(
                "API returned unexpected audio output '{0}'".format(output_terminal.get("currentValue"))
            )

        return {
            "name": coalesce_none_or_empty(output_terminal.get("target")),
            "output": current_output
        }

    def get_speaker_settings(self):
        self.bravia_client.initialize()

        response = self.http_client.request(
            endpoint="audio",
            method="getSpeakerSettings",
            params={"target": ""},
            version="1.0"
        )

        if type(response) is not list:
            raise BraviaApiError("API returned unexpected response format for getSoundSettings.")

        settings = {
            "tv_position": None,
            "subwoofer_level": None,
            "subwoofer_frequency": None,
            "subwoofer_phase": None,
            "subwoofer_power": None
        }

        valid_positions = {
            "tableTop": TvPosition.TABLE_TOP,
            "wallMount": TvPosition.WALL_MOUNT
        }

        valid_sub_phases = {
            "normal": SubwooferPhase.NORMAL,
            "reverse": SubwooferPhase.REVERSE
        }

        for setting in response:
            target = setting.get("target")

            if target == "tvPosition":
                position = valid_positions.get(setting.get("currentValue"), TvPosition.UNKNOWN)
                if position == TvPosition.UNKNOWN:
                    raise BraviaApiError(
                        "API returned unexpected TV position '{0}'".format(setting.get("currentValue"))
                    )
                settings["tv_position"] = position

            elif target == "subwooferLevel":
                settings["subwoofer_level"] = setting.get("currentValue")

            elif target == "subwooferFreq":
                settings["subwoofer_frequency"] = setting.get("currentValue")

            elif target == "subwooferPhase":
                phase = valid_sub_phases.get(setting.get("currentValue"), SubwooferPhase.UNKNOWN)
                if phase == SubwooferPhase.UNKNOWN:
                    raise BraviaApiError(
                        "API returned unexpected subwoofer phase '{0}'".format(setting.get("currentValue"))
                    )
                settings["subwoofer_phase"] = phase

            elif target == "subwooferPower":
                settings["subwoofer_power"] = True if setting.get("currentValue") == "on" else False

            # Skip settings that are unrecognized
            else:
                continue

        return settings

    def get_volume_information(self):
        self.bravia_client.initialize()

        response = self.http_client.request(endpoint="audio", method="getVolumeInformation", version="1.0")

        if type(response) is not list:
            raise BraviaApiError("API returned unexpected response format for getVolumeInformation.")

        valid_devices = {
            "speaker": VolumeDevice.SPEAKERS,
            "headphone": VolumeDevice.HEADPHONES
        }

        devices = []
        for this_device in response:
            device_type = valid_devices.get(this_device.get("target"))

            # Ignore unexpected device types
            if device_type is None:
                continue

            device_info = {
                "type": device_type,
                "volume": this_device.get("volume"),
                "muted": True if this_device.get("mute") else False,
                "min_volume": this_device.get("minVolume"),
                "max_volume": this_device.get("maxVolume")
            }
            devices.append(device_info)

        return devices

    def mute(self):
        self.set_mute(True)

    def unmute(self):
        self.set_mute(False)

    def set_mute(self, mute):
        self.bravia_client.initialize()

        if type(mute) is not bool:
            raise TypeError("mute must be a boolean value")

        self.http_client.request(
            endpoint="audio",
            method="setAudioMute",
            params={"status": mute},
            version="1.0"
        )

    def set_volume_level(self, volume, show_ui=True, device=None):
        if type(volume) is not int:
            raise TypeError("volume must be an integer value")

        self.set_volume(volume, show_ui, device)

    def increase_volume(self, increase_by=1, show_ui=True, device=None):
        if type(increase_by) is not int:
            raise TypeError("increase_by must be an integer value")

        self.set_volume("+" + str(increase_by), show_ui, device)

    def decrease_volume(self, decrease_by=1, show_ui=True, device=None):
        if type(decrease_by) is not int:
            raise TypeError("decrease_by must be an integer value")

        self.set_volume("-" + str(decrease_by), show_ui, device)

    def set_volume(self, volume, show_ui=True, device=None):
        self.bravia_client.initialize()

        if device is not None and type(device) is not VolumeDevice:
            raise TypeError("device must be a VolumeDevice enum type or None")

        if device == VolumeDevice.UNKNOWN:
            raise ValueError("device cannot be VolumeDevice.UNKNOWN")

        if type(volume) is not int and type(volume) is not str:
            raise TypeError("volume must be an int or string")

        if type(volume) is str:
            pprint(volume)
            if re.match(r'^[+-]\d+$', volume) is None:
                raise ValueError("volume must be in the format 1, +1, or -1")

        if type(show_ui) is not bool:
            raise TypeError("show_ui must be a boolean value")

        if device is None:
            target = ""
        else:
            valid_requested_devices = {
                VolumeDevice.SPEAKERS: "speaker",
                VolumeDevice.HEADPHONES: "headphone"
            }
            target = valid_requested_devices.get(device)
            if target is None:
                raise BraviaApiError("Internal error: Invalid VolumeDevice specified")

        try:
            self.http_client.request(
                endpoint="audio",
                method="setAudioVolume",
                params={
                    "target": target,
                    "volume": str(volume),
                    "ui": "on" if show_ui else "off"
                },
                version="1.2"
            )
        except HttpError as err:
            if err.error_code == ErrorCode.TARGET_NOT_SUPPORTED:
                raise BraviaApiError("The target device does not support controlling volume of the specified output.")
            if err.error_code == ErrorCode.VOLUME_OUT_OF_RANGE:
                raise BraviaApiError("The specified volume value is out of range for the target device.")
            else:
                raise BraviaApiError("An unexpected error occurred: {0}".format(str(err)))
