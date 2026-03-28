import struct
import zlib
from pathlib import Path
from unittest.mock import patch

from config.settings import settings


def _make_minimal_png(path: Path) -> None:
    """Write a valid 1x1 pixel red PNG to path."""

    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return length + chunk_type + data + crc

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = make_chunk(b"IHDR", ihdr_data)
    raw_pixel = b"\x00\xff\x00\x00"  # filter byte + R, G, B
    compressed = zlib.compress(raw_pixel)
    idat = make_chunk(b"IDAT", compressed)
    iend = make_chunk(b"IEND", b"")
    path.write_bytes(signature + ihdr + idat + iend)


def test_vlm_captioner_returns_description(tmp_path, mock_siliconflow):
    """INGEST-05: VLM captioner (Qwen-VL via SiliconFlow) returns a text description for a diagram image."""
    from src.ingestion.parsing.vlm_captioner import caption_diagram

    # Create a minimal valid PNG file in tmp_path
    image_path = tmp_path / "diagram.png"
    _make_minimal_png(image_path)

    result = caption_diagram(image_path)

    # Assert return value is a non-empty string
    assert isinstance(result, str), "caption_diagram must return a string"
    assert len(result) > 0, "caption_diagram must return a non-empty string"

    # Assert the mock client's chat.completions.create was called with correct model
    mock_siliconflow.chat.completions.create.assert_called_once()
    call_kwargs = mock_siliconflow.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == settings.vlm_model, (
        f"Must use settings.vlm_model={settings.vlm_model}"
    )

    # Assert the message content contains an image_url type entry
    messages = call_kwargs.kwargs["messages"]
    assert len(messages) == 1
    content = messages[0]["content"]
    content_types = [item["type"] for item in content]
    assert "image_url" in content_types, "Message content must include an image_url entry"


def test_diagram_image_extraction(tmp_path):
    """INGEST-05: Diagram images are correctly extracted from parsed output and captioned."""
    from src.ingestion.parsing.vlm_captioner import extract_and_caption_diagrams

    # Create two PNG files in tmp_path
    img1 = tmp_path / "diagram1.png"
    img2 = tmp_path / "diagram2.png"
    _make_minimal_png(img1)
    _make_minimal_png(img2)

    # Mock caption_diagram to return a fixed caption
    with patch(
        "src.ingestion.parsing.vlm_captioner.caption_diagram", return_value="Test caption"
    ) as mock_caption:
        results = extract_and_caption_diagrams(tmp_path)

    # Assert result is a list of 2 dicts
    assert isinstance(results, list), "extract_and_caption_diagrams must return a list"
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"

    for item in results:
        assert "image_path" in item, "Each result must have 'image_path' key"
        assert "caption" in item, "Each result must have 'caption' key"
        assert item["caption"] == "Test caption"

    # Assert caption_diagram was called for each image
    assert mock_caption.call_count == 2
