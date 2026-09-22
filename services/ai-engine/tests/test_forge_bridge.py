"""Check the LUMA-to-Forge request and response boundary."""

import base64
import json
import sys
from io import BytesIO
from pathlib import Path

import pytest
import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402


def _valid_png_base64():
    output = BytesIO()
    Image.new("RGB", (2, 2), (20, 80, 140)).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


VALID_PNG = _valid_png_base64()


def test_generation_forwards_defaults_and_extracts_real_forge_seed(monkeypatch):
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"images": [VALID_PNG], "info": json.dumps({"seed": 42})}

    def post(url, json, timeout):
        sent.update(url=url, body=json, timeout=timeout)
        return Response()

    monkeypatch.setattr(requests, "post", post)
    client = create_app({"TESTING": True, "FORGE_URL": "http://forge-host:7860"}).test_client()
    response = client.post("/forge/txt2img", json={"prompt": "a tree"})

    assert response.status_code == 200
    assert response.json == {"images": [VALID_PNG], "seed_used": 42}
    assert sent["url"] == "http://forge-host:7860/sdapi/v1/txt2img"
    assert sent["body"]["cfg_scale"] == 8
    assert sent["body"]["seed"] == -1
    assert sent["body"]["sampler_name"] == "DPM++ 2M"
    assert sent["body"]["scheduler"] == "Karras"
    assert sent["timeout"] == 120


@pytest.mark.parametrize("body,expected_sampler,expected_scheduler", [
    ({"sampler_name": "DPM++ 2M Karras"}, "DPM++ 2M", "Karras"),
    ({"sampler_name": "DPM++ SDE Karras"}, "DPM++ SDE", "Karras"),
    ({"sampler_name": "DPM++ 2M SDE Karras"}, "DPM++ 2M SDE", "Karras"),
    ({"sampler_name": "Euler a", "scheduler": "karras"}, "Euler a", "Karras"),
    ({"scheduler": "Exponential"}, "DPM++ 2M", "Exponential"),
])
def test_scheduler_and_legacy_sampler_are_forwarded_separately(monkeypatch, body, expected_sampler, expected_scheduler):
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"images": [VALID_PNG], "info": json.dumps({"seed": 42})}

    def post(url, json, timeout):
        sent.update(json)
        return Response()

    monkeypatch.setattr(requests, "post", post)
    response = create_app({"TESTING": True, "FORGE_URL": "http://forge-host:7860"}).test_client().post(
        "/forge/txt2img", json={"prompt": "a tree", **body}
    )
    assert response.status_code == 200
    assert sent["sampler_name"] == expected_sampler
    assert sent["scheduler"] == expected_scheduler


@pytest.mark.parametrize("body", [
    {"scheduler": ""},
    {"scheduler": None},
    {"scheduler": 123},
    {"sampler_name": "DPM++ 2M Karras", "scheduler": "Exponential"},
])
def test_invalid_or_conflicting_scheduler_is_rejected_before_forge(monkeypatch, body):
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: pytest.fail("Forge was called"))
    response = create_app({"TESTING": True}).test_client().post(
        "/forge/txt2img", json={"prompt": "a tree", **body}
    )
    assert response.status_code == 400


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


def test_explicit_parameters_are_forwarded(monkeypatch):
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"images": [VALID_PNG], "info": json.dumps({"seed": 123})}

    def post(url, json, timeout):
        sent.update(json)
        return Response()

    monkeypatch.setattr(requests, "post", post)
    body = {"prompt": "(tree:1.2)", "negative_prompt": "blur", "steps": 30,
            "cfg_scale": 7.5, "sampler_name": "Euler a", "seed": 123,
            "width": 768, "height": 512}
    response = create_app({"TESTING": True, "FORGE_URL": "http://forge-host:7860"}).test_client().post(
        "/forge/txt2img", json=body
    )
    assert response.status_code == 200
    assert sent == body


@pytest.mark.parametrize("result", [
    {"images": [VALID_PNG]},
    {"images": [], "seed_used": 123},
    {"images": [VALID_PNG], "seed_used": -1},
    {"images": ["not-base64!!!"], "seed_used": 123},
    {"images": [base64.b64encode(b"not an image").decode("ascii")], "seed_used": 123},
])
def test_unusable_forge_response_is_bad_gateway(monkeypatch, result):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return result

    monkeypatch.setattr(requests, "post", lambda *a, **kw: Response())
    response = create_app({"TESTING": True, "FORGE_URL": "http://forge-host:7860"}).test_client().post(
        "/forge/txt2img", json={"prompt": "a tree"}
    )
    assert response.status_code == 502


def test_unreachable_forge_is_bad_gateway(monkeypatch):
    def disconnected(*args, **kwargs):
        raise requests.ConnectionError("Forge is offline")

    monkeypatch.setattr(requests, "post", disconnected)
    response = create_app({"TESTING": True, "FORGE_URL": "http://forge-host:7860"}).test_client().post(
        "/forge/txt2img", json={"prompt": "a tree"}
    )
    assert response.status_code == 502
