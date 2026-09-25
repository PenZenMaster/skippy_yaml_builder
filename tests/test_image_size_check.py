import requests

import image_size_check
from image_size_check import MAX_UPLOAD_IMAGE_BYTES, check_image_sizes


class _Resp:
    def __init__(self, status=200, headers=None, body=b""):
        self.status_code = status
        self.headers = headers or {}
        self._body = body

    def iter_content(self, chunk):
        for i in range(0, len(self._body), chunk):
            yield self._body[i : i + chunk]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch(monkeypatch, head=None, get=None):
    monkeypatch.setattr(
        image_size_check.requests, "head", head or (lambda *a, **k: _Resp(405))
    )
    monkeypatch.setattr(
        image_size_check.requests, "get", get or (lambda *a, **k: _Resp(404))
    )


def test_no_items_returns_no_warnings():
    assert check_image_sizes([]) == []


def test_small_image_via_head_content_length_is_fine(monkeypatch):
    _patch(monkeypatch, head=lambda *a, **k: _Resp(200, {"Content-Length": "120000"}))

    assert check_image_sizes([("Hero Image URL", "https://x.example/a.jpg")]) == []


def test_oversized_image_warns_with_size_and_413_hint(monkeypatch):
    _patch(monkeypatch, head=lambda *a, **k: _Resp(200, {"Content-Length": "1350000"}))

    warnings = check_image_sizes([("Logo URL", "https://x.example/logo.png")])

    assert len(warnings) == 1
    assert "Logo URL" in warnings[0]
    assert "1318KB" in warnings[0]
    assert "413" in warnings[0]


def test_exactly_at_cap_is_fine_and_one_byte_over_warns(monkeypatch):
    _patch(
        monkeypatch,
        head=lambda url, **k: _Resp(
            200,
            {
                "Content-Length": str(
                    MAX_UPLOAD_IMAGE_BYTES + (1 if "over" in url else 0)
                )
            },
        ),
    )

    warnings = check_image_sizes(
        [("A", "https://x.example/at.jpg"), ("B", "https://x.example/over.jpg")]
    )

    assert len(warnings) == 1
    assert warnings[0].startswith("B ")


def test_head_rejected_falls_back_to_streamed_get_content_length(monkeypatch):
    _patch(
        monkeypatch,
        head=lambda *a, **k: _Resp(405),
        get=lambda *a, **k: _Resp(200, {"Content-Length": "999999"}),
    )

    warnings = check_image_sizes([("Hero Image URL", "https://x.example/a.jpg")])

    assert len(warnings) == 1 and "over YACSS's 400KB" in warnings[0]


def test_no_content_length_reads_body_far_enough_to_flag_oversize(monkeypatch):
    big = b"x" * (MAX_UPLOAD_IMAGE_BYTES + 50_000)
    _patch(
        monkeypatch,
        head=lambda *a, **k: _Resp(200, {}),
        get=lambda *a, **k: _Resp(200, {}, big),
    )

    warnings = check_image_sizes([("Hero Image URL", "https://x.example/a.jpg")])

    assert len(warnings) == 1 and "400KB" in warnings[0]


def test_no_content_length_small_body_is_fine(monkeypatch):
    _patch(
        monkeypatch,
        head=lambda *a, **k: _Resp(200, {}),
        get=lambda *a, **k: _Resp(200, {}, b"x" * 1000),
    )

    assert check_image_sizes([("Hero Image URL", "https://x.example/a.jpg")]) == []


def test_http_error_status_warns(monkeypatch):
    _patch(monkeypatch, head=lambda *a, **k: _Resp(404), get=lambda *a, **k: _Resp(404))

    warnings = check_image_sizes([("Hero Image URL", "https://x.example/gone.jpg")])

    assert warnings == ["Hero Image URL returned HTTP 404: https://x.example/gone.jpg"]


def test_network_error_becomes_warning_not_exception(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("no route")

    _patch(monkeypatch, head=boom, get=boom)

    warnings = check_image_sizes([("Logo URL", "https://x.example/logo.png")])

    assert len(warnings) == 1
    assert "could not be checked" in warnings[0] and "ConnectionError" in warnings[0]


def test_warnings_keep_input_order(monkeypatch):
    _patch(monkeypatch, head=lambda *a, **k: _Resp(200, {"Content-Length": "999999"}))

    warnings = check_image_sizes(
        [("First", "https://x.example/1.jpg"), ("Second", "https://x.example/2.jpg")]
    )

    assert [w.split(" ")[0] for w in warnings] == ["First", "Second"]
