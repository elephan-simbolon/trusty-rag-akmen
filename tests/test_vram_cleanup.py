import os
from unittest.mock import MagicMock, patch


def test_vram_cleanup_sequence():
    """INGEST-04: Full VRAM cleanup (gc.collect, torch.cuda.empty_cache, synchronize) runs in correct order."""
    import src.ingestion.parsing.gpu_utils as gpu_utils

    # Track call order across the three functions
    call_order = []

    def mock_gc_collect():
        call_order.append("gc.collect")

    mock_cuda = MagicMock()
    mock_cuda.is_available.return_value = True
    mock_cuda.empty_cache.side_effect = lambda: call_order.append("empty_cache")
    mock_cuda.synchronize.side_effect = lambda: call_order.append("synchronize")
    mock_cuda.memory_allocated.return_value = 0
    mock_cuda.memory_reserved.return_value = 0

    mock_torch = MagicMock()
    mock_torch.cuda = mock_cuda

    with (
        patch.dict("sys.modules", {"torch": mock_torch}),
        patch("gc.collect", side_effect=mock_gc_collect),
    ):
        gpu_utils.vram_cleanup()

    # Assert all three functions were called
    assert "gc.collect" in call_order, "gc.collect must be called"
    assert "empty_cache" in call_order, "torch.cuda.empty_cache must be called"
    assert "synchronize" in call_order, "torch.cuda.synchronize must be called"

    # Assert call order: gc.collect -> empty_cache -> synchronize
    gc_idx = call_order.index("gc.collect")
    empty_idx = call_order.index("empty_cache")
    sync_idx = call_order.index("synchronize")
    assert gc_idx < empty_idx, "gc.collect must be called before empty_cache"
    assert empty_idx < sync_idx, "empty_cache must be called before synchronize"


def test_vram_cleanup_between_parsers():
    """INGEST-04: VRAM cleanup env var PYTORCH_CUDA_ALLOC_CONF is set at module import time."""
    import importlib

    import src.ingestion.parsing.gpu_utils as gpu_utils

    # Reload the module to ensure the setdefault side effect is captured
    importlib.reload(gpu_utils)

    # The module sets PYTORCH_CUDA_ALLOC_CONF via os.environ.setdefault at import time
    assert "PYTORCH_CUDA_ALLOC_CONF" in os.environ, (
        "gpu_utils.py must set PYTORCH_CUDA_ALLOC_CONF in os.environ at module level"
    )
    assert "max_split_size_mb:512" in os.environ["PYTORCH_CUDA_ALLOC_CONF"], (
        "PYTORCH_CUDA_ALLOC_CONF must include max_split_size_mb:512"
    )
