"""Build a reproducible, installable integration archive using tracked files."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = Path("custom_components/mousetrap_manager")


def build(version: str | None = None, output: Path | None = None) -> Path:
    manifest = json.loads((ROOT / INTEGRATION / "manifest.json").read_text())
    version = version or manifest["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or manifest["version"] != version:
        raise ValueError("Release version must match the integration manifest")
    card = ROOT / INTEGRATION / "frontend/mousetrap-manager-card.js"
    if f'const VERSION = "{version}";' not in card.read_text():
        raise ValueError("Bundled frontend version does not match the release")
    if card.read_bytes() != (ROOT / "dist/mousetrap-manager-card.js").read_bytes():
        raise ValueError("The two frontend copies differ")
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", str(INTEGRATION)], cwd=ROOT
    ).decode().split("\0")
    files = {
        str(Path("mousetrap_manager") / Path(path).relative_to(INTEGRATION)): (ROOT / path).read_bytes()
        for path in paths if path
    }
    for source, destination in [
        ("LICENSE", "LICENSE"),
        ("docs/UPSTREAM.md", "UPSTREAM.md"),
        ("README.md", "INSTALL.md"),
    ]:
        files[f"mousetrap_manager/{destination}"] = (ROOT / source).read_bytes()
    output = output or ROOT / "build/releases"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"mousetrap-manager-v{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 28, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, content)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n")
    return archive


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else None))
