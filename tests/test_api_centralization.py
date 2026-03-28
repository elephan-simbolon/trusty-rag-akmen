"""
FLAG-3 API centralization validation tests.

All tests are static file-analysis (no live services, no integration marker).
They verify the structural correctness of the FLAG-3 refactor:
  - frontend/src/lib/api.ts exports API_BASE_URL with correct fallback
  - 5 consumer files import from @/lib/api, not raw import.meta.env
  - main.tsx DEV guard is gated
  - SC-4 (Streamlit removal) is pre-satisfied
  - Vite production build artifact exists
"""

import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_SRC = PROJECT_ROOT / "frontend" / "src"


# ---------------------------------------------------------------------------
# FLAG-3/T1 — api.ts exists and exports API_BASE_URL with correct signature
# ---------------------------------------------------------------------------

def test_api_ts_file_exists():
    """api.ts must exist at frontend/src/lib/api.ts."""
    api_file = FRONTEND_SRC / "lib" / "api.ts"
    assert api_file.exists(), (
        f"frontend/src/lib/api.ts not found at {api_file}. "
        "FLAG-3 requires this file to centralize VITE_API_BASE_URL."
    )


def test_api_ts_exports_typed_string_constant():
    """api.ts must export API_BASE_URL as an explicit string type."""
    api_file = FRONTEND_SRC / "lib" / "api.ts"
    content = api_file.read_text(encoding="utf-8")

    # Must have: export const API_BASE_URL: string = ...
    assert "export const API_BASE_URL: string" in content, (
        "api.ts does not export 'API_BASE_URL' with explicit ': string' type annotation. "
        f"Current content:\n{content}"
    )


def test_api_ts_uses_logical_or_empty_string_fallback():
    """api.ts must use || '' fallback so production relative URLs work."""
    api_file = FRONTEND_SRC / "lib" / "api.ts"
    content = api_file.read_text(encoding="utf-8")

    # Pattern: import.meta.env.VITE_API_BASE_URL || ""  (or single-quoted)
    pattern = r'import\.meta\.env\.VITE_API_BASE_URL\s*\|\|'
    assert re.search(pattern, content), (
        "api.ts must use 'import.meta.env.VITE_API_BASE_URL || \"\"' (logical OR fallback). "
        f"Current content:\n{content}"
    )


# ---------------------------------------------------------------------------
# FLAG-3/T2 — Zero raw VITE_API_BASE_URL in 5 consumer files
# ---------------------------------------------------------------------------

CONSUMER_FILES = [
    FRONTEND_SRC / "hooks" / "useStreamingQuery.ts",
    FRONTEND_SRC / "hooks" / "useHistory.ts",
    FRONTEND_SRC / "hooks" / "useHistoryActions.ts",
    FRONTEND_SRC / "components" / "FeedbackButtons.tsx",
    FRONTEND_SRC / "components" / "HistorySidebar.tsx",
]

RAW_ENV_PATTERN = re.compile(r"import\.meta\.env\.VITE_API_BASE_URL")
IMPORT_API_PATTERN = re.compile(r'from\s+["\']@/lib/api["\']')


def test_consumer_files_have_no_raw_vite_api_base_url():
    """None of the 5 consumer files may contain raw import.meta.env.VITE_API_BASE_URL."""
    violations = []
    for filepath in CONSUMER_FILES:
        assert filepath.exists(), f"Consumer file not found: {filepath}"
        content = filepath.read_text(encoding="utf-8")
        if RAW_ENV_PATTERN.search(content):
            violations.append(str(filepath.relative_to(PROJECT_ROOT)))

    assert not violations, (
        "The following consumer files still contain raw 'import.meta.env.VITE_API_BASE_URL' "
        f"and must import API_BASE_URL from @/lib/api instead:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_consumer_files_import_api_base_url_from_lib_api():
    """All 5 consumer files must import API_BASE_URL from @/lib/api."""
    missing_import = []
    for filepath in CONSUMER_FILES:
        assert filepath.exists(), f"Consumer file not found: {filepath}"
        content = filepath.read_text(encoding="utf-8")
        if "API_BASE_URL" in content and not IMPORT_API_PATTERN.search(content):
            missing_import.append(str(filepath.relative_to(PROJECT_ROOT)))

    assert not missing_import, (
        "The following files use API_BASE_URL but do not import it from '@/lib/api':\n"
        + "\n".join(f"  - {v}" for v in missing_import)
    )


# ---------------------------------------------------------------------------
# FLAG-3/T3 — main.tsx console.error is DEV-gated
# ---------------------------------------------------------------------------

def test_main_tsx_console_error_gated_with_dev_flag():
    """main.tsx warning must only fire in DEV mode — production builds stay silent."""
    main_tsx = FRONTEND_SRC / "main.tsx"
    assert main_tsx.exists(), f"main.tsx not found at {main_tsx}"

    content = main_tsx.read_text(encoding="utf-8")

    # Check that DEV guard appears before the console.error
    dev_guard_pattern = re.compile(
        r"import\.meta\.env\.DEV\s*&&\s*!import\.meta\.env\.VITE_API_BASE_URL"
    )
    assert dev_guard_pattern.search(content), (
        "main.tsx console.error is not gated with 'import.meta.env.DEV'. "
        "The guard must read: if (import.meta.env.DEV && !import.meta.env.VITE_API_BASE_URL). "
        f"Current main.tsx content:\n{content}"
    )


def test_main_tsx_does_not_have_ungated_vite_api_base_url_warning():
    """main.tsx must not have an ungated (!import.meta.env.VITE_API_BASE_URL) check."""
    main_tsx = FRONTEND_SRC / "main.tsx"
    content = main_tsx.read_text(encoding="utf-8")

    # An ungated pattern would be: if (!import.meta.env.VITE_API_BASE_URL) {
    # without the DEV guard preceding it on the same condition line.
    # We look for lines that have the negated check but NOT the DEV guard.
    ungated_pattern = re.compile(
        r"if\s*\(\s*!import\.meta\.env\.VITE_API_BASE_URL\s*\)"
    )
    assert not ungated_pattern.search(content), (
        "main.tsx has an ungated 'if (!import.meta.env.VITE_API_BASE_URL)' check. "
        "This will fire console.error in production. Gate it with import.meta.env.DEV."
    )


# ---------------------------------------------------------------------------
# FLAG-3/T4 — SC-4 pre-satisfied: app/ absent, streamlit absent from pyproject
# ---------------------------------------------------------------------------

def test_app_directory_does_not_exist():
    """SC-4: the app/ directory (Streamlit app) must not exist."""
    app_dir = PROJECT_ROOT / "app"
    assert not app_dir.exists(), (
        f"app/ directory exists at {app_dir}. "
        "SC-4 requires Streamlit app directory to be absent."
    )


def test_streamlit_absent_from_pyproject_toml():
    """SC-4: 'streamlit' must not appear as a dependency in pyproject.toml."""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    assert pyproject.exists(), f"pyproject.toml not found at {pyproject}"

    content = pyproject.read_text(encoding="utf-8")
    # Match streamlit as a package name (not in comments or strings describing removal)
    # Look for streamlit in dependency lines: "streamlit", streamlit>=, streamlit~=, etc.
    dep_pattern = re.compile(r'^\s*"?streamlit', re.MULTILINE)
    matches = dep_pattern.findall(content)

    assert not matches, (
        "pyproject.toml still contains 'streamlit' as a dependency. "
        "SC-4 requires Streamlit to be fully removed from the project."
    )


# ---------------------------------------------------------------------------
# FLAG-3/T5 — Vite production build artifact exists
# ---------------------------------------------------------------------------

def test_frontend_dist_directory_exists():
    """A prior successful Vite production build must have produced frontend/dist/."""
    dist_dir = PROJECT_ROOT / "frontend" / "dist"
    assert dist_dir.exists() and dist_dir.is_dir(), (
        f"frontend/dist/ not found at {dist_dir}. "
        "Run 'cd frontend && npm run build' to produce the production artifact."
    )


def test_frontend_dist_contains_index_html():
    """frontend/dist/ must contain index.html — the SPA entry point."""
    index_html = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    assert index_html.exists(), (
        f"frontend/dist/index.html not found. "
        "The Vite build output is incomplete or missing."
    )


def test_frontend_dist_contains_assets():
    """frontend/dist/ must contain an assets/ subdirectory with bundled JS/CSS."""
    assets_dir = PROJECT_ROOT / "frontend" / "dist" / "assets"
    assert assets_dir.exists() and assets_dir.is_dir(), (
        f"frontend/dist/assets/ not found. "
        "Vite build output is missing the assets directory."
    )

    js_files = list(assets_dir.glob("*.js"))
    assert js_files, (
        "frontend/dist/assets/ contains no .js files. "
        "Vite build output appears incomplete."
    )


def test_vite_build_exits_zero():
    """Vite production build must complete successfully (exit code 0)."""
    frontend_dir = PROJECT_ROOT / "frontend"
    # shell=True required on Windows: npm is a .cmd script and not directly executable
    result = subprocess.run(
        "npm run build",
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
        timeout=120,
        shell=True,
    )
    assert result.returncode == 0, (
        f"Vite build failed with exit code {result.returncode}.\n"
        f"stdout:\n{result.stdout[-2000:]}\n"
        f"stderr:\n{result.stderr[-2000:]}"
    )
    # Confirm dist/ was produced
    dist_dir = frontend_dir / "dist"
    assert dist_dir.exists(), "Vite build exited 0 but frontend/dist/ was not created."
