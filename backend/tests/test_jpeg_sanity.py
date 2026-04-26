import base64

from app.session.jpeg_sanity import is_plausible_jpeg


def test_stub_9j_is_not_plausible() -> None:
    data = base64.b64decode(b"/9j/")  # 3 bytes – unit-test stub, not a file
    assert not is_plausible_jpeg(data)
    assert not is_plausible_jpeg(b"\xff\xd8" + b"\x00" * 30)  # SOI, no EOI


def test_fixture_jpeg_is_plausible() -> None:
    from pathlib import Path

    raw = (Path(__file__).parent / "fixtures" / "one_pixel.jpg").read_bytes()
    assert is_plausible_jpeg(raw)
