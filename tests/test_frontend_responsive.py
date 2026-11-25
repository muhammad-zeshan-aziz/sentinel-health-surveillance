"""
Module 12: Production Frontend Build & Responsive Layout Verification Tests.
Verifies compiled production assets (dist/index.html), persistent filter contracts,
DEMO DATA banner labeling, and responsive CSS breakpoints across all 5 views.
"""

import os
from pathlib import Path

def test_frontend_dist_index_html(paths):
    dist_html = paths["dist"] / "index.html"
    assert dist_html.exists(), "frontend/dist/index.html is missing. Run 'npm run build'."
    content = dist_html.read_text(encoding="utf-8")
    assert '<div id="root"></div>' in content, "Root element missing in index.html"
    assert "Sentinel Health Surveillance" in content

def test_frontend_compiled_assets(paths):
    assets_dir = paths["dist"] / "assets"
    assert assets_dir.exists(), "frontend/dist/assets is missing"

    js_files = list(assets_dir.glob("*.js"))
    css_files = list(assets_dir.glob("*.css"))

    assert len(js_files) >= 1, "No compiled JS bundle found"
    assert len(css_files) >= 1, "No compiled CSS bundle found"
    assert js_files[0].stat().st_size > 50000, "JS bundle is suspiciously small"
    assert css_files[0].stat().st_size > 10000, "CSS bundle is suspiciously small"

def test_demo_data_badge_in_source(paths):
    top_header = paths["frontend"] / "src" / "components" / "layout" / "TopHeader.jsx"
    assert top_header.exists(), "TopHeader.jsx missing"
    code = top_header.read_text(encoding="utf-8")
    assert "DEMO DATA" in code, "TopHeader must display prominent 'DEMO DATA' badge"
    assert "isSyntheticActive" in code

def test_persistent_filters_source_contract(paths):
    filter_context = paths["frontend"] / "src" / "context" / "FilterContext.jsx"
    assert filter_context.exists(), "FilterContext.jsx missing"
    code = filter_context.read_text(encoding="utf-8")

    # All 5 mandatory filters must be present in FilterContext
    assert "disease" in code
    assert "districtPcode" in code
    assert "facilityId" in code
    assert "timeSpan" in code
    assert "caseStatus" in code
    assert "resetFilters" in code

def test_responsive_mobile_css_breakpoints(paths):
    views_dir = paths["frontend"] / "src" / "views"
    for view_file in views_dir.glob("*.jsx"):
        code = view_file.read_text(encoding="utf-8")
        # Views must include responsive classes (sm:, md:, lg:, or overflow-x-auto)
        has_responsive = "sm:" in code or "lg:" in code or "md:" in code or "overflow-x-auto" in code
        assert has_responsive, f"View {view_file.name} lacks responsive styling classes"

    sidebar = paths["frontend"] / "src" / "components" / "layout" / "Sidebar.jsx"
    sidebar_code = sidebar.read_text(encoding="utf-8")
    assert "lg:hidden" in sidebar_code or "translate-x" in sidebar_code, "Sidebar must support mobile collapsible drawer"
