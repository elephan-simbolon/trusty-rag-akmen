"""Backfill source_domain="accounting" on all existing Qdrant points lacking that field.

Safety order (REQUIRED per 07-RESEARCH.md):
  1. create_payload_index — enables fast filtering; idempotent if already exists
  2. set_payload with IsEmptyCondition filter — single server-side bulk update, no loops
  3. count verification — assert total == tagged before exit

This script must be run BEFORE any query code passes a non-None domain_filter.
Running it again after completion is safe (idempotent).

Usage:
    uv run python scripts/backfill_source_domain.py
    uv run python scripts/backfill_source_domain.py --collection my_collection
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level import required for test patchability (patch target: scripts.backfill_source_domain.get_qdrant_client)
from src.services.qdrant_service import get_qdrant_client  # noqa: E402


def backfill(collection_name: str | None = None) -> dict:
    """Tag all untagged Qdrant points with source_domain='accounting'.

    Returns:
        dict with keys 'total' and 'tagged' (both equal on success)
    Raises:
        AssertionError: if tagged count != total count after set_payload
    """
    from qdrant_client.models import (
        FieldCondition,
        Filter,
        IsEmptyCondition,
        MatchValue,
        PayloadField,
        PayloadSchemaType,
    )

    from config.settings import settings

    client = get_qdrant_client()
    name = collection_name or settings.qdrant_collection_name

    # Step 1: Create payload index on the live collection (idempotent)
    # NOTE: create_collection() skips this for existing collections — must do it here.
    client.create_payload_index(
        collection_name=name,
        field_name="source_domain",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    logger.info("Payload index on source_domain: created (or already existed — idempotent)")

    # Step 2: Bulk-update all points missing source_domain (single server-side API call)
    filter_no_domain = Filter(
        must=[IsEmptyCondition(is_empty=PayloadField(key="source_domain"))]
    )
    client.set_payload(
        collection_name=name,
        payload={"source_domain": "accounting"},
        points=filter_no_domain,
        wait=True,
    )
    logger.info("set_payload complete — all previously untagged points now carry source_domain='accounting'")

    # Step 3: Verify — tagged count must equal total count
    total = client.count(collection_name=name, exact=True).count
    tagged = client.count(
        collection_name=name,
        count_filter=Filter(
            must=[FieldCondition(key="source_domain", match=MatchValue(value="accounting"))]
        ),
        exact=True,
    ).count

    if total != tagged:
        raise AssertionError(
            f"Backfill incomplete: {tagged}/{total} points tagged with source_domain='accounting'. "
            "Do NOT enable domain_filter in hybrid_search until this is resolved."
        )

    logger.info(f"Backfill complete: {tagged}/{total} points tagged with source_domain='accounting'")
    return {"total": total, "tagged": tagged}


def main():
    parser = argparse.ArgumentParser(
        description="Backfill source_domain='accounting' on existing Qdrant points"
    )
    parser.add_argument("--collection", default=None, help="Override collection name")
    args = parser.parse_args()
    result = backfill(collection_name=args.collection)
    logger.info(f"Result: {result}")


if __name__ == "__main__":
    main()
