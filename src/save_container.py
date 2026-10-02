"""Conservative CIM2 save container handling.

The current game format starts with UTF-16 metadata followed by a raw DEFLATE
stream. We preserve every byte outside that stream and refuse ambiguous
containers instead of producing a file that the game may reject.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
import zlib


@dataclass(frozen=True)
class PayloadLocation:
    offset: int
    compressed_size: int
    payload_size: int


def locate_payload(path: Path) -> tuple[PayloadLocation, bytes]:
    raw = path.read_bytes()
    # The thumbnail/metadata size varies. The stream is page aligned even
    # when the last page has fewer than 32 (or no) zero-padding bytes.
    candidates = set(range(0x1000, len(raw), 0x1000))
    candidates.update(match.end() for match in re.finditer(b"\x00{32,}", raw))
    hits = []
    for offset in sorted(candidates):
        if offset >= len(raw):
            continue
        try:
            # Reject false boundaries before allocating a complete payload.
            probe = zlib.decompressobj(-15)
            if probe.decompress(raw[offset:offset + 4096], 4) != b"\xfd\x77\xfd\xc9":
                continue
            decoder = zlib.decompressobj(-15)
            payload = decoder.decompress(raw[offset:]) + decoder.flush()
        except zlib.error:
            continue
        if decoder.eof and payload.startswith(b"\xfd\x77\xfd\xc9"):
            hits.append((offset, len(raw[offset:]) - len(decoder.unused_data), payload))
    if len(hits) != 1:
        raise ValueError(f"无法唯一定位存档 payload: 找到 {len(hits)} 个候选")
    offset, compressed_size, payload = hits[0]
    return PayloadLocation(offset, compressed_size, len(payload)), payload


def rebuild(path: Path, payload: bytes, output: Path, location: PayloadLocation) -> dict:
    """Rebuild a save while preserving its envelope.

    This function only accepts the currently observed single-stream layout;
    callers must still run a full deserialize/validation pass afterwards.
    """
    if not payload.startswith(b"\xfd\x77\xfd\xc9"):
        raise ValueError("新 payload 缺少 CIM2 magic")
    original = path.read_bytes()
    compressed = zlib.compress(payload, level=6, wbits=-15)
    prefix = original[:location.offset]
    suffix_start = location.offset + location.compressed_size
    suffix = original[suffix_start:]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(prefix + compressed + suffix)
    return {"sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "compressed_size": len(compressed), "payload_size": len(payload)}
