"""Shared authenticated client for AI-engine route tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402


TEST_ENGINE_KEY = "test-engine-key"


def authenticated_client(config=None):
    app = create_app({"TESTING": True, "AI_ENGINE_KEY": TEST_ENGINE_KEY, **(config or {})})
    client = app.test_client()
    client.environ_base["HTTP_X_LUMA_ENGINE_KEY"] = TEST_ENGINE_KEY
    return client
