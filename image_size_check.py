"""
Module/Script Name: image_size_check.py
Path: E:\\projects\\skippy_yaml_builder\\image_size_check.py

Description:
Advisory pre-export check that image URLs headed for rr_yacss_factory's
POST /uploads/image path are reachable and no larger than YACSS's 400KB
upload cap. rr_yacss_factory rejects an oversized image (HTTP 413) only
when the job is actually run, after other work may already be under way;
this surfaces the same problem while the job file is still being
authored. It never raises: any network trouble becomes a warning string,
because the real, authoritative check stays in rr_yacss_factory itself.
The 400KB figure is checked as 400,000 bytes (the stricter reading), so a
file just over the line warns rather than slipping through to a 413.

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-09-23

Last Modified Date:
2026-09-23

Comments:
- v1.00 Initial implementation.
"""

from concurrent.futures import ThreadPoolExecutor

import requests

# YACSS's POST /uploads/image cap (confirmed live, rr_yacss_factory ticket
# #2668-era 413: 1320KB against 400KB). Stricter 400,000-byte reading.
MAX_UPLOAD_IMAGE_BYTES = 400_000
DEFAULT_TIMEOUT_SECONDS = 5.0
_MAX_WORKERS = 8
_CHUNK_BYTES = 16 * 1024
# Some hosts (Wikimedia, several CDNs) 403 the default python-requests agent.
_HEADERS = {"User-Agent": "skippy-yaml-builder/0.10 (image size check)"}


def _measure(url: str, timeout: float) -> tuple[int, int | None]:
    """Returns (http_status, size_in_bytes_or_None). Tries HEAD first and
    trusts Content-Length; falls back to a streamed GET (read only far
    enough to know whether the body exceeds the cap) when HEAD is
    rejected or reports no length."""
    head = requests.head(url, headers=_HEADERS, allow_redirects=True, timeout=timeout)
    if head.status_code < 400:
        length = head.headers.get("Content-Length")
        if length is not None and length.isdigit():
            return head.status_code, int(length)

    with requests.get(
        url, headers=_HEADERS, stream=True, allow_redirects=True, timeout=timeout
    ) as resp:
        if resp.status_code >= 400:
            return resp.status_code, None
        length = resp.headers.get("Content-Length")
        if length is not None and length.isdigit():
            return resp.status_code, int(length)
        read = 0
        for chunk in resp.iter_content(_CHUNK_BYTES):
            read += len(chunk)
            if read > MAX_UPLOAD_IMAGE_BYTES:
                break
        return resp.status_code, read


def _check_one(label: str, url: str, timeout: float) -> str | None:
    try:
        status, size = _measure(url, timeout)
    except requests.RequestException as exc:
        return f"{label} could not be checked ({type(exc).__name__}): {url}"
    if status >= 400:
        return f"{label} returned HTTP {status}: {url}"
    if size is not None and size > MAX_UPLOAD_IMAGE_BYTES:
        return (
            f"{label} is {size / 1024:.0f}KB, over YACSS's 400KB upload cap "
            f"(rr_yacss_factory will fail with a 413): {url}"
        )
    return None


def check_image_sizes(
    items: list[tuple[str, str]], timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> list[str]:
    """items is a list of (label, url). Returns human-readable warnings in
    input order; an empty list means every image looked fine (or there was
    nothing to check)."""
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(items))) as pool:
        results = list(pool.map(lambda item: _check_one(item[0], item[1], timeout), items))
    return [r for r in results if r]
