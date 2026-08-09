"""Module for extracting media download links from video pages."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any

import httpx
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

from src.config import (
    AES_HEADER,
    AES_KEY,
    AUTH_API_URL,
    DENO_PREAMBLE,
    HANIME_NAME_PATTERN,
    HOST_URL,
    JS_VENDOR_PATTERN,
    RESOLUTION_MAP,
    USER_AGENT,
    VIDEO_TITLE_PATTERN,
    VIDEO_URL,
)


def _b64url_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str | bytes) -> bytes:
    if isinstance(data, str):
        data = data.encode("ascii", errors="ignore")

    return urlsafe_b64decode(data.ljust((len(data) // 4 + 1) * 4, b"="))


def encrypt_token(payload: dict[str, Any]) -> str:
    """Encrypt a payload dict using AES-256-GCM (mirrors hanime.tv handshake)."""
    plaintext = json.dumps(payload, separators=(",", ":")).encode()
    nonce = get_random_bytes(12)
    cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=nonce)
    cipher.update(AES_HEADER)
    cipher_text, tag = cipher.encrypt_and_digest(plaintext)

    result = {
        "v": 1,
        "alg": "AES-256-GCM",
        "iv": _b64url_encode(nonce),
        "tag": _b64url_encode(tag),
        "data": _b64url_encode(cipher_text),
    }
    encoded_result = json.dumps(result, separators=(",", ":")).encode()
    return _b64url_encode(encoded_result)


def decrypt_token(token: str) -> dict[str, Any]:
    """Decrypt an AES-256-GCM-encrypted handshake token."""
    decoded = json.loads(_b64url_decode(token))
    nonce = _b64url_decode(decoded["iv"])
    tag = _b64url_decode(decoded["tag"])
    data = _b64url_decode(decoded["data"])
    cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=nonce)
    cipher.update(AES_HEADER)
    plaintext = cipher.decrypt_and_verify(data, tag)
    return json.loads(plaintext.decode())


def get_episode_id(url: str) -> str | None:
    """Validate the provided URL against a predefined pattern."""
    if not re.compile(HANIME_NAME_PATTERN, re.IGNORECASE).match(url):
        logging.warning("Invalid URL.")
        sys.exit(0)

    return url.rstrip("/").split("/")[-1]


def _find_vendor_js_url(page_html: str) -> str:
    """Extract the vendor JS URL (containing embedded WASM) from the page HTML."""
    match = re.search(JS_VENDOR_PATTERN, page_html)

    if not match:
        msg = "Could not find vendor JS URL on page"
        raise ValueError(msg)

    return match.group(1)


def _generate_credentials(vendor_js: str) -> tuple[str, int]:
    """Run vendor JS (with embedded WASM) in Deno to extract ssignature and stime."""
    script = DENO_PREAMBLE + vendor_js
    try:
        result = subprocess.run(  # noqa: S603
            ["deno", "run", "-"],  # noqa: S607
            input=script,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

    except FileNotFoundError:
        msg = "Deno is required but not found. Install it from https://deno.land"
        raise RuntimeError(msg) from None

    except subprocess.TimeoutExpired:
        msg = "Deno WASM auth script timed out"
        raise RuntimeError(msg) from None

    if result.returncode != 0:
        msg = f"Deno WASM auth failed: {result.stderr.strip()}"
        raise RuntimeError(msg)

    lines = result.stdout.strip().split("\n", 1)
    creds: dict[str, str] = {}

    for line in lines:
        if " " in line:
            key, val = line.split(" ", 1)
            creds[key] = val

    ssignature = creds.get("ssignature", "")
    stime_str = creds.get("stime", "0")
    return ssignature, int(stime_str)


def fetch_video_page(video_id: str) -> str:
    """Fetch the video page to get vendor JS URL and page content."""
    page_url = f"{VIDEO_URL}/{video_id}"
    response = httpx.get(
        page_url,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def extract_video_title(page_html: str, video_id: str) -> str:
    """Extract video title from page."""
    title_match = re.search(VIDEO_TITLE_PATTERN, page_html)
    return title_match.group(1).strip() if title_match else video_id


def extract_vendor_js(page_html: str) -> str:
    """Fetch the vendor JavaScript from the video page."""
    vendor_js_url = _find_vendor_js_url(page_html)
    vendor_response = httpx.get(
        vendor_js_url,
        headers={
            "Referer": HOST_URL,
            "User-Agent": USER_AGENT,
        },
        timeout=30,
    )
    vendor_response.raise_for_status()
    return vendor_response.text


def perform_handshake(video_id: str, signature: str, timestamp: int) -> str:
    """Perform the video handshake and return the encrypted X-Token."""
    # Build and encrypt handshake payload
    payload = encrypt_token({
        "timestamp_unix": int(time.time()),
        "directive": "htv_player_handshake",
        "slug": video_id,
    })

    handshake_response = httpx.post(
        f"{AUTH_API_URL}/api/v11/handshake",
        json={"token": payload},
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": HOST_URL,
            "Referer": HOST_URL,
            "X-Csrf-Token": "null",
            "X-Signature": signature,
            "X-Time": str(timestamp),
            "X-Signature-Version": "web2",
            "User-Agent": USER_AGENT,
        },
        timeout=30,
    )
    handshake_response.raise_for_status()

    # Extract the encrypted X-Token from the response
    x_token = handshake_response.headers.get("X-Token")
    if not x_token:
        msg = "Handshake response missing X-Token header"
        raise ValueError(msg)

    return x_token


def get_hanime_info(video_id: str) -> dict[str, Any]:
    """Retrieve video stream information via the new handshake API."""
    page_html = fetch_video_page(video_id)
    title = extract_video_title(page_html, video_id)

    # Generate handshake credentials via Deno + WASM
    vendor_js = extract_vendor_js(page_html)
    signature, timestamp = _generate_credentials(vendor_js)

    # Extract and decrypt the X-Token from the response
    x_token = perform_handshake(video_id, signature, timestamp)
    manifest = decrypt_token(x_token)

    return {
        "title": title,
        "slug": video_id,
        "sources": manifest.get("sources", []),
    }


def get_all_episodes_ids(info: dict[str, Any]) -> list[str]:
    """Extract the episode IDs (slugs) for a hanime series.

    NOTE: The new hanime.tv API no longer returns franchise episode data in the
    handshake response. This function returns an empty list as a placeholder.
    """
    logging.warning(
        "All-episodes mode is not supported with the current hanime.tv API. "
        "Only the current episode will be downloaded.",
    )
    return [info.get("slug", "")] if info.get("slug") else []


def generate_all_episode_urls(episode_ids: str) -> str:
    """Generate a list of URLs for the given episode IDs."""
    return [f"{VIDEO_URL}/{episode_id}" for episode_id in episode_ids]


def get_hanime_title(info: dict[str, Any]) -> str:
    """Extract the title of the hanime video from the provided information."""
    return info["title"]


def fetch_streams(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch the list of available video streams from the provided information."""
    return info["sources"]


def select_and_validate_stream(
    resolution_choice: str,
    streams: list[dict[str, Any]],
) -> dict[str, Any]:
    """Select and validate the video stream based on the user's resolution choice.

    Attempts to select the stream at the index corresponding to the given resolution.
    If it's invalid, not guest-accessible, or doesn't match the intended height,
    falls back to the first guest-accessible stream with matching height.
    If none is found, falls back to any guest-accessible stream.
    """
    resolution_indx = RESOLUTION_MAP.get(resolution_choice, 0)
    target_height = resolution_choice.lower().replace("p", "")

    def is_valid_stream(stream: dict[str, Any]) -> bool:
        return stream.get("kind") in ("normal", None)

    def match_target_height(stream: dict[str, Any]) -> bool:
        label = stream.get("label", "")
        return target_height in label

    if 0 <= resolution_indx < len(streams):
        stream = streams[resolution_indx]
        if is_valid_stream(stream) and match_target_height(stream):
            return stream

    for stream in streams:
        if is_valid_stream(stream) and match_target_height(stream):
            return stream

    for stream in streams:
        if is_valid_stream(stream):
            return stream

    message = "No guest-accessible stream available."
    raise ValueError(message)


def format_filename(
    streams: list[dict[str, Any]],
    video_id: str,
    resolution_choice: str,
) -> str:
    """Format the file name for the video based on the chosen stream resolution."""
    stream = select_and_validate_stream(resolution_choice, streams)
    resolution = stream.get("label", resolution_choice).lower()
    return f"{video_id}-{resolution}.mp4"
