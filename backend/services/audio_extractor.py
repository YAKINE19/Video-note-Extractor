"""Audio extraction from YouTube URLs and local video files."""
import os
import base64
import subprocess
import tempfile
import logging

import yt_dlp

from config import settings

logger = logging.getLogger(__name__)


def _audio_output_path(session_id: str) -> str:
    return os.path.join(settings.audio_dir, f"{session_id}.wav")


def _cookies_file() -> str | None:
    """Return a path to a Netscape-format cookies file, or None.

    Checks two env vars (in order):
      YOUTUBE_COOKIES_FILE  — path to an existing cookies.txt on disk
      YOUTUBE_COOKIES_B64   — cookies.txt content encoded as base64
                              (useful for injecting secrets into Render/Railway)
    """
    path = os.environ.get("YOUTUBE_COOKIES_FILE", "").strip()
    if path and os.path.exists(path):
        return path

    b64 = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()
    if b64:
        try:
            content = base64.b64decode(b64).decode("utf-8")
            # Write to a temp file that lives for the duration of the process
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", prefix="yt_cookies_", delete=False
            )
            tmp.write(content)
            tmp.close()
            logger.info("Using cookies from YOUTUBE_COOKIES_B64")
            return tmp.name
        except Exception as exc:
            logger.warning("Failed to decode YOUTUBE_COOKIES_B64: %s", exc)

    return None


def extract_from_youtube(url: str, session_id: str) -> tuple[str, str]:
    """Download audio from a YouTube URL and convert to WAV.

    Returns (wav_path, title).

    Bot-detection bypass strategy (applied in order):
      1. iOS player client  — YouTube rarely challenges the iOS app signature
      2. Android client     — fallback if iOS is also blocked
      3. Cookies            — if YOUTUBE_COOKIES_FILE or YOUTUBE_COOKIES_B64 is set,
                              those are passed to every attempt and usually resolve
                              "Sign in to confirm you're not a bot" errors
    """
    output_path = _audio_output_path(session_id)
    outtmpl = os.path.join(settings.audio_dir, f"{session_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }
        ],
        # ── Bot-detection bypass ───────────────────────────────────────────
        # Use the iOS player client — its request signature is not flagged
        # by YouTube's bot-detection on cloud IPs (unlike the default web client).
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android"],
            }
        },
        # ── Network resilience ─────────────────────────────────────────────
        "retries": 10,
        "fragment_retries": 10,
        "retry_sleep_functions": {"http": lambda n: min(2 ** n, 30)},
        "socket_timeout": 30,
        "http_chunk_size": 1048576,
        # ── Misc ───────────────────────────────────────────────────────────
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    # Attach cookies if the operator has provided them
    cookies = _cookies_file()
    if cookies:
        ydl_opts["cookiefile"] = cookies

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
