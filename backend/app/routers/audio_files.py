"""Audio files listing router

Provides a small JSON endpoint to list available audio files placed
under frontend/public/audio so the frontend can populate the voice menu
dynamically.
"""
import os
from pathlib import Path

from fastapi import APIRouter

from ..core.config import PROJECT_ROOT

router = APIRouter(prefix="/api", tags=["Audio"])


@router.get('/audio-files')
async def list_audio_files():
    """Return JSON array of filenames under frontend/public/audio.

    Files are returned sorted alphabetically and filtered to common audio
    extensions (.mp3, .wav, .ogg).
    """
    audio_dir = PROJECT_ROOT / 'frontend' / 'public' / 'audio'
    if not audio_dir.exists() or not audio_dir.is_dir():
        return {"files": []}

    files = []
    try:
        for fn in os.listdir(audio_dir):
            p = audio_dir / fn
            if not p.is_file():
                continue
            if fn.lower().endswith(('.mp3', '.wav', '.ogg')):
                files.append(fn)
    except Exception:
        return {"files": []}

    files.sort()
    return {"files": files}
