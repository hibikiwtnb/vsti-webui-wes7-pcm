from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time


class AudioStream:
    def __init__(
        self,
        hls_dir: Path,
        udp_host: str = "0.0.0.0",
        udp_port: int = 9998,
        sample_rate: int = 44100,
        channels: int = 2,
    ):
        self.hls_dir = hls_dir
        self.udp_host = udp_host
        self.udp_port = int(udp_port)
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self._ffmpeg: subprocess.Popen | None = None
        self._receiver_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._log_handles = []
        self._lock = threading.RLock()
        self._error: str | None = None
        self._packets = 0
        self._non_silent_packets = 0
        self._last_packet_at = 0.0

    def start(self) -> None:
        with self._lock:
            if self._is_running():
                return

            self.stop()
            self._stop = threading.Event()
            self._error = None
            self._packets = 0
            self._non_silent_packets = 0
            self._last_packet_at = 0.0
            self.hls_dir.mkdir(parents=True, exist_ok=True)
            self._clean_generated_files()

            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                self._error = "FFmpeg was not found on PATH"
                return

            ffmpeg_log = (self.hls_dir / "ffmpeg.log").open("wb")
            receiver_log = (self.hls_dir / "pcm-receiver.log").open("wb")
            self._log_handles = [ffmpeg_log, receiver_log]
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            try:
                self._ffmpeg = subprocess.Popen(
                    [
                        ffmpeg_path,
                        "-hide_banner",
                        "-loglevel",
                        "warning",
                        "-f",
                        "s16le",
                        "-ar",
                        str(self.sample_rate),
                        "-ac",
                        str(self.channels),
                        "-i",
                        "pipe:0",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "192k",
                        "-f",
                        "hls",
                        "-hls_time",
                        "1",
                        "-hls_list_size",
                        "6",
                        "-hls_flags",
                        "delete_segments+append_list+omit_endlist+independent_segments+program_date_time",
                        "-hls_segment_type",
                        "fmp4",
                        "-hls_fmp4_init_filename",
                        "init.mp4",
                        "-hls_segment_filename",
                        str(self.hls_dir / "segment-%06d.m4s"),
                        str(self.hls_dir / "stream.m3u8"),
                    ],
                    cwd=self.hls_dir,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=ffmpeg_log,
                    creationflags=creation_flags,
                )
                self._receiver_thread = threading.Thread(
                    target=self._receive_pcm,
                    args=(receiver_log,),
                    daemon=True,
                )
                self._receiver_thread.start()
            except OSError as exc:
                self._error = str(exc)
                self.stop()
                return

            time.sleep(0.25)
            if not self._is_running():
                self._error = "Audio pipeline exited during startup; see data/hls logs"

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            ffmpeg = self._ffmpeg
            receiver = self._receiver_thread
            self._ffmpeg = None
            self._receiver_thread = None

            if ffmpeg and ffmpeg.stdin:
                try:
                    ffmpeg.stdin.close()
                except OSError:
                    pass
            if receiver and receiver.is_alive():
                receiver.join(timeout=2)
            if ffmpeg and ffmpeg.poll() is None:
                ffmpeg.terminate()
                self._wait_or_kill(ffmpeg)

            for log_handle in self._log_handles:
                log_handle.close()
            self._log_handles = []

    def state(self) -> dict:
        running = self._is_running()
        playlist = self.hls_dir / "stream.m3u8"
        return {
            "running": running,
            "ready": running and playlist.is_file() and playlist.stat().st_size > 0,
            "url": "/stream/stream.m3u8",
            "ffmpeg_process_id": self._ffmpeg.pid if self._ffmpeg and self._ffmpeg.poll() is None else None,
            "udp_host": self.udp_host,
            "udp_port": self.udp_port,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "packets": self._packets,
            "non_silent_packets": self._non_silent_packets,
            "last_packet_age_seconds": None if not self._last_packet_at else round(time.monotonic() - self._last_packet_at, 3),
            "error": self._error,
        }

    def _is_running(self) -> bool:
        return bool(self._ffmpeg and self._ffmpeg.poll() is None)

    def _receive_pcm(self, log_handle) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
                udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                udp_socket.bind((self.udp_host, self.udp_port))
                udp_socket.settimeout(0.5)
                log_handle.write(f"Listening on UDP {self.udp_host}:{self.udp_port}\n".encode("utf-8"))
                log_handle.flush()
                while not self._stop.is_set():
                    try:
                        packet, _ = udp_socket.recvfrom(65535)
                    except socket.timeout:
                        continue
                    if len(packet) <= 32 or packet[:4] != b"SYNT":
                        continue
                    payload = packet[32:]
                    self._packets += 1
                    if any(payload):
                        self._non_silent_packets += 1
                    self._last_packet_at = time.monotonic()
                    ffmpeg = self._ffmpeg
                    if not ffmpeg or not ffmpeg.stdin or ffmpeg.poll() is not None:
                        break
                    try:
                        ffmpeg.stdin.write(payload)
                    except (BrokenPipeError, OSError):
                        break
        except OSError as exc:
            self._error = str(exc)
            log_handle.write((str(exc) + "\n").encode("utf-8", errors="replace"))
            log_handle.flush()

    def _clean_generated_files(self) -> None:
        names = ("stream.m3u8", "init.mp4", "ffmpeg.log", "pcm-receiver.log")
        for name in names:
            path = self.hls_dir / name
            if path.is_file():
                path.unlink()
        for path in self.hls_dir.glob("segment-*.m4s"):
            if path.is_file():
                path.unlink()

    @staticmethod
    def _wait_or_kill(process: subprocess.Popen) -> None:
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
