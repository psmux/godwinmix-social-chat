"""Keys typed into the panel travel sealed, so the mixer never records them.

The panel reaches this plugin through the mixer's `tool.call`, and the mixer
writes every `tool.call` into its session log, arguments and all. A key sent
as plain text would sit in that log. So the panel seals it first: a
Diffie-Hellman exchange in the 2048 bit MODP group of RFC 3526 against a key
pair this process makes at start and never writes down, then SHA-256 in
counter mode with an HMAC over the result. The log holds the panel's public
number and the ciphertext, which nobody can open once this process has gone.

ui/seal.js is the other half, in the page.
"""
import hashlib
import hmac
import secrets

P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A0879"
    "8E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0B"
    "FF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55"
    "D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C"
    "08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF695581718"
    "3995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF", 16)
G = 2
_private = secrets.randbits(320) | 1
PUBLIC = pow(G, _private, P)


class SealError(Exception):
    pass


def public_hex():
    return format(PUBLIC, "x")


def _keys(their_hex):
    try:
        theirs = int(their_hex, 16)
    except (TypeError, ValueError):
        raise SealError("the sealed value has no public number") from None
    if not 1 < theirs < P - 1:
        raise SealError("the sealed value's public number is out of range")
    shared = pow(theirs, _private, P).to_bytes(256, "big")
    return (hashlib.sha256(b"social-chat enc" + shared).digest(),
            hashlib.sha256(b"social-chat mac" + shared).digest())


def stream(key, iv, length):
    out, counter = b"", 0
    while len(out) < length:
        out += hashlib.sha256(key + iv + counter.to_bytes(4, "big")).digest()
        counter += 1
    return out[:length]


def open_sealed(sealed):
    """The plain text inside `{pub, iv, data, tag}`, all hex."""
    if not isinstance(sealed, dict):
        raise SealError("a sealed value is an object with pub, iv, data and tag")
    enc, mac = _keys(sealed.get("pub"))
    try:
        iv, data, tag = (bytes.fromhex(sealed.get(k, "")) for k in ("iv", "data", "tag"))
    except ValueError:
        raise SealError("the sealed value is not hex") from None
    expected = hmac.new(mac, iv + data, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(expected, tag):
        raise SealError("the sealed value does not open with this plugin's key. The plugin "
                        "may have restarted since the page read its key: reopen Settings "
                        "and type it again.")
    plain = bytes(a ^ b for a, b in zip(data, stream(enc, iv, len(data))))
    return plain.decode("utf-8")


def seal(their_public_hex, text, private=None):
    """The page's half, here for the tests: seal `text` for a public number."""
    mine = private or (secrets.randbits(320) | 1)
    theirs = int(their_public_hex, 16)
    shared = pow(theirs, mine, P).to_bytes(256, "big")
    enc = hashlib.sha256(b"social-chat enc" + shared).digest()
    mac = hashlib.sha256(b"social-chat mac" + shared).digest()
    iv = secrets.token_bytes(16)
    raw = text.encode("utf-8")
    data = bytes(a ^ b for a, b in zip(raw, stream(enc, iv, len(raw))))
    tag = hmac.new(mac, iv + data, hashlib.sha256).digest()[:16]
    return {"pub": format(pow(G, mine, P), "x"), "iv": iv.hex(), "data": data.hex(),
            "tag": tag.hex()}
