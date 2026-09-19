"""Check the LUMA-to-Forge request and response boundary."""

import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402


def test_generation_forwards_defaults_and_extracts_real_forge_seed(monkeypatch):
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"images": ["image-base64"], "info": json.dumps({"seed": 42})}

    def post(url, json, timeout):
        sent.update(url=url, body=json, timeout=timeout)
        return Response()

    monkeypatch.setattr(requests, "post", post)
    client = create_app({"TESTING": True, "FORGE_URL": "http://forge-host:7860"}).test_client()
    response = client.post("/forge/txt2img", json={"prompt": "a tree"})

    assert response.status_code == 200
    assert response.json == {"images": ["image-base64"], "seed_used": 42}
    assert sent["url"] == "http://forge-host:7860/sdapi/v1/txt2img"
    assert sent["body"]["cfg_scale"] == 8
    assert sent["body"]["seed"] == -1
    assert sent["timeout"] == 120


@pytest.mark.parametrize("body", [{"prompt": ""}, {"prompt": "x", "steps": True}])
def test_bad_requests_never_reach_forge(monkeypatch, body):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: pytest.fail("Forge was called"))
    response = create_app({"TESTING": True}).test_client().post("/forge/txt2img", json=body)
    assert response.status_code == 400


def test_timeout_is_reported_as_gateway_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("Forge is slow")

    monkeypatch.setattr(requests, "post", timeout)
    response = create_app({"TESTING": True, "FORGE_URL": "http://forge-host:7860"}).test_client().post(
        "/forge/txt2img", json={"prompt": "a tree"}
    )
    assert response.status_code == 504


def test_missing_forge_url_is_reported_before_call(monkeypatch):
    monkeypatch.delenv("FORGE_URL", raising=False)
    monkeypatch.setattr(requests, "post", lambda *a, **kw: pytest.fail("Forge was called"))
    response = create_app({"TESTING": True}).test_client().post(
        "/forge/txt2img", json={"prompt": "a tree"}
    )
    assert response.status_code == 503
