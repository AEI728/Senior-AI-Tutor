"""Bounded provider calls. Credentials / raw provider bodies never reach UI or logs."""

import json
import time
import httpx
from openai import OpenAI, APIConnectionError, APITimeoutError, APIStatusError
from .config import settings


class ProviderError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def retry(call):
    cfg = settings()
    deadline = time.monotonic() + cfg.provider_timeout_seconds
    for attempt in range(cfg.max_retry_attempts + 1):
        try:
            return call()
        except (APIConnectionError, APITimeoutError, httpx.TransportError):
            code, retryable = "PROVIDER_CONNECTION", True
        except (APIStatusError, httpx.HTTPStatusError) as error:
            status = error.status_code if isinstance(error, APIStatusError) else error.response.status_code
            code = (
                "PROVIDER_AUTH"
                if status in (401, 403)
                else ("PROVIDER_QUOTA" if status in (402, 429) else "PROVIDER_UNAVAILABLE")
            )
            retryable = status in (429, 500, 502, 503, 504)
        if (
            not retryable
            or attempt >= cfg.max_retry_attempts
            or time.monotonic() + 0.4 * 2**attempt >= deadline
        ):
            raise ProviderError(code) from None
        time.sleep(0.4 * 2**attempt)
    raise ProviderError("PROVIDER_UNAVAILABLE")


def deepseek_client():
    cfg = settings()
    return OpenAI(
        api_key=cfg.deepseek_api_key,
        base_url=cfg.deepseek_base_url,
        max_retries=0,
        timeout=cfg.provider_timeout_seconds,
    )


def structured(schema_class, instructions, data):
    cfg = settings()
    parameters = schema_class.model_json_schema()
    response = retry(
        lambda: deepseek_client().chat.completions.create(
            model=cfg.deepseek_model,
            temperature=0,
            max_tokens=700,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "learning_decision",
                        "description": "返回受限的学习操作参数，业务执行由服务器核验",
                        "parameters": parameters,
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": "learning_decision"}},
            extra_body={"thinking": {"type": "disabled"}},
        )
    )
    calls = response.choices[0].message.tool_calls or []
    if len(calls) != 1 or calls[0].function.name != "learning_decision":
        raise ProviderError("INVALID_MODEL_PLAN")
    try:
        return schema_class.model_validate_json(calls[0].function.arguments), response.id
    except ValueError:
        raise ProviderError("INVALID_MODEL_PLAN") from None


def deepseek_text(instructions, data):
    r = retry(
        lambda: deepseek_client().chat.completions.create(
            model=settings().deepseek_model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
            ],
            max_tokens=500,
            temperature=0.2,
            extra_body={"thinking": {"type": "disabled"}},
        )
    )
    return r.choices[0].message.content or ""


def audio_request(endpoint, **kwargs):
    cfg = settings()
    # The /v1/tools endpoints live at the API origin, independently of chat /v1 base paths.
    from urllib.parse import urlsplit

    u = urlsplit(cfg.deepseek_base_url)
    url = f"{u.scheme}://{u.netloc}/v1/tools/{endpoint}"

    def call():
        with httpx.Client(timeout=30) as c:
            r = c.post(url, headers={"Authorization": "Bearer " + cfg.deepseek_api_key}, **kwargs)
            r.raise_for_status()
            return r

    return retry(call)


def normalize_wav(raw):
    """Streaming WAV may advertise an unknown frame count. Emit a finite PCM WAV."""
    import io
    import wave

    with wave.open(io.BytesIO(raw), "rb") as source:
        params = source.getparams()
        frames = source.readframes(source.getnframes())
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setparams(params._replace(nframes=0))
        target.writeframes(frames)
    return output.getvalue()
