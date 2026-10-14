"""Check public release metadata, documentation links, and repository hygiene."""
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors = []
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    version = package["version"]
    backend = re.search(r'app_version: str = "([^"]+)"', (ROOT / "backend/app/config.py").read_text(encoding="utf-8"))
    if not backend or {backend[1], lock["version"], lock["packages"][""]["version"]} != {version}:
        errors.append("Backend, frontend, and lockfile release versions must match.")
    if f"## {version}" not in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"):
        errors.append("The release version needs a changelog entry.")
    dependencies = package["dependencies"]
    if dependencies["react"] != dependencies["react-dom"]:
        errors.append("React and React DOM must use the same pinned version.")

    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, capture_output=True, encoding="utf-8",
    )
    files = sorted({name for name in result.stdout.split("\0") if name and (ROOT / name).is_file()})
    markdown = [name for name in files if name.endswith(".md")]
    for name in files:
        path = Path(name)
        if (name.startswith("data/") and path.name != ".gitkeep") or path.suffix.lower() in {".dcm", ".dicom", ".sqlite", ".sqlite3", ".db", ".pt", ".pth", ".onnx", ".safetensors", ".gguf"}:
            errors.append(f"Runtime data or model weights must not be published: {name}")
        if path.name.startswith(".env") and path.name != ".env.example":
            errors.append(f"Private environment configuration must not be published: {name}")

    for name in markdown:
        source = (ROOT / name).read_text(encoding="utf-8")
        if re.search(r"[A-Za-z]:[\\/]Users[\\/]", source):
            errors.append(f"Remove personal absolute paths from {name}.")
        # Ignore code examples; their placeholder paths are not documentation links.
        source = re.sub(r"```.*?```", "", source, flags=re.DOTALL)
        for destination in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)", source):
            target = urlsplit(destination.strip("<>"))
            if target.scheme or target.netloc or not target.path:
                continue
            relative = unquote(target.path)
            resolved = (ROOT / relative.lstrip("/")) if relative.startswith("/") else (ROOT / name).parent / relative
            if not resolved.resolve().is_relative_to(ROOT) or not resolved.exists():
                errors.append(f"Broken local link in {name}: {destination}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Release {version}: versions, React pair, {len(markdown)} Markdown files, local links, and publication boundaries passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
