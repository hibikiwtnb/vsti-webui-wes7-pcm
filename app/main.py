from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import json
import logging
import re
import uuid
from urllib.parse import quote, urlparse

from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import load_settings
from app.errors import AppError, ConflictError, ValidationError
from app.library.service import MidiLibrary
from app.playback.service import MidiPlayback
from app.streaming.service import AudioStream
from app.workbench.service import build_bpm_fixed_midi, build_workbench_page


settings = load_settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.hls_dir.mkdir(parents=True, exist_ok=True)
library = MidiLibrary(settings.data_dir / "midi", settings.max_upload_bytes)
playback = MidiPlayback(settings.midi_port)
audio_stream = AudioStream(settings.hls_dir, settings.pcm_udp_host, settings.pcm_udp_port, settings.pcm_rate, settings.pcm_channels)
logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","message":"%(message)s"}')
logger = logging.getLogger("yamaha-lan")


class SynthPlayRequest(BaseModel):
    file_id: str = Field(min_length=16, max_length=16)
    synth: str = "yamaha-syxg2006le"
    start_seconds: float = Field(default=0.0, ge=0.0)


class SynthMixRequest(BaseModel):
    muted_tracks: list[str] = Field(default_factory=list)
    solo: str | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Yamaha LAN service started")
    audio_stream.start()
    yield
    playback.stop()
    audio_stream.stop()


app = FastAPI(title="VSTi WebUI", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=settings.root_dir / "static"), name="static")
app.mount("/stream", StaticFiles(directory=settings.hls_dir), name="stream")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "SAMEORIGIN"
    response.headers["referrer-policy"] = "no-referrer"
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["cache-control"] = "no-store"
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "request_id": request.headers.get("x-request-id"),
        },
    )


@app.get("/")
async def index():
    return FileResponse(settings.root_dir / "static" / "index.html")


@app.get("/share/{file_id}/share.html")
async def share(file_id: str):
    path = library.resolve(file_id)
    try:
        page = build_workbench_page(file_id, path, path.name.split("--", 1)[-1])
    except (EOFError, OSError, ValueError) as exc:
        raise ValidationError("MIDI could not be displayed.") from exc
    return HTMLResponse(page)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    playback_state = playback.state()
    stream_state = audio_stream.state()
    is_ready = playback_state["port_available"] and stream_state["ready"]
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ready" if is_ready else "degraded",
            "playback": playback_state,
            "stream": stream_state,
        },
    )


@app.get("/api/midi")
async def list_midi():
    return {"items": library.list()}


@app.post("/api/midi", status_code=201)
async def upload_midi(file: UploadFile = File(...)):
    content = await file.read(settings.max_upload_bytes + 1)
    return library.save(file.filename or "upload.mid", content)


@app.post("/api/play/{file_id}", status_code=202)
async def play(file_id: str):
    path = library.resolve(file_id)
    return playback.play(file_id, path)


@app.get("/api/midi/{file_id}/file")
async def midi_file(file_id: str):
    path = library.resolve(file_id)
    return FileResponse(path, media_type="audio/midi", filename=path.name.split("--", 1)[-1])


@app.post("/api/synth/play")
async def synth_play(payload: SynthPlayRequest):
    if payload.synth != "yamaha-syxg2006le":
        raise ValidationError("Unknown synth.")
    path = library.resolve(payload.file_id)
    return playback.play(payload.file_id, path, payload.start_seconds)


@app.post("/api/synth/stop")
async def synth_stop():
    playback.stop()
    return playback.state()


@app.post("/api/synth/mix")
async def synth_mix(payload: SynthMixRequest):
    return playback.set_mix(payload.muted_tracks, payload.solo)


@app.get("/api/midi-fix")
async def midi_fix(
    midi_url: str = Query(),
    bpm: float = Query(ge=20, le=300),
    first_beat: float = Query(ge=-60, le=60),
):
    match = re.fullmatch(r"/api/midi/([0-9a-f]{16})/file", urlparse(midi_url).path)
    if match is None:
        raise ValidationError("Invalid MIDI URL.")
    path = library.resolve(match.group(1))
    try:
        content = build_bpm_fixed_midi(path, bpm, first_beat)
    except (EOFError, OSError, ValueError) as exc:
        raise ValidationError("MIDI could not be converted.") from exc
    filename = path.name.split("--", 1)[-1]
    download_name = Path(filename).with_suffix("").name + "_bpmfix.mid"
    return Response(
        content=content,
        media_type="audio/midi",
        headers={
            "Content-Disposition": (
                'attachment; filename="bpmfix.mid"; '
                f"filename*=UTF-8''{quote(download_name, safe='')}"
            )
        },
    )


@app.delete("/api/midi/{file_id}")
async def delete_midi(file_id: str):
    playback_state = playback.state()
    if playback_state["status"] == "playing" and playback_state["file_id"] == file_id:
        raise ConflictError("Stop this MIDI file before deleting it.")
    return {"deleted": library.delete(file_id)}


@app.post("/api/stop")
async def stop():
    playback.stop()
    return {"status": "stopping"}


@app.get("/api/state")
async def state():
    return {"playback": playback.state(), "stream": audio_stream.state()}


@app.get("/api/events")
async def events(request: Request):
    async def generate():
        while not await request.is_disconnected():
            state = {"playback": playback.state(), "stream": audio_stream.state()}
            yield f"event: state\ndata: {json.dumps(state)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream")

