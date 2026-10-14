"""Isolated, bounded smoke test. Never receives patient data or remote code."""
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image

from app.ai_setup.catalog import TXRV_ID
from app.config import get_settings
from app.vision.torchxrayvision_classifier import run_torchxrayvision_classifier


def main():
    with tempfile.TemporaryDirectory(dir=get_settings().cache_dir) as folder:
        image = Image.new("L", (256, 256))
        image.putdata([x % 256 for x in range(256 * 256)])
        path = Path(folder) / "synthetic-test.png"
        image.save(path)
        if len(sys.argv) > 2 and sys.argv[1] == "--classifier":
            result = run_torchxrayvision_classifier(str(path), sys.argv[2])
        elif len(sys.argv) > 1:
            from app.vision.ultralytics_detector import run_msk_fracture_detector
            result = run_msk_fracture_detector(str(path), sys.argv[1], cpu_only=True)
        else:
            result = run_torchxrayvision_classifier(str(path), TXRV_ID)
    print(json.dumps({"status": result["status"], "findings": len(result.get("findings", [])), "detail": result.get("detail", "Model test failed.")}))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
