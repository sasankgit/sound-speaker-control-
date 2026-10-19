"""Windows WASAPI playback-device discovery."""

import sounddevice as sd
import soundcard as sc


def get_output_devices():
    """Return available output devices backed by Windows WASAPI."""
    devices = sd.query_devices()
    host_apis = sd.query_hostapis()
    results = []
    for index, device in enumerate(devices):
        host_api = host_apis[device["hostapi"]]
        if device["max_output_channels"] <= 0 or host_api["name"] != "Windows WASAPI":
            continue
        results.append(
            {
                "index": index,
                "name": device["name"],
                "samplerate": int(device["default_samplerate"]),
                "channels": int(device["max_output_channels"]),
            }
        )
    return results


def get_loopback_devices():
    """Return Windows playback endpoints exposed as loopback microphones."""
    return [
        {
            "id": microphone.id,
            "name": microphone.name,
            "channels": microphone.channels,
        }
        for microphone in sc.all_microphones(include_loopback=True)
        if microphone.isloopback
    ]


def list_devices():
    print("Playback sources:")
    for device in get_loopback_devices():
        print(f"{device['id']}: {device['name']}")
    print("\nOutput devices:")
    for device in get_output_devices():
        print(
            f"#{device['index']}: {device['name']} "
            f"({device['samplerate']} Hz, {device['channels']} channels)"
        )
