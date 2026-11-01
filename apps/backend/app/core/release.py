"""Content identity for deployable source; excludes secrets and generated output."""
import hashlib
import os
from pathlib import Path

EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".css", ".json", ".yaml", ".yml", ".toml",
              ".woff", ".woff2", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".txt"}


def source_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    files = []
    for directory, folders, names in os.walk(root):
        folders[:] = sorted(name for name in folders if not name.startswith(".") and name not in {"node_modules", "__pycache__", "tests"})
        for name in names:
            if name.startswith(".") or name == "next-env.d.ts":
                continue
            file = Path(directory) / name
            if file.suffix in EXTENSIONS or name == "uv.lock":
                files.append(file)
    for file in sorted(files):
        digest.update(file.relative_to(root).as_posix().encode() + b"\0")
        digest.update(file.read_bytes() + b"\0")
    return digest.hexdigest()
