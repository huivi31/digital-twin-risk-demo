import os

API_CONFIG = {
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "api_key": os.environ.get("OPENAI_API_KEY", "")
}
