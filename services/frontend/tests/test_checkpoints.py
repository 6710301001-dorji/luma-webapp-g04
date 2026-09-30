"""Model list success/empty/offline behavior using the real loader script."""
import json
import shutil
import subprocess
from pathlib import Path
import pytest

HERE = Path(__file__).parent
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is required")


@pytest.mark.parametrize("scenario", ["success", "empty", "offline"])
def test_checkpoint_loader(scenario):
    result = subprocess.run([NODE, str(HERE / "checkpoints_harness.js"), scenario,
                             str(HERE.parent / "js/checkpoints.js")],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    data = json.loads(result.stdout)
    assert data["requested"] == "https://backend.example/api/checkpoints"
    if scenario == "success":
        assert data["options"][1] == {"value": "<b>landscape</b> [222]", "textContent": "<b>landscape</b> [222]"}
    else:
        assert data["options"] == []
    assert data["status"] != "loading"
