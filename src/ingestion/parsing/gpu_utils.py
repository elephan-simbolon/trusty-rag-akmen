import gc
import logging
import os

logger = logging.getLogger(__name__)

# Must be set BEFORE importing torch — set at module level
os.environ.setdefault(
    "PYTORCH_CUDA_ALLOC_CONF",
    "max_split_size_mb:512,expandable_segments:True"
)


def vram_cleanup():
    """Full VRAM cleanup: gc.collect → empty_cache → synchronize."""
    try:
        import torch
        if torch.cuda.is_available():
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            allocated = torch.cuda.memory_allocated() / 1024**2
            reserved = torch.cuda.memory_reserved() / 1024**2
            logger.info(f"VRAM cleanup: allocated={allocated:.1f}MB, reserved={reserved:.1f}MB")
        else:
            gc.collect()
            logger.info("VRAM cleanup: CUDA not available, gc.collect() only")
    except ImportError:
        gc.collect()
        logger.warning("VRAM cleanup: torch not installed, gc.collect() only")
