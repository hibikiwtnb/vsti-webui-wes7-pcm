"""Project-native browser workbench with the public MuScriptor result controls."""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import quote

_COLORS = (
    "#1976d2",
    "#008b8b",
    "#3f8f3f",
    "#7559a6",
    "#b77900",
    "#b54f7d",
    "#087f8c",
    "#6d9628",
)


def track_file_url(path: str | Path) -> str:
    return "/file=" + quote(str(Path(path).resolve()))


def _result_instrument_label(instrument: str, language: str) -> str:
    del language
    return instrument.replace("_", " ")


def build_muscriptor_result_html(
    state: Mapping[str, object],
    translate: Callable[[str], str],
    language: str,
) -> str:
    detected = [str(item) for item in state.get("detected_instruments", [])]
    selected = [str(item) for item in state.get("selected_instruments", [])]
    ordered = list(selected or detected)
    for instrument in detected:
        if instrument not in ordered:
            ordered.append(instrument)
    instrument_metadata = state.get("instrument_metadata", {})
    if not isinstance(instrument_metadata, Mapping):
        instrument_metadata = {}
    instruments = [
        {
            "id": instrument,
            "label": _result_instrument_label(instrument, language),
            "detected": instrument in detected,
            "color": _COLORS[index % len(_COLORS)],
            "midi": instrument_metadata.get(instrument, []),
        }
        for index, instrument in enumerate(ordered)
    ]
    manifest = {
        "notes": list(state.get("notes", [])),
        "duration": float(state.get("duration", 0.0)),
        "bpm": float(state.get("bpm", 120.0)),
        "backendLabel": str(state.get("backend_label", "")),
        "sourceTrackName": str(state.get("source_track_name", "")),
        "instruments": instruments,
        "downloads": {
            "midi": str(
                state.get("midi_url")
                or track_file_url(str(state["midi_path"]))
            ),
        },
        "fileId": str(state.get("file_id", "")),
        "strings": {
            key: translate(f"muscriptor_result.{key}")
            for key in (
                "play",
                "pause",
                "follow",
                "original",
                "instruments",
                "not_detected",
                "solo",
                "mute",
                "ready",
                "linked_source",
                "zoom_help",
            )
        },
    }
    encoded = html.escape(json.dumps(manifest, ensure_ascii=False), quote=False)
    return (
        '<div class="msr-root">'
        f'<pre class="msr-manifest" hidden>{encoded}</pre>'
        '<div class="msr-host"></div>'
        "</div>"
    )


def muscriptor_result_head() -> str:
    return (
        f"<style>{MUSCRIPTOR_RESULT_CSS}</style>"
        '<script src="/static/vendor/hls.min.js"></script>'
        f"<script>{MUSCRIPTOR_RESULT_JS}</script>"
    )
