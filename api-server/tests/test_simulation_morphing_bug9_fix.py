import base64
import io

from PIL import Image

from services import simulation_morphing as sm


def _png_bytes(color: str = "#88aaff") -> bytes:
    img = Image.new("RGB", (32, 32), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_resolve_image_model_falls_back_to_gpt_image_1(monkeypatch):
    monkeypatch.setattr(sm.settings, "openai_image_model", "dall-e-3")
    assert sm._resolve_image_model() == "gpt-image-1"


def test_build_simulation_prompt_includes_zone_and_intensity():
    prompt = sm._build_simulation_prompt("lèvres", 55)
    assert "lèvres" in prompt
    assert "55/100" in prompt
    assert "Preserve identity perfectly" in prompt


def test_generate_ai_simulation_image_calls_openai_edit_endpoint(monkeypatch):
    expected = _png_bytes("#55cc88")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"b64_json": base64.b64encode(expected).decode("ascii")}
                ]
            }

    def fake_post(url, headers, data, files, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        captured["files"] = files
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(sm.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(sm.settings, "openai_image_model", "gpt-image-1")
    monkeypatch.setattr(sm.requests, "post", fake_post)

    result = sm._generate_ai_simulation_image(_png_bytes(), zone="pommettes", intensite=35)

    assert result == expected
    assert captured["url"] == sm.OPENAI_IMAGE_EDIT_ENDPOINT
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["data"]["model"] == "gpt-image-1"
    assert "pommettes" in captured["data"]["prompt"]
    assert captured["files"]["image"][0].endswith(".png")
