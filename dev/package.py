#!/usr/bin/env python3
"""Build the release archives: one per platform, each the same pure Python plugin.

    python dev/package.py dist

Writes social-chat-<version>-<platform>.tar.gz for Linux and macOS and a .zip
for Windows, each holding one `social-chat/` folder with the manifest at its
top, which is how `gmx plugin add` and the gallery expect a release asset.
Also writes SHA256SUMS. The version is read from gmx-plugin.toml.
"""
import hashlib
import io
import os
import re
import sys
import tarfile
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "social-chat"
PLATFORMS = ["windows-x86_64", "linux-x86_64", "linux-aarch64", "macos-aarch64", "macos-x86_64"]
SHIP = ["gmx-plugin.toml", "main.py", "README.md", "LICENSE", "social_chat", "ui", "graphics",
        "schemas", "skills", "docs"]


def version():
    with open(os.path.join(ROOT, "gmx-plugin.toml"), encoding="utf-8") as f:
        return re.search(r'^version = "([^"]+)"', f.read(), re.M).group(1)


def files():
    for entry in SHIP:
        path = os.path.join(ROOT, entry)
        if os.path.isfile(path):
            yield entry
            continue
        for here, dirs, names in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in sorted(names):
                if not name.endswith(".pyc"):
                    yield os.path.relpath(os.path.join(here, name), ROOT).replace(os.sep, "/")


def build(out, platform, stamp):
    base = "%s-%s-%s" % (NAME, version(), platform)
    listed = list(files())
    if platform.startswith("windows"):
        path = os.path.join(out, base + ".zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for rel in listed:
                info = zipfile.ZipInfo("%s/%s" % (NAME, rel), time.gmtime(stamp)[:6])
                info.external_attr = 0o644 << 16
                with open(os.path.join(ROOT, rel), "rb") as f:
                    z.writestr(info, f.read(), zipfile.ZIP_DEFLATED)
        return path
    path = os.path.join(out, base + ".tar.gz")
    with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as t:
        for rel in listed:
            with open(os.path.join(ROOT, rel), "rb") as f:
                data = f.read()
            info = tarfile.TarInfo("%s/%s" % (NAME, rel))
            info.size, info.mtime = len(data), stamp
            info.mode = 0o755 if rel in ("main.py",) else 0o644
            t.addfile(info, io.BytesIO(data))
    return path


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist")
    os.makedirs(out, exist_ok=True)
    stamp = int(os.environ.get("SOURCE_DATE_EPOCH", "1790000000"))
    sums = []
    for platform in PLATFORMS:
        path = build(out, platform, stamp)
        with open(path, "rb") as f:
            sums.append("%s  %s" % (hashlib.sha256(f.read()).hexdigest(), os.path.basename(path)))
        print(path)
    with open(os.path.join(out, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sums) + "\n")


if __name__ == "__main__":
    main()
