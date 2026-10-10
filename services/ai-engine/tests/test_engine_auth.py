"""Only the backend should be able to call AI-engine work routes."""

import base64
from io import BytesIO

import pytest
from PIL import Image

from app import _validate_bind_host, create_app


def _image_base64():
    output = BytesIO()
    Image.new("RGB", (2, 2), "red").save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_health_remains_public_without_configured_key():
    client = create_app({"TESTING": True, "AI_ENGINE_KEY": None}).test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


@pytest.mark.parametrize("header,status", [
    ({}, 401),
    ({"X-LUMA-Engine-Key": "wrong-key"}, 401),
    ({"X-LUMA-Engine-Key": "right-key"}, 200),
])
def test_pipeline_requires_correct_engine_key(header, status):
    client = create_app({"TESTING": True, "AI_ENGINE_KEY": "right-key"}).test_client()
    response = client.post(
        "/pipeline/04_features/color_palette",
        json={"image": _image_base64(), "params": {"colors": 1}},
        headers=header,
    )
    assert response.status_code == status


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_configuration_fails_closed_even_on_loopback(key):
    client = create_app({"TESTING": True, "AI_ENGINE_KEY": key}).test_client()
    response = client.post(
        "/pipeline/04_features/color_palette",
        json={"image": _image_base64()},
        headers={"X-LUMA-Engine-Key": "any-key"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("method,path", [
    ("get", "/forge/checkpoints"),
    ("post", "/forge/txt2img"),
    ("post", "/forge/img2img"),
])
def test_forge_routes_also_require_engine_key(method, path):
    client = create_app({"TESTING": True, "AI_ENGINE_KEY": "right-key"}).test_client()
    assert getattr(client, method)(path).status_code == 401


def test_non_ascii_configured_key_does_not_cause_server_error():
    client = create_app({"TESTING": True, "AI_ENGINE_KEY": "clé"}).test_client()
    response = client.get("/forge/checkpoints", headers={"X-LUMA-Engine-Key": "wrong"})
    assert response.status_code == 401


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.30", "engine.example"])
def test_network_bind_requires_configured_key(host):
    for key in (None, "", "   "):
        with pytest.raises(RuntimeError, match="AI_ENGINE_KEY"):
            _validate_bind_host(host, key)
    _validate_bind_host(host, "right-key")


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.1.1", "::1", "localhost"])
def test_loopback_bind_can_start_without_key(host):
    _validate_bind_host(host, None)
