#!/usr/bin/env python3
"""Image privacy scan: does any shipped image carry embedded metadata or PII-shaped text?

WHY THIS EXISTS
The text gate (`scripts/hygiene-check.sh`) skips binary files, so every PNG in
`results/cards/` and every OCR fixture was outside it. A rendered card is a plausible
carrier for an absolute path, an author tag or a hostname in a text chunk, and a fixture
screenshot is a plausible carrier for an account name typed into it.

This script closes the machine-readable half of that gap: it walks every tracked or
to-be-tracked image, lists the ancillary chunks that can carry text (tEXt/iTXt/zTXt/eXIf/
tIME/JPEG APPn/COM), and scans the raw bytes for PII-shaped strings. Pattern literals are
assembled from fragments, like the text gate, so this file never contains the strings it
screens for.

Pixels are not machine-readable: a human still has to look at a new image. This catches
metadata and embedded text, not "a name was rendered into the picture".

Usage: python3 scripts/image_privacy_check.py [repo_root]
Exit: 0 clean, 1 PII-shaped hit (metadata surfaces are reported, not fatal).
"""
from __future__ import annotations

import os
import re
import struct
import subprocess
import sys

IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")

# fragments (each is only part of the real token) — same technique as the text gate
_ORG = "".join(["ty", "sa", "is"])
PATTERNS = {
    "first-name": r"\b" + "".join(["ty", "ler"]) + r"\b",
    "surname": r"\b" + "".join(["jer", "man"]) + r"\b",
    "home-path": r"/home/[a-z][a-z0-9_-]+" + "|" + "/Us" + "ers/",
    "personal-mail": "@g" + "mail." + "|@icloud\\.",
    "tailnet": "".join(["ty", "jus", "drop"]),
    "lan-ip": r"10\.0\.0\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}",
    "tailnet-ip": r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b",
    "hostname": "".join(["all", "spark"]) + "|" + "".join(["ar", "biter"]) + "|"
                + "".join(["veri", "ton"]) + "|" + r"\bar" + "eo" + r"\b"
                + "|" + "".join(["pr", "ometheus"]),
    "internal-handle": r"\b" + "".join(["invi", "ncible"]) + r"\b",
    "org-handle-outside-url": r"\b" + _ORG + r"\b(?!/(?:slm-gauntlet)?)",
}

TEXT_CHUNKS = {"tEXt", "iTXt", "zTXt", "eXIf", "tIME"}


def png_chunks(path: str):
    out = []
    with open(path, "rb") as fh:
        if fh.read(8) != b"\x89PNG\r\n\x1a\n":
            return out
        while True:
            head = fh.read(8)
            if len(head) < 8:
                break
            length, ctype = struct.unpack(">I4s", head)
            data = fh.read(length)
            fh.read(4)  # crc
            out.append((ctype.decode("latin1"), data))
            if ctype == b"IEND":
                break
    return out


def jpeg_segments(path: str):
    out = []
    data = open(path, "rb").read()
    if not data.startswith(b"\xff\xd8"):
        return out
    i = 2
    while i + 4 < len(data):
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker in (0xD8, 0xD9):
            i += 2
            continue
        seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xE1, 0xE2, 0xED, 0xEE, 0xFE):  # exif/xmp/iptc/comment
            out.append((f"APP{marker - 0xE0}", data[i + 4:i + 2 + seglen]))
        i += 2 + seglen
    return out


def images(root: str):
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root, capture_output=True, check=True,
    ).stdout
    for name in out.split(b"\0"):
        if not name:
            continue
        rel = name.decode()
        if rel.lower().endswith(IMG_EXT):
            p = os.path.join(root, rel)
            if os.path.isfile(p):
                yield rel, p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    root = os.path.abspath(argv[0] if argv else ".")
    n = 0
    meta_surfaces = []
    hits = []
    for rel, path in images(root):
        n += 1
        ext = os.path.splitext(path)[1].lower()
        chunks = png_chunks(path) if ext == ".png" else (
            jpeg_segments(path) if ext in (".jpg", ".jpeg") else [])
        for ctype, data in chunks:
            if ctype in TEXT_CHUNKS or ctype.startswith("APP"):
                printable = "".join(ch if 32 <= ord(ch) < 127 else "." for ch in data[:200].decode("latin1"))
                meta_surfaces.append((rel, ctype, printable[:160]))
        try:
            blob = open(path, "rb").read()
        except OSError:
            continue
        text = blob.decode("latin1")
        for pname, pat in PATTERNS.items():
            m = re.search(pat, text, re.I)
            if m:
                hits.append((rel, pname, m.group(0)[:40]))
    print(f"== image privacy check: {n} image file(s) under {root}")
    print(f"metadata-bearing surfaces: {len(meta_surfaces)}")
    for rel, ctype, payload in meta_surfaces[:40]:
        print(f"  {rel} :: {ctype} :: {payload!r}")
    print(f"PII-shaped strings inside image bytes: {len(hits)}")
    for rel, pname, val in hits[:40]:
        print(f"  {rel} [{pname}] {val!r}")
    if hits:
        print("== FAILED: image carries a personal/environment identifier.")
        return 1
    print("== image privacy check: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
