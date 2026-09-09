from __future__ import annotations

import html
import io
import math
from dataclasses import dataclass
from pathlib import Path

import mido

from app.playback.service import normalize_track_name
from app.workbench.runtime import build_muscriptor_result_html, muscriptor_result_head


ORIGINAL_MIDI_BPM = 120.0

GM_PROGRAM_NAMES = (
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
    "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
    "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass",
    "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2",
    "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute",
    "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)",
    "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)",
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)",
    "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)",
    "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto",
    "Kalimba", "Bag Pipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
    "Telephone Ring", "Helicopter", "Applause", "Gunshot",
)

STRINGS = {
    "play": "播放",
    "pause": "暫停",
    "follow": "跟隨",
    "original": "原音",
    "instruments": "樂器",
    "not_detected": "未偵測",
    "solo": "獨奏",
    "mute": "靜音",
    "download": "下載",
    "download_midi": "下載修正後 MIDI",
    "ready": "就緒",
    "linked_source": "{track} · {backend}",
    "zoom_help": "Ctrl/Alt + 滾輪縮放，Shift + 滾輪橫向捲動",
}


@dataclass(frozen=True)
class RollNote:
    instrument: str
    pitch: int
    velocity: int
    start: float
    end: float


def read_roll_notes(
    path: Path,
) -> tuple[list[RollNote], list[str], dict[str, list[dict[str, object]]], float, float]:
    midi = mido.MidiFile(path)
    raw_events: list[tuple[int, int, int, str, mido.Message | mido.MetaMessage]] = []
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
            raw_events.append(
                (absolute_tick, track_index, sequence, track_id, message.copy(time=0))
            )
            sequence += 1

    raw_events.sort(key=lambda item: (item[0], item[1], item[2]))
    tempo = 500000
    display_tempo = next(
        (
            int(message.tempo)
            for track in midi.tracks
            for message in track
            if message.type == "set_tempo"
        ),
        None,
    )
    current_tick = 0
    current_seconds = 0.0
    active: dict[tuple[str, int, int], list[tuple[float, int]]] = {}
    programs: dict[tuple[str, int], int] = {}
    initial_programs: dict[tuple[str, int], int] = {}
    notes: list[RollNote] = []

    for absolute_tick, _, _, track_id, message in raw_events:
        current_seconds += mido.tick2second(
            absolute_tick - current_tick,
            midi.ticks_per_beat,
            tempo,
        )
        current_tick = absolute_tick
        if message.type == "set_tempo":
            tempo = message.tempo
            continue
        if message.type == "program_change":
            programs[(track_id, int(message.channel))] = int(message.program)
            continue
        if message.type not in {"note_on", "note_off"}:
            continue
        channel = int(getattr(message, "channel", 0))
        pitch = int(message.note)
        key = (track_id, channel, pitch)
        if message.type == "note_on" and message.velocity > 0:
            program = programs.get((track_id, channel), 0)
            initial_programs.setdefault((track_id, channel), program)
            active.setdefault(key, []).append((current_seconds, int(message.velocity)))
            continue
        starts = active.get(key)
        if not starts:
            continue
        start, velocity = starts.pop(0)
        if not starts:
            active.pop(key, None)
        if current_seconds > start:
            notes.append(
                RollNote(track_id, pitch, velocity, start, current_seconds)
            )

    notes.sort(key=lambda note: (note.start, note.instrument, note.pitch))
    instruments = list(dict.fromkeys(note.instrument for note in notes))
    instrument_metadata = {
        instrument: [
            {
                "channel": channel,
                "program": program,
                "program_name": (
                    GM_PROGRAM_NAMES[program]
                    if 0 <= program < len(GM_PROGRAM_NAMES)
                    else f"Program {program + 1}"
                ),
            }
            for (track_id, channel), program in initial_programs.items()
            if track_id == instrument
        ]
        for instrument in instruments
    }
    duration = max(current_seconds, max((note.end for note in notes), default=0.0))
    bpm = float(mido.tempo2bpm(display_tempo)) if display_tempo else ORIGINAL_MIDI_BPM
    return notes, instruments, instrument_metadata, duration, bpm


def build_bpm_fixed_midi(
    midi_path: Path,
    target_bpm: float,
    first_beat_delay: float,
) -> bytes:
    midi = mido.MidiFile(midi_path)
    scale = target_bpm / ORIGINAL_MIDI_BPM
    target_tempo = mido.bpm2tempo(target_bpm)
    bar_ticks = midi.ticks_per_beat * 4
    user_offset_ticks = int(
        round(first_beat_delay * midi.ticks_per_beat * target_bpm / 60.0)
    )
    scaled_tracks: list[list[tuple[int, mido.Message | mido.MetaMessage]]] = []
    earliest_note_tick: int | None = None

    for track in midi.tracks:
        absolute_tick = 0
        scaled_events: list[tuple[int, mido.Message | mido.MetaMessage]] = []
        for message in track:
            absolute_tick += int(round(message.time * scale))
            copied = message.copy(time=0)
            if copied.type != "set_tempo":
                scaled_events.append((absolute_tick, copied))
            if (
                copied.type == "note_on"
                and copied.velocity > 0
                and (earliest_note_tick is None or absolute_tick < earliest_note_tick)
            ):
                earliest_note_tick = absolute_tick
        scaled_tracks.append(scaled_events)

    shift_ticks = -user_offset_ticks
    if earliest_note_tick is not None and earliest_note_tick + shift_ticks < 0:
        shift_ticks += (
            math.ceil(-(earliest_note_tick + shift_ticks) / bar_ticks) * bar_ticks
        )

    output = mido.MidiFile(type=midi.type, ticks_per_beat=midi.ticks_per_beat)
    for track_index, events in enumerate(scaled_tracks):
        output_track = mido.MidiTrack()
        output.tracks.append(output_track)
        previous_tick = 0
        if track_index == 0:
            output_track.append(
                mido.MetaMessage("set_tempo", tempo=target_tempo, time=0)
            )
        for absolute_tick, message in events:
            corrected_tick = max(0, absolute_tick + shift_ticks)
            message.time = corrected_tick - previous_tick
            previous_tick = corrected_tick
            output_track.append(message)

    encoded = io.BytesIO()
    output.save(file=encoded)
    return encoded.getvalue()


def build_workbench_page(file_id: str, midi_path: Path, filename: str) -> str:
    notes, instruments, instrument_metadata, duration, bpm = read_roll_notes(midi_path)
    if not notes:
        raise ValueError("MIDI contains no completed notes")
    state = {
        "kind": "midi_result",
        "file_id": file_id,
        "midi_url": f"/api/midi/{file_id}/file",
        "selected_instruments": instruments,
        "detected_instruments": instruments,
        "instrument_metadata": instrument_metadata,
        "notes": [
            {
                "instrument": note.instrument,
                "pitch": note.pitch,
                "velocity": note.velocity,
                "start": note.start,
                "end": note.end,
            }
            for note in notes
        ],
        "duration": duration,
        "bpm": bpm,
        "backend_label": "Local Yamaha VSTi",
        "source_track_name": "",
    }
    translate = lambda key: STRINGS.get(key.rsplit(".", 1)[-1], key)
    body = build_muscriptor_result_html(state, translate, "zh_TW")
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="zh-Hant">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{html.escape(filename)}</title>",
            muscriptor_result_head(),
            "<style>",
            "body{margin:0;padding:0;background:#fff;color:#18212f;font-family:system-ui,'Noto Sans TC',sans-serif;}",
            ".share-shell{max-width:1600px;margin:0 auto;}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="share-shell">',
            body,
            "</main>",
            "</body>",
            "</html>",
        ]
    )
