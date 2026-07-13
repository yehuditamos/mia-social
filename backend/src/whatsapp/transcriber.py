import os
import base64
import requests
from src.whatsapp.media import download_media

_WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"

_MIME_TO_EXT = {
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp4": "mp4",
    "audio/wav": "wav",
    "audio/aac": "aac",
    "audio/webm": "webm",
}


def transcribe_audio(audio_id: str) -> str:
    """Download WhatsApp voice note and transcribe via Whisper. Returns empty string on failure."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[WHISPER] OPENAI_API_KEY not set")
        return ""

    try:
        audio_b64, mime_type = download_media(audio_id)
    except Exception as e:
        print(f"[WHISPER] download failed: {repr(e)}")
        return ""

    audio_bytes = base64.b64decode(audio_b64)

    # Strip codec suffix, e.g. "audio/ogg; codecs=opus" → "audio/ogg"
    base_mime = mime_type.split(";")[0].strip()
    ext = _MIME_TO_EXT.get(base_mime, "ogg")
    filename = f"voice.{ext}"

    print(f"[WHISPER] sending {len(audio_bytes)} bytes, mime={base_mime}, file={filename}")

    try:
        res = requests.post(
            _WHISPER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, audio_bytes, base_mime)},
            data={"model": "whisper-1", "language": "he"},
            timeout=40,
        )
        data = res.json()
        print(f"[WHISPER] status={res.status_code} text={str(data.get('text', ''))[:80]}")
        if res.status_code != 200:
            print(f"[WHISPER] error body: {data}")
            return ""
        return data.get("text", "").strip()
    except Exception as e:
        print(f"[WHISPER] request error: {repr(e)}")
        return ""
