import json
import os
import tempfile
import logging

from groq import Groq

from bot.prompts import get_system_prompt

logger = logging.getLogger(__name__)

_groq_client = None


def _get_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _groq_client


def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcreve áudio OGG usando Groq Whisper. Retorna string vazia se falhar."""
    client = _get_client()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name
    try:
        with open(temp_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                file=("audio.ogg", audio_file, "audio/ogg"),
                model="whisper-large-v3",
                language="pt",
            )
        return result.text.strip()
    except Exception as e:
        logger.error(f"Erro ao transcrever áudio: {e}")
        return ""
    finally:
        os.unlink(temp_path)


def interpret_text(text: str) -> dict:
    """Interpreta o texto com LLaMA e retorna o dict de ação."""
    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": text},
        ],
        temperature=0.1,
        max_tokens=512,
    )
    content = response.choices[0].message.content.strip()

    # Remove blocos markdown caso o modelo os inclua
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    return json.loads(content)
