# WES7 VSTi WebUI

Browser workbench for a WES7 Yamaha S-YXG50 appliance. The WebUI runs on the Windows host, sends MIDI to the WES7 VM over UDP, receives raw PCM from the VM over UDP, converts it to HLS/AAC with FFmpeg, and plays it in the browser with the existing piano roll UI.

The synthesizer files stay outside this repository. The WES7 VM owns `SGP2.DLL`, the Yamaha `.tbl` files, and `synthstream.exe`.

## Features

- Upload and save MIDI files locally
- Piano roll display in the browser
- Browser playback through HLS/AAC
- MIDI playback to the WES7 VM over UDP
- PCM receive from the WES7 VM over UDP
- Per-track mute and solo
- BPM and first-beat correction
- Corrected MIDI download
- Per-track MIDI channel and GM program display

## Architecture

```text
Browser WebUI (:8789)
  -> FastAPI on Windows host
  -> UDP MIDI to WES7 synthstream (:9999)
  -> WES7 SGP2.DLL render
  -> UDP PCM back to Windows host (:9998)
  -> FFmpeg HLS/AAC
  -> Browser audio + piano roll
```

No Docker, WSL, Wine, VSTHost, loopMIDI, audio bridge, RDP audio, or virtual audio driver is required for this version.

## Default runtime assumptions

The current defaults match the WES7 appliance used during development:

- WebUI bind: `0.0.0.0:8789`
- WES7 VM IP: `172.19.32.190`
- MIDI target: `udp://172.19.32.190:9999`
- PCM listen: `0.0.0.0:9998`
- PCM format: `s16le`, `44100 Hz`, stereo

These defaults can be overridden with environment variables:

- `YAMAHA_BIND_HOST`
- `YAMAHA_PORT`
- `YAMAHA_MIDI_PORT`
- `YAMAHA_PCM_UDP_HOST`
- `YAMAHA_PCM_UDP_PORT`
- `YAMAHA_PCM_RATE`
- `YAMAHA_PCM_CHANNELS`
- `YAMAHA_MAX_UPLOAD_BYTES`

## Setup

Run once:

```powershell
.\Setup-VstiWebUi.ps1
```

This creates `.venv` and installs the pinned Python dependencies.

FFmpeg must be available on `PATH`.

## Start

Run:

```powershell
.\Start-VstiWebUi.ps1
```

Open locally:

```text
http://127.0.0.1:8789/
```

Open from the same Tailscale network using the Windows host address, for example:

```text
http://100.71.39.33:8789/
```

## Repository boundaries

- `app/library`: local MIDI file library
- `app/playback`: MIDI scheduling and UDP output
- `app/streaming`: UDP PCM receiver and FFmpeg HLS pipeline
- `app/workbench`: piano roll manifest and browser runtime
- `static`: upload, picker, and iframe shell

User MIDI files, HLS segments, logs, virtual environments, binaries, synth DLLs, and VM images are intentionally ignored by Git.
