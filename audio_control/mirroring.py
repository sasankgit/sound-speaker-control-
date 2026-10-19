"""Route system audio from a Windows playback endpoint to other outputs."""

import queue
import threading

import numpy as np
import soundcard as sc
import sounddevice as sd

from audio_control.devices import get_output_devices


def mirror(source_id, out_specs, samplerate=48000, blocksize=1024, stop_event=None):
    """Capture a Windows playback endpoint using WASAPI loopback and route it."""
    available = get_output_devices()
    by_index = {device["index"]: device for device in available}
    output_indices = [int(spec) for spec in out_specs]
    if not output_indices:
        raise ValueError("Select at least one additional output device.")
    missing = [index for index in output_indices if index not in by_index]
    if missing:
        raise ValueError(f"Unavailable WASAPI output device(s): {missing}")

    source = sc.get_microphone(source_id, include_loopback=True)
    if not source.isloopback:
        raise ValueError("The selected source is not a system-audio loopback device.")
    rate = int(samplerate)
    channels = min(2, source.channels)
    if channels <= 0:
        raise ValueError("The source device has no output channels.")

    stop_event = stop_event or threading.Event()
    queues = [queue.Queue(maxsize=12) for _ in output_indices]
    pending_chunks = [None for _ in output_indices]
    pending_offsets = [0 for _ in output_indices]
    capture_error = []

    def capture():
        try:
            while not stop_event.is_set():
                audio = source.record(
                    samplerate=rate,
                    numframes=blocksize,
                    channels=list(range(channels)),
                )
                audio = np.asarray(audio, dtype="float32")
                for audio_queue in queues:
                    try:
                        audio_queue.put_nowait(audio)
                    except queue.Full:
                        try:
                            audio_queue.get_nowait()
                            audio_queue.put_nowait(audio)
                        except queue.Empty:
                            pass
        except Exception as error:
            capture_error.append(error)
            stop_event.set()

    def make_output_callback(position, device_index, audio_queue):
        output_channels = min(channels, by_index[device_index]["channels"])

        def callback(outdata, frames, time_info, status):
            del time_info
            if status:
                print(f"Output #{device_index} status: {status}")
            outdata.fill(0)
            written = 0
            while written < frames:
                chunk = pending_chunks[position]
                if chunk is None or pending_offsets[position] >= len(chunk):
                    try:
                        chunk = audio_queue.get_nowait()
                    except queue.Empty:
                        break
                    pending_chunks[position] = chunk
                    pending_offsets[position] = 0
                offset = pending_offsets[position]
                count = min(frames - written, len(chunk) - offset)
                outdata[written:written + count, :output_channels] = (
                    chunk[offset:offset + count, :output_channels]
                )
                pending_offsets[position] += count
                written += count
                if pending_offsets[position] >= len(chunk):
                    pending_chunks[position] = None

        return callback

    output_settings = sd.WasapiSettings(auto_convert=True)
    streams = [
        sd.OutputStream(
            device=index,
            samplerate=rate,
            channels=min(channels, by_index[index]["channels"]),
            blocksize=blocksize,
            dtype="float32",
            extra_settings=output_settings,
            callback=make_output_callback(position, index, audio_queue),
        )
        for position, (index, audio_queue) in enumerate(zip(output_indices, queues))
    ]
    capture_thread = threading.Thread(target=capture, daemon=True)
    started_streams = []
    print(f"Routing WASAPI playback '{source.name}' -> {output_indices}.")
    try:
        for stream in streams:
            stream.start()
            started_streams.append(stream)
        capture_thread.start()
        while not stop_event.wait(0.5):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        if capture_thread.is_alive():
            capture_thread.join(timeout=2)
        for stream in started_streams:
            stream.stop()
        for stream in streams:
            stream.close()
    if capture_error:
        raise RuntimeError(
            f"System audio loopback failed: {capture_error[0]}"
        ) from capture_error[0]
