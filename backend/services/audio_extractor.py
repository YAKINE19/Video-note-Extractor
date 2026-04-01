"""Audio extraction from YouTube URLs and local video files."""
import os
import subprocess
import logging
from pathlib import Path

import yt_dlp

from config import settings

logger = logging.getLogger(__name__)


def _audio_output_path(session_id: str) -> str:
    return os.path.join(settings.audio_dir, f"{session_id}.wav")


def extract_from_youtube(url: str, session_id: str) -> tuple[str, str]:
    """Download audio from a YouTube URL and convert to WAV.

    Returns (wav_path, title).
    """
    output_path = _audio_output_path(session_id)
    outtmpl = os.path.join(settings.audio_dir, f"{session_id}.%(ext)s")

    ydl_opts = {
        # Prefer an audio-only stream to minimise bytes transferred.
        # Falls back to best available if no audio-only stream exists.
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",   # lossless for Whisper
            }
        ],
        # ── Network resilience ────────────────────────────────────────────
        "retries": 10,             # retry failed fragment/segment downloads
        "fragment_retries": 10,    # retry individual DASH/HLS fragments
        "retry_sleep_functions": {"http": lambda n: 2 ** n},  # exponential back-off
        "socket_timeout": 30,      # seconds per socket operation
        "http_chunk_size": 1048576,  # 1 MB chunks — reduces per-read stall risk
        # ── Misc ──────────────────────────────────────────────────────────
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "Untitled Video")

    # yt-dlp names the final file <session_id>.wav after the postprocessor runs.
    # If for any reason the extension differs, locate it explicitly.
    if not os.path.exists(output_path):
        candidates = [
            f for f in os.listdir(settings.audio_dir)
            if f.startswith(session_id)
        ]
        if not candidates:
            raise FileNotFoundError(
                f"yt-dlp finished but no audio file found for session {session_id}"
            )
        # Prefer .wav; otherwise take the first match and re-encode with ffmpeg
        wav_candidates = [c for c in candidates if c.endswith(".wav")]
        if wav_candidates:
            output_path = os.path.join(settings.audio_dir, wav_candidates[0])
        else:
            raw = os.path.join(settings.audio_dir, candidates[0])
            output_path = _audio_output_path(session_id)
            _reencode_to_wav(raw, output_path)

    logger.info("Downloaded audio for session %s: %s", session_id, title)
    return output_path, title


def _reencode_to_wav(src: str, dst: str) -> None:
    """Re-encode any audio file to 16-kHz mono WAV using ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        dst,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg re-encode failed: {result.stderr}")


def extract_from_video(video_path: str, session_id: str) -> str:
    """Extract audio from a local video file using ffmpeg.

    Returns the path to the WAV file.
    """
    output_path = _audio_output_path(session_id)

    cmd = [
        "ffmpeg",
        "-y",                   # overwrite output
        "-i", video_path,
        "-vn",                  # no video
        "-acodec", "pcm_s16le", # WAV codec
        "-ar", "16000",         # 16 kHz — optimal for Whisper
        "-ac", "1",             # mono
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    logger.info("Extracted audio for session %s → %s", session_id, output_path)
    return output_path


def get_video_duration(audio_path: str) -> float:
    """Return audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except (ValueError, TypeError):
        return 0.0
