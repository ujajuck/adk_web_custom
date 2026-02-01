import os, json
from base64 import b64decode

def _to_bytes_from_part(part) -> bytes:
    b = getattr(part, "blob", None)
    if b is not None:
        data_attr = getattr(b, "data", None)
        if isinstance(data_attr, (bytes, bytearray)): return bytes(data_attr)
        if isinstance(data_attr, str):
            try: return b64decode(data_attr)
            except Exception: return data_attr.encode("utf-8")
        if isinstance(b, (bytes, bytearray)): return bytes(b)
        if isinstance(b, str):
            try: return b64decode(b)
            except Exception: return b.encode("utf-8")
    t = getattr(part, "text", None)
    if t is not None: return t.encode("utf-8")
    raise TypeError("Unsupported content part format")
