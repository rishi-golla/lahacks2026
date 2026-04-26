"""Heuristic checks for JPEG byte payloads (e.g. before writing debug dumps)."""

from __future__ import annotations


def is_plausible_jpeg(data: bytes) -> bool:
    """True if bytes look like a complete JPEG, not a truncated header or test stub.

    The backend protocol uses base64; the unit test stub ``/9j/`` decodes to three
    bytes (``FF D8`` only) which is *not* a decodable file.
    """

    if len(data) < 32:
        return False
    if not data.startswith(b"\xff\xd8"):
        return False
    # SOI and EOI markers; scan end of file (large JFIFs may put EOI last).
    if data.rfind(b"\xff\xd9", max(0, len(data) - 256 * 1024)) < 0:
        return False
    return True
