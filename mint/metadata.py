"""Decode the on-chain metadata returned by Windmill42.tokenURI()."""

import base64
import binascii
import json
from typing import Any

PREFIX = "data:application/json;base64,"


def decode_token_uri(uri: str) -> dict[str, Any]:
    """
    Turn "data:application/json;base64,<...>" into the metadata dict.

    Raises:
        ValueError: if the URI is not base64 JSON describing an object.
    """
    if not uri.startswith(PREFIX):
        raise ValueError("tokenURI is not an on-chain base64 JSON URI.")
    try:
        raw = base64.b64decode(uri[len(PREFIX) :], validate=True)
        metadata = json.loads(raw)
    except (binascii.Error, ValueError) as error:
        raise ValueError(f"tokenURI does not contain valid JSON: {error}")
    if not isinstance(metadata, dict):
        raise ValueError("tokenURI JSON is not an object.")
    return metadata
