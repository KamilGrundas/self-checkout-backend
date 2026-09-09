"""Discover models using the stored endpoint and its credential only."""

import json
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from app.core.autolabel_credentials import inference_headers
from app.models import AutolabelSettings


class AvailableModel(BaseModel):
    id: str
    loaded: bool = False
    is_vision: bool | None = None


class AvailableModels(BaseModel):
    models: list[AvailableModel]
    active_model: str | None = None


def discover_models(stored: AutolabelSettings) -> AvailableModels:
    endpoint = stored.endpoint_url or ""
    parsed = urlsplit(endpoint)
    if not endpoint.endswith("/chat/completions") or parsed.query or parsed.fragment:
        raise ValueError("Save a chat/completions endpoint before fetching models")
    base = endpoint.removesuffix("/chat/completions")
    headers = inference_headers(stored.api_key_encrypted, endpoint)
    with httpx.Client(
        timeout=httpx.Timeout(15, connect=5), follow_redirects=False, trust_env=False
    ) as client:

        def read(path: str) -> dict[str, Any]:
            with client.stream("GET", base + path, headers=headers) as response:
                if response.is_redirect:
                    raise ValueError("Model endpoint redirects are not allowed")
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 1_048_576:
                        raise ValueError("Model response is too large")
                result = json.loads(data)
                if not isinstance(result, dict):
                    raise ValueError("Invalid model response")
                return result

        response = read("/models")
        status = read("/status")
    rows = response.get("data")
    if not isinstance(rows, list):
        raise ValueError("Invalid model list")
    loaded = status.get("loaded", [])
    loaded = loaded if isinstance(loaded, list) else []
    active = status.get("model_identifier") or status.get("active_model")
    if not isinstance(active, str) or active not in loaded:
        active = next((item for item in loaded if isinstance(item, str)), None)
    models: dict[str, AvailableModel] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            continue
        model_id = row["id"]
        if not model_id or len(model_id) > 512:
            continue
        is_active = model_id == active
        vision = status.get("is_vision") if is_active else None
        models[model_id] = AvailableModel(
            id=model_id,
            loaded=model_id in loaded or is_active,
            is_vision=vision if isinstance(vision, bool) else None,
        )
    if active not in models:
        active = next((m.id for m in models.values() if m.loaded), None)
    return AvailableModels(models=list(models.values()), active_model=active)
