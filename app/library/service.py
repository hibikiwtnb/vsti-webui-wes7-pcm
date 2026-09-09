from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
import unicodedata

from mido import MidiFile

from app.errors import NotFoundError, ValidationError


UNSAFE_NAME = re.compile(r'[\x00-\x1f<>:"/\\|?*]+')
FILE_ID = re.compile(r"^[0-9a-f]{16}$")


@dataclass(frozen=True)
class MidiEntry:
    id: str
    filename: str
    duration_seconds: float
    tracks: int
    size: int


class MidiLibrary:
    def __init__(self, library_dir: Path, max_upload_bytes: int) -> None:
        self.library_dir = library_dir
        self.max_upload_bytes = max_upload_bytes
        self.library_dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content: bytes) -> MidiEntry:
        if not content or len(content) > self.max_upload_bytes:
            raise ValidationError("MIDI file is empty or exceeds the upload limit.")
        if not filename.lower().endswith((".mid", ".midi")):
            raise ValidationError("Only .mid and .midi files are accepted.")
        try:
            midi = MidiFile(file=BytesIO(content))
        except Exception as exc:
            raise ValidationError("The uploaded file is not a valid MIDI file.") from exc
        file_id = sha256(content).hexdigest()[:16]
        original_name = unicodedata.normalize("NFC", Path(filename).name)
        clean_name = UNSAFE_NAME.sub("_", original_name).strip(" .") or f"{file_id}.mid"
        target = self.library_dir / f"{file_id}--{clean_name}"
        if not target.exists():
            target.write_bytes(content)
        return MidiEntry(file_id, clean_name, midi.length, len(midi.tracks), len(content))

    def list(self) -> list[dict]:
        entries: list[dict] = []
        for path in sorted(self.library_dir.glob("*--*.mid*"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                midi = MidiFile(path)
                file_id, filename = path.name.split("--", 1)
                entries.append(asdict(MidiEntry(file_id, filename, midi.length, len(midi.tracks), path.stat().st_size)))
            except Exception:
                continue
        return entries

    def resolve(self, file_id: str) -> Path:
        if FILE_ID.fullmatch(file_id) is None:
            raise NotFoundError("MIDI file was not found.")
        matches = list(self.library_dir.glob(f"{file_id}--*.mid*"))
        if len(matches) != 1:
            raise NotFoundError("MIDI file was not found.")
        return matches[0]

    def delete(self, file_id: str) -> str:
        path = self.resolve(file_id)
        filename = path.name.split("--", 1)[-1]
        path.unlink()
        return filename
