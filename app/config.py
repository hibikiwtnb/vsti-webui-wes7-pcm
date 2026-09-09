from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    data_dir: Path
    bind_host: str
    port: int
    midi_port: str
    max_upload_bytes: int
    hls_dir: Path
    pcm_udp_host: str
    pcm_udp_port: int
    pcm_rate: int
    pcm_channels: int


def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parent.parent
    return Settings(
        root_dir=root_dir,
        data_dir=root_dir / "data",
        bind_host=os.getenv("YAMAHA_BIND_HOST", "0.0.0.0"),
        port=int(os.getenv("YAMAHA_PORT", "8789")),
        midi_port=os.getenv("YAMAHA_MIDI_PORT", "udp://172.19.32.190:9999"),
        max_upload_bytes=int(os.getenv("YAMAHA_MAX_UPLOAD_BYTES", "5242880")),
        hls_dir=root_dir / "data" / "hls",
        pcm_udp_host=os.getenv("YAMAHA_PCM_UDP_HOST", "0.0.0.0"),
        pcm_udp_port=int(os.getenv("YAMAHA_PCM_UDP_PORT", "9998")),
        pcm_rate=int(os.getenv("YAMAHA_PCM_RATE", "44100")),
        pcm_channels=int(os.getenv("YAMAHA_PCM_CHANNELS", "2")),
    )
