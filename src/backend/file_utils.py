import hashlib, os, mimetypes
try:
    import magic
    _MAGIC = magic.Magic(mime=True)
except Exception:
    _MAGIC = None

def sha256_file(fp) -> str:
    h = hashlib.sha256()
    for chunk in iter(lambda: fp.read(8192), b''):
        h.update(chunk)
    fp.seek(0)
    return h.hexdigest()

def sniff_mime(path: str, filename: str) -> str:
    if _MAGIC:
        return _MAGIC.from_file(path)
    mt, _ = mimetypes.guess_type(filename)
    return mt or 'application/octet-stream'
