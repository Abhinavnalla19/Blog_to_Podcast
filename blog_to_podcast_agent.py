import os
import base64
import requests
import streamlit as st
from dotenv import load_dotenv
import logging
import json
from pathlib import Path
from datetime import datetime

load_dotenv()

# Logging setup
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("blog_to_podcast")

# Streamlit Setup
st.set_page_config(page_title="📰 ➡️ 🎙️ Blog to Podcast", page_icon="🎙️")
st.title("📰 ➡️ 🎙️ Blog to Podcast Agent")

# API Keys (Runtime Input) — use Gemini and Jina
env_gemini = os.environ.get("GEMINI_API_KEY", "")
env_jina = os.environ.get("JINA_API_KEY", "")

# Setup & Keys expander removed for a cleaner UI (keys loaded from environment)

# Blog URL Input
url = st.text_input("Enter Blog URL:", "")


def fetch_article_with_jina(url: str, jina_api_key: str) -> str:
    """Fetch article text using Jina Reader API (placeholder).

    Update `JINA_READER_URL` in env or replace endpoint with Jina's real reader endpoint.
    """
    # Use an explicit Jina Reader endpoint by default: r.jina.ai
    # The Reader service accepts a GET to https://r.jina.ai/{TARGET_URL}
    endpoint = os.environ.get("JINA_READER_URL", "https://r.jina.ai")
    headers = {"Authorization": f"Bearer {jina_api_key}"} if jina_api_key else {}

    logger.info("fetch_article_with_jina: start url=%s endpoint=%s", url, endpoint)

    # If the configured endpoint looks like the r.jina.ai reader host, call it with GET
    try:
        if endpoint.rstrip('/').endswith('r.jina.ai') or 'r.jina.ai' in endpoint:
            # URL-encode the target URL path segment
            from urllib.parse import quote

            target = quote(url, safe='')
            reader_url = f"{endpoint.rstrip('/')}/{target}"
            resp = requests.get(reader_url, headers=headers, timeout=30)
            resp.raise_for_status()
            # r.jina.ai typically returns plain text with the scraped article
            # but may return JSON on some deployments — try JSON first.
            try:
                data = resp.json()
                if isinstance(data, dict):
                    for key in ("text", "content", "article", "result"):
                        if key in data:
                            return data[key]
                    if "data" in data and isinstance(data["data"], dict):
                        for key in ("text", "content"):
                            if key in data["data"]:
                                return data["data"][key]
                return str(data)
            except ValueError:
                logger.info("fetch_article_with_jina: received text response, len=%d", len(resp.text or ""))
                return resp.text

        # Fallback: if a custom JINA_READER_URL is provided, try POST (legacy behavior)
        resp = requests.post(endpoint, json={"url": url}, headers=headers, timeout=30)
        resp.raise_for_status()
        try:
            data = resp.json()
            if isinstance(data, dict):
                for key in ("text", "content", "article", "result"):
                    if key in data:
                        return data[key]
                if "data" in data and isinstance(data["data"], dict):
                    for key in ("text", "content"):
                        if key in data["data"]:
                            return data["data"][key]
            return str(data)
        except ValueError:
            logger.info("fetch_article_with_jina: fallback POST returned text, len=%d", len(resp.text or ""))
            return resp.text
    except requests.HTTPError as e:
        # surface clearer message when Jina endpoint rejects a method (e.g. 405)
        logger.exception("fetch_article_with_jina: HTTP error")
        raise requests.HTTPError(f"Jina Reader request failed: {e} (endpoint={endpoint})")


def generate_summary_with_gemini(text: str, gemini_api_key: str) -> str:
    """Generate a summary using Gemini (Gemma 3 27b) — placeholder HTTP call.

    Replace `GEMINI_TEXT_ENDPOINT` with the real Gemini text generation endpoint and
    adjust payload/response parsing to the actual API.
    """
    # Prefer using the official Google GenAI client when available.
    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3-flash")
    try:
        from google import genai
    except Exception:
        # Fallback: instruct user to install client or set a working REST endpoint
        raise RuntimeError(
            "google-genai client not installed. Install it with `pip install google-genai` "
            "or set GEMINI_TEXT_ENDPOINT to a valid REST endpoint."
        )

    # Initialize client — prefer passing API key if provided
    client = genai.Client(api_key=gemini_api_key) if gemini_api_key else genai.Client()

    prompt = f"Summarize the following text for a podcast (conversational, <=2000 chars):\n\n{text}"
    logger.info("generate_summary_with_gemini: generating summary using model=%s", model)

    def list_models_from_client(c: "genai.Client"):
        # Try common list APIs on the client to get available model ids/names
        model_names = []
        try:
            if hasattr(c, "models") and hasattr(c.models, "list_models"):
                res = c.models.list_models()
            elif hasattr(c, "models") and hasattr(c.models, "list"):
                res = c.models.list()
            elif hasattr(c, "list_models"):
                res = c.list_models()
            else:
                return model_names

            # `res` may be an iterable or a response with `.models` or `.data`
            if hasattr(res, "models"):
                iterable = res.models
            elif hasattr(res, "data"):
                iterable = res.data
            else:
                iterable = res

            for m in iterable:
                # model object may expose `name`, `id` or `model`
                name = None
                try:
                    name = getattr(m, "name", None) or getattr(m, "id", None) or getattr(m, "model", None)
                except Exception:
                    pass
                if not name and isinstance(m, (dict,)):
                    name = m.get("name") or m.get("id") or m.get("model")
                if name:
                    model_names.append(str(name))
        except Exception:
            pass
        return model_names

    def choose_model(c: "genai.Client", preferred: list[str]) -> str:
        available = list_models_from_client(c)
        # try to find first preferred model present
        for p in preferred:
            for a in available:
                if a.lower() == p.lower() or p.lower() in a.lower() or a.lower() in p.lower():
                    return a
        # fallback: return first available gemini model that looks like it supports text
        for a in available:
            if "gemini" in a.lower() and any(k in a.lower() for k in ("flash", "pro", "2.5", "3")):
                return a
        # if nothing matches, return empty
        return ""

    preferred_models = [model, "gemini-3-flash", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-flash-latest"]

    try:
        resp = client.models.generate_content(model=model, contents=prompt)
    except Exception as e:
        # If model not found or unsupported for this API, try to discover a working model and retry
        msg = str(e)
        if "NOT_FOUND" in msg or "not found" in msg.lower() or "is not found" in msg.lower():
            fallback = choose_model(client, preferred_models)
            if fallback and fallback != model:
                try:
                    logger.info("generate_summary_with_gemini: retrying with fallback model=%s", fallback)
                    resp = client.models.generate_content(model=fallback, contents=prompt)
                except Exception:
                    raise
            else:
                # include available models in the error to help debugging
                avail = list_models_from_client(client)
                raise RuntimeError(f"Model '{model}' not available and no suitable fallback found. Available models: {avail}") from e
        else:
            raise

    # Response objects from the GenAI client may expose `.text` or `.candidates`
    if hasattr(resp, "text") and resp.text:
        logger.info("generate_summary_with_gemini: got text output, len=%d", len(resp.text or ""))
        return resp.text
    if hasattr(resp, "candidates") and isinstance(resp.candidates, (list, tuple)) and len(resp.candidates) > 0:
        first = resp.candidates[0]
        logger.info("generate_summary_with_gemini: candidates returned, candidates_len=%d", len(resp.candidates))
        # try common attrs
        for attr in ("text", "output", "content"):
            if hasattr(first, attr) and getattr(first, attr):
                return getattr(first, attr)
        # attempt to stringify
        return str(first)
    return str(resp)


def generate_audio_with_gemini(text: str, gemini_api_key: str) -> tuple[bytes, str]:
    """Generate audio using Gemini's audio model (placeholder).

    Replace `GEMINI_AUDIO_ENDPOINT` with the real Gemini audio endpoint. This
    function expects either a JSON with base64 under `audio` or a direct audio response.
    """
    # Use google-genai client for audio generation if available
    model = os.environ.get("GEMINI_AUDIO_MODEL", "gemini-2.5-pro-tts")
    try:
        from google import genai
        from google.genai import types
    except Exception:
        raise RuntimeError(
            "google-genai client not installed. Install it with `pip install google-genai` "
            "or set GEMINI_AUDIO_ENDPOINT to a valid REST endpoint."
        )

    client = genai.Client(api_key=gemini_api_key) if gemini_api_key else genai.Client()

    def list_models_from_client(c: "genai.Client"):
        model_names = []
        try:
            if hasattr(c, "models") and hasattr(c.models, "list_models"):
                res = c.models.list_models()
            elif hasattr(c, "models") and hasattr(c.models, "list"):
                res = c.models.list()
            elif hasattr(c, "list_models"):
                res = c.list_models()
            else:
                return model_names

            if hasattr(res, "models"):
                iterable = res.models
            elif hasattr(res, "data"):
                iterable = res.data
            else:
                iterable = res

            for m in iterable:
                name = None
                try:
                    name = getattr(m, "name", None) or getattr(m, "id", None) or getattr(m, "model", None)
                except Exception:
                    pass
                if not name and isinstance(m, (dict,)):
                    name = m.get("name") or m.get("id") or m.get("model")
                if name:
                    model_names.append(str(name))
        except Exception:
            pass
        return model_names

    def choose_audio_model(c: "genai.Client", preferred: list[str]) -> str:
        available = list_models_from_client(c)
        # Prefer exact or substring matches from preferred list
        for p in preferred:
            for a in available:
                if a.lower() == p.lower() or p.lower() in a.lower() or a.lower() in p.lower():
                    # ensure candidate seems audio-capable
                    if any(tok in a.lower() for tok in ("tts", "audio", "speech", "voice", "text_to_speech")):
                        return a
        # Otherwise pick the first model that clearly advertises TTS/audio capabilities
        for a in available:
            if any(tok in a.lower() for tok in ("tts", "audio", "speech", "voice", "text_to_speech")):
                return a
        return ""

    preferred_audio_models = [model, "gemini-2.5-pro-tts", "gemini-2.5-flash-tts"]

    voice = os.environ.get("GEMINI_TTS_VOICE", "Kore")

    logger.info("generate_audio_with_gemini: request audio model=%s voice=%s", model, voice)

    def _call_generate(mod_name: str):
        return client.models.generate_content(
            model=mod_name,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                    )
                ),
            ),
        )

    # First attempt with configured model; on NOT_FOUND or invalid-output errors, retry with stricter audio-model fallbacks
    try:
        response = _call_generate(model)
    except Exception as e:
        msg = str(e)
        # If model isn't found, or it doesn't support audio, try to find a true TTS model and retry
        if any(x in msg.lower() for x in ("not found", "not_found", "is not found", "model not found")) or (
            "only supports text output" in msg.lower() or "invalid_argument" in msg.lower()
        ):
            avail = list_models_from_client(client)
            fallback = choose_audio_model(client, preferred_audio_models)
            if fallback and fallback != model:
                try:
                    logger.info("generate_audio_with_gemini: retrying audio generation with fallback=%s", fallback)
                    response = _call_generate(fallback)
                except Exception as e2:
                    # If fallback failed due to model supporting only text, try searching for any audio-capable model
                    msg2 = str(e2).lower()
                    if "only supports text" in msg2 or "invalid_argument" in msg2:
                        # discover explicit audio-capable models
                        audio_candidates = [a for a in avail if any(tok in a.lower() for tok in ("tts", "audio", "speech", "voice", "text_to_speech"))]
                        for candidate in audio_candidates:
                            if candidate == fallback:
                                continue
                            try:
                                logger.info("generate_audio_with_gemini: trying audio candidate=%s", candidate)
                                response = _call_generate(candidate)
                                break
                            except Exception:
                                continue
                        else:
                            raise RuntimeError(f"No working audio-capable model found. Tried: {fallback} and candidates: {audio_candidates}") from e2
                    else:
                        raise
            else:
                raise RuntimeError(f"Audio model '{model}' not available and no suitable TTS fallback found. Available models: {avail}") from e
        else:
            # unknown error — re-raise
            raise

    # Extract audio payload from response candidates if present
    def normalize_audio(obj) -> bytes:
        # obj may be bytes, bytearray, memoryview, list[int], or base64 str
        if obj is None:
            return b""
        if isinstance(obj, (bytes, bytearray, memoryview)):
            b = bytes(obj)
            # Try to detect and decode base64-encoded bytes (some SDKs return bytes containing base64 text)
            try:
                decoded = base64.b64decode(b, validate=True)
                sigs = [b'RIFF', b'ID3', b'OggS', b'fLaC', b'ftyp', b'\xff\xfb', b'\xff\xf3']
                if any(decoded.startswith(s) for s in sigs):
                    return decoded
            except Exception:
                pass
            # Last attempt: try non-validating base64 decode and check signatures
            try:
                decoded2 = base64.b64decode(b)
                if any(decoded2.startswith(s) for s in sigs):
                    return decoded2
            except Exception:
                pass
            return b
        if isinstance(obj, str):
            # try base64 decode, fallback to utf-8 bytes
            try:
                return base64.b64decode(obj)
            except Exception:
                return obj.encode("utf-8")
        if isinstance(obj, (list, tuple)) and all(isinstance(x, int) for x in obj):
            return bytes(obj)
        # last resort
        try:
            return str(obj).encode("utf-8")
        except Exception:
            return b""

    audio_bytes = b""
    try:
        candidate = response.candidates[0]
        parts = getattr(candidate.content, "parts", None)
        if parts and len(parts) > 0 and hasattr(parts[0], "inline_data"):
            data = parts[0].inline_data.data
            audio_bytes = normalize_audio(data)
            logger.info("generate_audio_with_gemini: extracted inline_data, bytes_len=%d", len(audio_bytes))
    except Exception:
        logger.exception("generate_audio_with_gemini: error extracting candidate inline_data")
        audio_bytes = b""

    # If still empty, check response.text or string payloads
    if (not audio_bytes) and hasattr(response, "text") and response.text:
        audio_bytes = normalize_audio(response.text)

    # Determine mime type from requested format env var
    fmt = os.environ.get("GEMINI_TTS_FORMAT", "wav").lower()
    if fmt in ("wav", "audio/wav", "audio/wave"):
        mime = "audio/wav"
        ext = "wav"
    elif fmt in ("mp3", "audio/mp3", "audio/mpeg"):
        mime = "audio/mpeg"
        ext = "mp3"
    else:
        # default to wav
        mime = f"audio/{fmt}"
        ext = fmt

    # If the payload has leading null bytes (some SDK responses include padding), strip them
    try:
        if audio_bytes:
            first_nonzero = next((i for i, x in enumerate(audio_bytes) if x != 0), None)
            if first_nonzero and first_nonzero > 0:
                logger.info("generate_audio_with_gemini: trimming %d leading null bytes", first_nonzero)
                trimmed = audio_bytes[first_nonzero:]
                # detect common signatures to set mime/ext heuristically
                sig_map = {
                    b"RIFF": ("audio/wav", "wav"),
                    b"ID3": ("audio/mpeg", "mp3"),
                    b"OggS": ("audio/ogg", "ogg"),
                    b"fLaC": ("audio/flac", "flac"),
                    b"ftyp": ("audio/mp4", "m4a"),
                    b"\xff\xfb": ("audio/mpeg", "mp3"),
                    b"\xff\xf3": ("audio/mpeg", "mp3"),
                }
                for s, mt in sig_map.items():
                    if trimmed.startswith(s):
                        mime, ext = mt
                        audio_bytes = trimmed
                        break
                else:
                    # if no signature matched, still keep trimmed bytes (more likely to play)
                    audio_bytes = trimmed
    except Exception:
        logger.exception("generate_audio_with_gemini: error while trimming/detecting audio signature")

    # If payload lacks a RIFF header, attempt to wrap raw PCM into a WAV container
    try:
        if audio_bytes and not audio_bytes.startswith(b"RIFF"):
            import io
            import wave
            # Guess common params: 16-bit PCM, mono, 24kHz (configurable via env)
            sampwidth = 2
            nchannels = 1
            framerate = int(os.environ.get("GEMINI_TTS_SR", "24000"))
            frame_bytes = sampwidth * nchannels
            if len(audio_bytes) > frame_bytes * 10:
                trunc = (len(audio_bytes) // frame_bytes) * frame_bytes
                raw_trunc = audio_bytes[:trunc]
                bio = io.BytesIO()
                with wave.open(bio, "wb") as w:
                    w.setnchannels(nchannels)
                    w.setsampwidth(sampwidth)
                    w.setframerate(framerate)
                    w.writeframes(raw_trunc)
                wrapped = bio.getvalue()
                logger.info("generate_audio_with_gemini: wrapped raw PCM into WAV (frames=%d sr=%d)", trunc // frame_bytes, framerate)
                audio_bytes = wrapped
                mime = "audio/wav"
                ext = "wav"
                # save wrapped debug file
                try:
                    with open(LOG_DIR / f"audio-wrapped.{ext}", "wb") as wf:
                        wf.write(audio_bytes)
                    logger.info("generate_audio_with_gemini: wrote wrapped audio %s", LOG_DIR / f"audio-wrapped.{ext}")
                except Exception:
                    logger.exception("generate_audio_with_gemini: failed to write wrapped audio file")
    except Exception:
        logger.exception("generate_audio_with_gemini: error while attempting to wrap raw PCM into WAV")

    # Debug dump: save response structure and audio to logs for troubleshooting
    try:
        debug = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "model": model,
            "voice": voice,
            "mime": mime,
            "audio_len": len(audio_bytes),
        }

        # candidate summary
        try:
            debug_candidates = []
            for c in getattr(response, "candidates", []) or []:
                cinfo = {"has_content": hasattr(c, "content")}
                try:
                    parts = getattr(c.content, "parts", None)
                    cinfo["parts_count"] = len(parts) if parts is not None else 0
                except Exception:
                    cinfo["parts_count"] = None
                    # Try to capture more details about parts and inline data
                    try:
                        part_details = []
                        if parts:
                            for p in parts:
                                pd = {}
                                pd["content_type"] = getattr(p, "content_type", None)
                                if hasattr(p, "inline_data"):
                                    idata = p.inline_data
                                    pd["inline_has_data"] = hasattr(idata, "data")
                                    try:
                                        raw = getattr(idata, "data")
                                        pd["inline_type"] = type(raw).__name__
                                        if isinstance(raw, (bytes, bytearray)):
                                            pd["inline_len"] = len(raw)
                                            # sample first bytes (hex) truncated
                                            pd["inline_head_hex"] = raw[:16].hex()
                                        elif isinstance(raw, str):
                                            pd["inline_len"] = len(raw)
                                            pd["inline_head"] = raw[:64]
                                        elif isinstance(raw, (list, tuple)):
                                            pd["inline_len"] = len(raw)
                                        else:
                                            pd["inline_repr"] = str(raw)[:100]
                                    except Exception:
                                        pd["inline_error"] = True
                                part_details.append(pd)
                        if part_details:
                            cinfo["parts"] = part_details
                    except Exception:
                        cinfo["parts_inspect_error"] = True
                    debug_candidates.append(cinfo)
            debug["candidates"] = debug_candidates
        except Exception:
            debug["candidates"] = "error-inspecting-candidates"

        dbg_path = LOG_DIR / f"genai_response_{int(datetime.utcnow().timestamp())}.json"
        with open(dbg_path, "w", encoding="utf-8") as f:
            json.dump(debug, f, indent=2)
        logger.info("generate_audio_with_gemini: debug written %s", dbg_path)

        # Save audio file if present for manual inspection
        if audio_bytes:
            audio_path = LOG_DIR / f"audio-debug.{ext}"
            with open(audio_path, "wb") as af:
                af.write(audio_bytes)
            logger.info("generate_audio_with_gemini: wrote audio debug file %s size=%d", audio_path, audio_path.stat().st_size)
    except Exception:
        logger.exception("generate_audio_with_gemini: failed to write debug files")

    return audio_bytes, mime


# Generate Button
gemini_key = os.environ.get("GEMINI_API_KEY", "")
jina_key = os.environ.get("JINA_API_KEY", "")

if st.button("🎙️ Generate Podcast", disabled=not all([gemini_key, jina_key])):
    if not url.strip():
        st.warning("Please enter a blog URL")
    else:
        with st.spinner("Scraping blog and generating podcast..."):
            try:
                # Keys are read from environment; ensure they exist
                # (No UI input is stored back to env for security.)

                # 1) Scrape article via Jina Reader
                article_text = fetch_article_with_jina(url, jina_key)

                # 2) Summarize with Gemini (Gemma 3 27b)
                summary = generate_summary_with_gemini(article_text, gemini_key)

                if summary:
                    # 3) Generate audio with Gemini audio model
                    audio_bytes, mime = generate_audio_with_gemini(summary, gemini_key)

                    # Display audio
                    st.success("Podcast generated! 🎧")
                    st.audio(audio_bytes, format=mime)

                    # Download button - choose extension from mime
                    ext = "mp3" if "mpeg" in mime or "mp3" in mime else "wav"
                    st.download_button(
                        "Download Podcast",
                        audio_bytes,
                        f"podcast.{ext}",
                        mime
                    )

                    # Show summary
                    with st.expander("📄 Podcast Summary"):
                        st.write(summary)
                else:
                    st.error("Failed to generate summary")

            except Exception as e:
                st.error(f"Error: {e}")
