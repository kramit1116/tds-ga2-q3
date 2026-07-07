import os
import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS: allow all origins for this endpoint (per task requirement)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}


def load_yaml_layer():
    try:
        with open("config.development.yaml") as f:
            data = yaml.safe_load(f) or {}
        return {k: v for k, v in data.items()}
    except FileNotFoundError:
        return {}


def map_prefixed_vars(raw: dict) -> dict:
    """Map APP_* keys (and NUM_WORKERS alias) to config keys."""
    result = {}
    for k, v in raw.items():
        if k == "NUM_WORKERS":
            result["workers"] = v
        elif k.startswith("APP_"):
            key = k[len("APP_"):].lower()  # APP_PORT -> port, APP_LOG_LEVEL -> log_level, etc.
            result[key] = v
    return result


def load_dotenv_layer():
    raw = dotenv_values(".env")  # does NOT touch os.environ
    return map_prefixed_vars(raw)


def load_os_env_layer():
    raw = {k: v for k, v in os.environ.items() if k.startswith("APP_") or k == "NUM_WORKERS"}
    return map_prefixed_vars(raw)


def coerce(key: str, value):
    if value is None:
        return None
    if key in ("port", "workers"):
        return int(value)
    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "on")
    return str(value)


@app.get("/effective-config")
async def effective_config(request: Request):
    merged = dict(DEFAULTS)
    merged.update(load_yaml_layer())
    merged.update(load_dotenv_layer())
    merged.update(load_os_env_layer())

    # CLI overrides via ?set=key=value (repeatable)
    set_params = request.query_params.getlist("set")
    for item in set_params:
        if "=" in item:
            k, v = item.split("=", 1)
            merged[k.strip()] = v.strip()

    result = {k: coerce(k, v) for k, v in merged.items()}

    # Always mask the secret, regardless of source
    result["api_key"] = "****"

    return result
