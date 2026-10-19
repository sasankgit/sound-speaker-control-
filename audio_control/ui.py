"""Tkinter control panel for routing Windows system audio."""

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import sounddevice as sd

from audio_control.devices import get_loopback_devices, get_output_devices
from audio_control.mirroring import mirror


class AudioControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("System Audio Router")
        self.root.geometry("680x520")
        self.root.minsize(560, 440)
        self.messages = queue.Queue()
        self.task = None
        self.stop_event = None
        self.source_devices = {}
        self.output_devices = {}

        self._build_ui()
        self._refresh_devices()
        self.root.after(100, self._process_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        content = ttk.Frame(self.root, padding=16)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)

        ttk.Label(
            content,
            text="Route the audio playing on one device to other devices.",
            wraplength=620,
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        source_frame = ttk.LabelFrame(content, text="Currently playing from", padding=10)
        source_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        source_frame.columnconfigure(0, weight=1)
        self.source = ttk.Combobox(source_frame, state="readonly")
        self.source.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            source_frame,
            text="Select the speaker/headset that Windows is currently using.",
            wraplength=600,
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))

        output_frame = ttk.LabelFrame(content, text="Also play through", padding=10)
        output_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.outputs = tk.Listbox(
            output_frame,
            selectmode=tk.EXTENDED,
            exportselection=False,
            height=9,
        )
        self.outputs.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            output_frame,
            orient=tk.VERTICAL,
            command=self.outputs.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.outputs.configure(yscrollcommand=scrollbar.set)
        ttk.Label(
            output_frame,
            text="Select one or more additional output devices.",
            wraplength=600,
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))

        controls = ttk.Frame(content)
        controls.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(controls, text="Refresh devices", command=self._refresh_devices).pack(
            side=tk.LEFT
        )
        self.start_button = ttk.Button(
            controls,
            text="Start routing",
            command=self._start_routing,
        )
        self.start_button.pack(side=tk.LEFT, padx=(8, 0))
        self.stop_button = ttk.Button(
            controls,
            text="Stop",
            command=self._stop_routing,
            state=tk.DISABLED,
        )
        self.stop_button.pack(side=tk.LEFT, padx=(8, 0))

        status_frame = ttk.LabelFrame(content, text="Status", padding=8)
        status_frame.grid(row=4, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)
        self.status = tk.StringVar(value="Ready.")
        ttk.Label(status_frame, textvariable=self.status, wraplength=620).grid(
            row=0, column=0, sticky="w"
        )

    def _refresh_devices(self):
        try:
            sources = get_loopback_devices()
            outputs = get_output_devices()
        except (OSError, RuntimeError, sd.PortAudioError) as error:
            self.status.set(f"Could not load audio devices: {error}")
            return

        current_source = self.source.get()
        self.source_devices = {
            f"{device['name']} [{device['id'][-8:]}]": device
            for device in sources
        }
        source_labels = list(self.source_devices)
        self.source.configure(values=source_labels)
        if current_source in self.source_devices:
            self.source.set(current_source)
        elif source_labels:
            self.source.current(0)
        else:
            self.source.set("")

        selected_labels = {
            self.outputs.get(index) for index in self.outputs.curselection()
        }
        current_output_devices = {
            label: self.output_devices.get(label) for label in selected_labels
        }
        self.output_devices = {
            f"#{device['index']} - {device['name']}": device
            for device in outputs
        }
        self.outputs.delete(0, tk.END)
        for label in self.output_devices:
            self.outputs.insert(tk.END, label)
            if label in current_output_devices and current_output_devices[label] is not None:
                self.outputs.selection_set(tk.END)

        self.status.set(
            f"Found {len(source_labels)} WASAPI playback source(s) and "
            f"{len(outputs)} output device(s)."
        )

    def _start_routing(self):
        source_label = self.source.get()
        selected = [self.outputs.get(i) for i in self.outputs.curselection()]
        if not source_label:
            messagebox.showerror(
                "No playback source",
                "No WASAPI playback source is available. Check that a Windows "
                "audio output device is connected.",
            )
            return
        if not selected:
            messagebox.showerror(
                "No destination selected",
                "Select at least one additional output device.",
            )
            return

        source = self.source_devices[source_label]
        destinations = [self.output_devices[label] for label in selected]
        if any(device["name"] == source["name"] for device in destinations):
            messagebox.showerror(
                "Choose another output",
                "The source device is already playing the original audio. "
                "Select additional output devices instead.",
            )
            return

        self.stop_event = threading.Event()
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.status.set(f"Starting audio routing from {source['name']}...")

        def run():
            try:
                mirror(
                    source["id"],
                    [device["index"] for device in destinations],
                    samplerate=48000,
                    stop_event=self.stop_event,
                )
            except (OSError, RuntimeError, ValueError, sd.PortAudioError) as error:
                self.messages.put(("error", str(error)))
            else:
                self.messages.put(("status", "Audio routing stopped."))
            finally:
                self.messages.put(("done", None))

        self.task = threading.Thread(target=run, daemon=True)
        self.task.start()

    def _stop_routing(self):
        if self.stop_event is not None:
            self.status.set("Stopping audio routing...")
            self.stop_event.set()

    def _process_messages(self):
        while True:
            try:
                kind, message = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "error":
                self.status.set(f"Routing failed: {message}")
            elif kind == "status":
                self.status.set(message)
            elif kind == "done":
                self.task = None
                self.stop_event = None
                self.start_button.configure(state=tk.NORMAL)
                self.stop_button.configure(state=tk.DISABLED)
        self.root.after(100, self._process_messages)

    def _close(self):
        if self.stop_event is not None:
            self.stop_event.set()
        self.root.destroy()


def run_app():
    root = tk.Tk()
    AudioControlApp(root)
    root.mainloop()
