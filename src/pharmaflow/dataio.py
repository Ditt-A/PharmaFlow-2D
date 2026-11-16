import hashlib

def md5_file(path):
    digest = hashlib.md5()  # MD5 is used only for the public Zenodo checksum
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
