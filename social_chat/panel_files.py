"""Put the panel's files where GodwinMix 0.3.x looks for them.

`gmx plugin add` installs a plugin at `<plugins>/<name>/<version>/`, but the
mixer's page lists panels from `<plugins>/<name>/ui/`, one level up, so a
panel installed the ordinary way is never shown. Until the mixer reads the
versioned folder, this copies `ui/` to where the page looks, at every start.
It writes only inside this plugin's own `<plugins>/social-chat/` folder, and
only files whose bytes differ. A plugin run from a checkout (no version
folder above it) is left alone.
"""
import os
import shutil

NAME = "social-chat"


def target_for(root):
    """`<plugins>/social-chat/ui` when `root` is a versioned install, else None."""
    root = os.path.abspath(root)
    parent = os.path.dirname(root)
    if os.path.basename(parent) != NAME:
        return None
    if not os.path.isfile(os.path.join(root, "gmx-plugin.toml")):
        return None
    return os.path.join(parent, "ui")


def mirror(root):
    """Copy ui/ up a level. Answers how many files were written."""
    target = target_for(root)
    source = os.path.join(root, "ui")
    if target is None or not os.path.isdir(source):
        return 0
    written = 0
    for here, _, files in os.walk(source):
        rel = os.path.relpath(here, source)
        dest_dir = os.path.normpath(os.path.join(target, rel))
        os.makedirs(dest_dir, exist_ok=True)
        for name in files:
            src, dst = os.path.join(here, name), os.path.join(dest_dir, name)
            if _same(src, dst):
                continue
            shutil.copyfile(src, dst)
            written += 1
    return written


def _same(a, b):
    try:
        if os.path.getsize(a) != os.path.getsize(b):
            return False
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False
