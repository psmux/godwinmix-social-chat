"""Keys at rest in settings.json.

On Windows each key is encrypted with DPAPI for the signed in user, so the
file is useless copied to another account or machine. On macOS and Linux the
file is created readable by its owner only (mode 600) and the keys are kept as
they are: without a key store to lean on, encrypting them here would only
move the key next to the lock.
"""
import base64
import os
import sys

PREFIX = "dpapi:"


def _dpapi():
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt = ctypes.windll.crypt32
    kernel = ctypes.windll.kernel32

    def run(fn, data):
        buffer = ctypes.create_string_buffer(data, len(data))
        blob_in = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        blob_out = Blob()
        if not fn(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out)):
            raise OSError("DPAPI refused")
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))

    def protect(data):
        return run(crypt.CryptProtectData, data)

    def unprotect(data):
        return run(crypt.CryptUnprotectData, data)

    return protect, unprotect


def available():
    return sys.platform == "win32" and not os.environ.get("SOCIAL_CHAT_NO_DPAPI")


def lock(value):
    if not value or not available():
        return value
    try:
        protect, _ = _dpapi()
        return PREFIX + base64.b64encode(protect(value.encode("utf-8"))).decode("ascii")
    except (OSError, AttributeError):
        return value


def unlock(value):
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return value
    try:
        _, unprotect = _dpapi()
        return unprotect(base64.b64decode(value[len(PREFIX):])).decode("utf-8")
    except (OSError, AttributeError, ValueError):
        return ""  # another user's or another machine's file: the key must be typed again
