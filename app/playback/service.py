from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse
import socket
from threading import Event, Lock, Thread, current_thread
import re
import time

import mido

from app.errors import ConflictError, ServiceUnavailableError


@dataclass(frozen=True)
class MidiEvent:
    seconds: float
    track_id: str
    message: mido.Message


@dataclass
class PlaybackState:
    status: str = "idle"
    file_id: str | None = None
    filename: str | None = None
    position_seconds: float = 0
    duration_seconds: float = 0
    error: str | None = None


def normalize_track_name(value: str, track_index: int) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or f"track_{track_index}"


def read_midi_events(path: Path) -> tuple[list[MidiEvent], list[str], float]:
    midi = mido.MidiFile(path)
    raw_events: list[tuple[int, int, int, str, mido.Message]] = []
    sequence = 0

    for track_index, track in enumerate(midi.tracks):
        track_name = next(
            (message.name for message in track if message.type == "track_name"),
            "",
        )
        track_id = normalize_track_name(track_name, track_index)
        absolute_tick = 0
        for message in track:
            absolute_tick += message.time
            if not message.is_meta or message.type == "set_tempo":
                raw_events.append(
                    (absolute_tick, track_index, sequence, track_id, message.copy(time=0))
                )
            sequence += 1

    raw_events.sort(key=lambda item: (item[0], item[1], item[2]))
    tempo = 500000
    current_tick = 0
    current_seconds = 0.0
    events: list[MidiEvent] = []

    for absolute_tick, _, _, track_id, message in raw_events:
        current_seconds += mido.tick2second(
            absolute_tick - current_tick,
            midi.ticks_per_beat,
            tempo,
        )
        current_tick = absolute_tick
        if message.type == "set_tempo":
            tempo = message.tempo
        elif not message.is_meta:
            events.append(MidiEvent(current_seconds, track_id, message))

    tracks = list(
        dict.fromkeys(
            event.track_id
            for event in events
            if event.message.type == "note_on" and event.message.velocity > 0
        )
    )
    return events, tracks, current_seconds


class UdpMidiOutput:
    def __init__(self, target: str) -> None:
        parsed = urlparse(target)
        if parsed.scheme != "udp" or not parsed.hostname or not parsed.port:
            raise ValueError(f"Invalid UDP MIDI target: {target}")
        self._address = (parsed.hostname, parsed.port)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def send(self, message: mido.Message) -> None:
        self._socket.sendto(bytes(message.bytes()), self._address)

    def close(self) -> None:
        self._socket.close()


class MidiPlayback:
    def __init__(self, port_name: str) -> None:
        self.port_name = port_name
        self._state = PlaybackState()
        self._state_lock = Lock()
        self._output_lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._output = None
        self._started_at = 0.0
        self._tracks: list[str] = []
        self._muted: set[str] = set()
        self._solo: str | None = None
        self._active_notes: set[tuple[str, int, int]] = set()

    def state(self) -> dict:
        resolved_port = self._resolve_port()
        with self._state_lock:
            state = asdict(self._state)
            if state["status"] == "playing":
                state["position_seconds"] = min(
                    state["duration_seconds"],
                    max(0.0, time.monotonic() - self._started_at),
                )
            state.update(
                {
                    "tracks": list(self._tracks),
                    "muted": sorted(self._muted),
                    "solo": self._solo,
                }
            )
        state["port_available"] = resolved_port is not None
        state["port_name"] = resolved_port or self.port_name
        return state

    def play(self, file_id: str, path: Path, start_seconds: float = 0.0) -> dict:
        resolved_port = self._resolve_port()
        if resolved_port is None:
            raise ServiceUnavailableError(f'MIDI port "{self.port_name}" is not available.')
        events, tracks, duration = read_midi_events(path)
        start_seconds = max(0.0, min(float(start_seconds), duration))
        with self._state_lock:
            if self._state.status == "playing":
                raise ConflictError("Another MIDI file is already playing.")
            is_new_file = self._state.file_id != file_id
            if is_new_file:
                self._muted.clear()
                self._solo = None
            self._tracks = tracks
            self._state = PlaybackState(
                status="playing",
                file_id=file_id,
                filename=path.name.split("--", 1)[-1],
                position_seconds=start_seconds,
                duration_seconds=duration,
            )
            self._started_at = time.monotonic() - start_seconds
        self._stop = Event()
        self._thread = Thread(
            target=self._run,
            args=(events, resolved_port, start_seconds, self._stop),
            daemon=True,
        )
        audio_start_epoch_ms = int(time.time() * 1000)
        self._thread.start()
        result = self.state()
        result["audio_start_epoch_ms"] = audio_start_epoch_ms
        return result

    def stop(self) -> None:
        self._stop.set()
        self._all_notes_off()
        thread = self._thread
        if thread and thread.is_alive() and thread is not current_thread():
            thread.join(timeout=2)
        self._thread = None
        with self._state_lock:
            if self._state.status == "playing":
                self._state.position_seconds = min(
                    self._state.duration_seconds,
                    max(0.0, time.monotonic() - self._started_at),
                )
                self._state.status = "idle"

    def set_mix(self, muted_tracks: list[str], solo: str | None) -> dict:
        requested_muted = set(muted_tracks)
        with self._state_lock:
            known_tracks = set(self._tracks)
            if requested_muted - known_tracks or (
                solo is not None and solo not in known_tracks
            ):
                raise ConflictError("Mix contains an unknown track.")
            self._muted = requested_muted
            self._solo = solo
            inaudible = {
                track_id
                for track_id, _, _ in self._active_notes
                if track_id in self._muted
                or (self._solo is not None and track_id != self._solo)
            }
            notes_to_stop = [
                note for note in self._active_notes if note[0] in inaudible
            ]
            self._active_notes.difference_update(notes_to_stop)
        for _, channel, note in notes_to_stop:
            self._send_message(mido.Message("note_off", channel=channel, note=note))
        return self.state()

    def _resolve_port(self) -> str | None:
        if self.port_name.startswith("udp://"):
            return self.port_name
        output_names = mido.get_output_names()
        if self.port_name in output_names:
            return self.port_name
        numbered_name = re.compile(rf"^{re.escape(self.port_name)} \d+$")
        matches = [name for name in output_names if numbered_name.fullmatch(name)]
        return matches[0] if len(matches) == 1 else None

    def _run(
        self,
        events: list[MidiEvent],
        resolved_port: str,
        start_seconds: float,
        stop_event: Event,
    ) -> None:
        started = time.monotonic()
        try:
            with self._open_output(resolved_port) as output:
                self._output = output
                self._send_message(
                    mido.Message("sysex", data=(0x7E, 0x7F, 0x09, 0x01))
                )
                for event in events:
                    if event.seconds < start_seconds:
                        if event.message.type not in {"note_on", "note_off"}:
                            self._send_message(event.message)
                        continue
                    wait_seconds = event.seconds - start_seconds - (
                        time.monotonic() - started
                    )
                    if stop_event.wait(max(0.0, wait_seconds)):
                        break
                    self._send_event(event)
                self._all_notes_off()
            with self._state_lock:
                if self._state.status == "playing":
                    self._state.status = "idle"
        except Exception as exc:
            with self._state_lock:
                self._state.status = "error"
                self._state.error = str(exc)
        finally:
            with self._state_lock:
                self._active_notes.clear()
            self._output = None

    def _open_output(self, resolved_port: str):
        if resolved_port.startswith("udp://"):
            return UdpMidiOutput(resolved_port)
        return mido.open_output(resolved_port)

    def _send_event(self, event: MidiEvent) -> None:
        message = event.message
        if message.type == "note_on" and message.velocity > 0:
            with self._state_lock:
                if event.track_id in self._muted or (
                    self._solo is not None and event.track_id != self._solo
                ):
                    return
                self._active_notes.add(
                    (event.track_id, message.channel, message.note)
                )
        elif message.type in {"note_off", "note_on"}:
            with self._state_lock:
                self._active_notes.discard(
                    (event.track_id, message.channel, message.note)
                )
        self._send_message(message)

    def _send_message(self, message: mido.Message) -> None:
        with self._output_lock:
            if self._output is not None:
                self._output.send(message)

    def _all_notes_off(self) -> None:
        with self._state_lock:
            self._active_notes.clear()
        for channel in range(16):
            self._send_message(
                mido.Message(
                    "control_change",
                    channel=channel,
                    control=123,
                    value=0,
                )
            )

