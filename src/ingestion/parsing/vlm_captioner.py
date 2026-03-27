import base64
from pathlib import Path
import logging
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
from config.settings import settings
from src.llm.client import get_openai_client

logger = logging.getLogger(__name__)

VLM_CAPTION_PROMPT = (
    "Describe this diagram or flowchart from an accounting textbook in detail. "
    "Include all labels, arrows, relationships, and numerical values visible. "
    "The description will be used for text-based retrieval, so be thorough and precise. "
    "Output in English."
)


@retry(
    retry=retry_if_exception_type((Exception,)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=30, max=120),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def caption_diagram(image_path: str | Path) -> str:
    """
    Send a diagram/flowchart image to Qwen-VL via SiliconFlow and return text description.
    Uses base64 encoding for the image payload.
    Returns: str — text description of the diagram.
    """
    image_bytes = Path(image_path).read_bytes()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    # Detect MIME type from extension
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "image/png")

    client = get_openai_client()
    response = client.chat.completions.create(
        model=settings.vlm_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VLM_CAPTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_image}"
                        }
                    }
                ]
            }
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    caption = response.choices[0].message.content
    logger.info(f"VLM caption for {image_path}: {len(caption)} chars")
    return caption


def extract_and_caption_diagrams(parsed_output_dir: str | Path) -> list[dict]:
    """
    Find all diagram images in a parsed output directory and caption each.
    Returns: list of dicts with 'image_path' and 'caption' keys.
    """
    output_dir = Path(parsed_output_dir)
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    images = [
        f for f in output_dir.rglob("*")
        if f.suffix.lower() in image_extensions
    ]

    results = []
    for img_path in images:
        try:
            caption = caption_diagram(img_path)
            results.append({
                "image_path": str(img_path),
                "caption": caption,
            })
        except Exception as e:
            logger.error(f"Failed to caption {img_path}: {e}")
            results.append({
                "image_path": str(img_path),
                "caption": f"[Captioning failed: {e}]",
            })
    return results
