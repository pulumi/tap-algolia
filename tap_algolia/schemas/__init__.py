"""Algolia schemas module."""

from pathlib import Path
import json


def load_schema(stream_name: str) -> dict:
    """Load a schema file.

    Args:
        stream_name: The name of the stream/schema file.

    Returns:
        The schema dictionary.
    """
    schema_path = Path(__file__).parent / f"{stream_name}.json"
    with open(schema_path, "r") as f:
        return json.load(f)
