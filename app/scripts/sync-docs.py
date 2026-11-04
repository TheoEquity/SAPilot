#!/usr/bin/env python3
"""
Documentation Sync Tool

Syncs documentation from ../docs/ to web/docs/, automatically handling image references.

Usage:
    make docs
    
    Or directly:
    python3 scripts/sync-docs.py

How It Works:
    1. Whitelist-based Sync: Only files listed in SYNC_WHITELIST are synced
    2. Automatic Image Detection: Scans markdown files for image references
    3. Smart Image Sync: Copies referenced images maintaining directory structure
    4. Timestamp Check: Only copies images if source is newer than destination

Features:
    - Markdown Sync: Copies markdown files from ../docs/ to web/docs/
    - Image Detection: Automatically finds images (![](path) and <img src="">)
    - Directory Structure: Preserves the website's locale/design layout
    - Smart Copy: Only copies when source is newer (timestamp check)
    - Safe: Never modifies source files in ../docs/
    - URL Aware: Skips external URLs (http://, https://)

Adding More Documents:
    Edit SYNC_WHITELIST below to add more documents:
    
    SYNC_WHITELIST = [
        "en-US/design/architecture.md",
        "en-US/design/document_upload_design.md",  # Uncomment to sync
        "zh-CN/design/architecture.md",
        "zh-CN/design/document_upload_design.md",  # Website paths stay stable
    ]

Important Notes:
    - ../docs/ is the source of truth - always edit files there
    - web/docs/ is generated - don't edit directly
    - Run 'make docs' to publish the documents selected below
    - Source paths and website paths are mapped separately

File Structure:
    ../docs/                       # Source of truth
    ├── design/
    │   ├── en-US/
    │   │   └── architecture.md    # Source file
    │   └── zh-CN/
    │       └── architecture.md
    └── en-US/
        └── images/                # Source images
            └── diagram.png

    web/docs/                      # Generated (don't edit directly)
    ├── en-US/
    │   ├── design/
    │   │   └── architecture.md    # Synced file
    │   └── images/                # Synced images
    │       └── diagram.png
    └── zh-CN/
        └── design/
            └── architecture.md
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Set
from urllib.parse import quote, unquote, urlsplit, urlunsplit

# Configuration
APP_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = APP_ROOT.parent / "docs"
WEB_DOCS_ROOT = APP_ROOT / "web/docs"
SOURCE_REF = subprocess.check_output(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=APP_ROOT.parent, text=True
).strip()
if SOURCE_REF == "HEAD":
    SOURCE_REF = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=APP_ROOT.parent, text=True
    ).strip()

# Whitelist: files to sync from ../docs/ to web/docs/
# Format: website-relative paths; source design docs live in design/<locale>/.
SYNC_WHITELIST = [
    # English docs - Design
    "en-US/design/architecture.md",
    "en-US/design/document_upload_design.md",
    "en-US/design/graph_index_creation.md",
    "en-US/design/chat_history_design.md",
    
    # English docs - Development
    "en-US/development/development-guide.md",
    
    # English docs - Deployment
    "en-US/deployment/build-docker-image.md",
    
    # English docs - Integration
    "en-US/integration/dify.md",
    "en-US/integration/mcp-api.md",
    
    # English docs - Reference
    # "en-US/reference/how-to-configure-ollama.md",
    # "en-US/reference/HOW-TO-DEBUG.md",
    
    # Chinese docs - Design
    "zh-CN/design/architecture.md",
    "zh-CN/design/document_upload_design.md",
    "zh-CN/design/graph_index_creation.md",
    "zh-CN/design/chat_history_design.md",
    
    # Publish the navigation page; development rules remain in docs/specs/.
    "zh-CN/development/development-guide.md",
    
    # Chinese docs - Deployment
    "zh-CN/deployment/build-docker-image.md",
    
    # Chinese docs - Integration
    "zh-CN/integration/dify.md",
    "zh-CN/integration/mcp-api.md",
    
    # Chinese docs - Reference
    # "zh-CN/reference/how-to-configure-ollama.md",
    # "zh-CN/reference/HOW-TO-DEBUG.md",
]

SOURCE_OVERRIDES = {
    "zh-CN/design/architecture.md": "design/zh-CN/pending-review/architecture.md",
    "zh-CN/design/document_upload_design.md": "design/zh-CN/pending-review/document_upload_design.md",
    "zh-CN/design/graph_index_creation.md": "design/zh-CN/pending-review/graph_index_creation.md",
    "zh-CN/design/chat_history_design.md": "design/zh-CN/pending-review/chat_history_design.md",
    "zh-CN/development/development-guide.md": "zh-CN/development/README.md",
}


def source_relative_path(web_path: Path) -> Path:
    override = SOURCE_OVERRIDES.get(web_path.as_posix())
    if override is not None:
        return Path(override)
    if len(web_path.parts) > 1 and web_path.parts[1] == "design":
        return Path("design", web_path.parts[0], *web_path.parts[2:])
    return web_path


def web_relative_path(source_path: Path) -> Path:
    for web_path in SYNC_WHITELIST:
        if source_relative_path(Path(web_path)) == source_path:
            return Path(web_path)
    if len(source_path.parts) > 1 and source_path.parts[0] == "design":
        return Path(source_path.parts[1], "design", *source_path.parts[2:])
    return source_path


def rewrite_document_links(content: str, src_path: Path, dest_path: Path) -> str:
    published = {
        (DOCS_ROOT / source_relative_path(Path(web_path))).resolve(): WEB_DOCS_ROOT / web_path
        for web_path in SYNC_WHITELIST
    }

    def replace(match):
        reference = urlsplit(match.group(2))
        if reference.scheme or reference.netloc:
            if reference.netloc == "github.com":
                # The website removes literal .md from document links. Keep GitHub source extensions.
                path = reference.path.replace(".md", "%2Emd")
                url = urlunsplit(reference._replace(path=path))
                return f"{match.group(1)}{url}{match.group(3)}"
            return match.group(0)
        if not reference.path or reference.path.startswith("/"):
            return match.group(0)
        target = (src_path.parent / unquote(reference.path)).resolve()
        if target in published:
            relative = os.path.relpath(published[target], dest_path.parent).replace(os.sep, "/")
            url = urlunsplit(("", "", quote(relative, safe="/"), reference.query, reference.fragment))
        else:
            try:
                relative = target.relative_to(APP_ROOT.parent).as_posix()
            except ValueError:
                return match.group(0)
            kind = "tree" if target.is_dir() else "blob"
            path = quote(relative, safe="/").replace(".md", "%2Emd")
            url = f"https://github.com/TheoEquity/SAPilot/{kind}/{SOURCE_REF}/{path}"
            url = urlunsplit((*urlsplit(url)[:3], reference.query, reference.fragment))
        return f"{match.group(1)}{url}{match.group(3)}"

    return re.sub(r"(?<!!)(\[[^\]\n]+\]\()([^\s)]+)(\))", replace, content)


def image_paths(doc_path: Path, image_ref: str):
    reference = urlsplit(image_ref)
    if reference.scheme or reference.netloc or not reference.path or reference.path.startswith("/"):
        return None
    source = (doc_path.parent / unquote(reference.path)).resolve()
    try:
        relative = source.relative_to(DOCS_ROOT)
    except ValueError:
        return None
    return source, WEB_DOCS_ROOT / web_relative_path(relative)


def find_image_references(content: str) -> Set[str]:
    """
    Find all image references in markdown content.
    Matches patterns like: ![alt](path), <img src="path">, etc.
    """
    image_refs = set()
    
    # Match markdown image syntax: ![alt](path)
    md_pattern = r'!\[.*?\]\((.*?)\)'
    for match in re.finditer(md_pattern, content):
        image_refs.add(match.group(1))
    
    # Match HTML img tags: <img src="path">
    html_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
    for match in re.finditer(html_pattern, content):
        image_refs.add(match.group(1))
    
    return image_refs


def sync_file(src_path: Path, dest_path: Path) -> List[str]:
    """
    Sync a single file from ../docs/ to web/docs/
    Returns list of image paths referenced in the document.
    """
    # Create destination directory if it doesn't exist
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read source file
    with open(src_path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    
    # Find image references
    image_refs = find_image_references(content)

    # Keep website image locations stable when source design folders move.
    for image_ref in image_refs:
        locations = image_paths(src_path, image_ref)
        if locations is None:
            continue
        _, image_dest = locations
        reference = urlsplit(image_ref)
        relative = os.path.relpath(image_dest, dest_path.parent).replace(os.sep, "/")
        web_ref = urlunsplit(("", "", quote(relative, safe="/"), reference.query, reference.fragment))
        content = content.replace(f"]({image_ref})", f"]({web_ref})")
        content = content.replace(f'src="{image_ref}"', f'src="{web_ref}"')
        content = content.replace(f"src='{image_ref}'", f"src='{web_ref}'")

    content = rewrite_document_links(content, src_path, dest_path)
    dest_path.write_text(content, encoding="utf-8", newline="")
    shutil.copystat(src_path, dest_path)
    print(f"✅ Synced: {src_path} -> {dest_path}")
    
    return list(image_refs)


def sync_images(doc_path: Path, image_refs: List[str]) -> None:
    """
    Sync images referenced in a document.
    """
    for img_ref in image_refs:
        locations = image_paths(doc_path, img_ref)
        if locations is None:
            continue
        img_src, img_dest = locations
        
        # Check if image exists
        if not img_src.exists():
            print(f"⚠️  Image not found: {img_src}")
            continue
        
        # Create destination directory
        img_dest.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy image
        if not img_dest.exists() or os.path.getmtime(img_src) > os.path.getmtime(img_dest):
            shutil.copy2(img_src, img_dest)
            print(f"   📷 Image: {img_ref}")


def main():
    """
    Main sync function.
    """
    print("🔄 Syncing documentation from ../docs/ to web/docs/\n")
    
    # Check if directories exist
    if not DOCS_ROOT.exists():
        print(f"❌ Error: {DOCS_ROOT} directory not found")
        return 1
    
    # Create web/docs if it doesn't exist
    WEB_DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    
    synced_count = 0
    error_count = 0
    
    # Sync each file in whitelist
    for doc_path in SYNC_WHITELIST:
        src = DOCS_ROOT / source_relative_path(Path(doc_path))
        dest = WEB_DOCS_ROOT / doc_path
        
        if not src.exists():
            print(f"⚠️  File not found in whitelist: {src}")
            error_count += 1
            continue
        
        try:
            # Sync document
            image_refs = sync_file(src, dest)
            synced_count += 1
            
            # Sync images
            if image_refs:
                sync_images(src, image_refs)
        
        except Exception as e:
            print(f"❌ Error syncing {doc_path}: {e}")
            error_count += 1
    
    # Sync _category.yaml files
    print("\n🔄 Syncing _category.yaml files...\n")
    category_count = 0
    for locale in ["en-US", "zh-CN"]:
        locale_dir = DOCS_ROOT / locale
        category_dirs = list(locale_dir.iterdir()) if locale_dir.exists() else []
        category_dirs.append(DOCS_ROOT / "design" / locale)
        for category_dir in category_dirs:
            if category_dir.is_dir():
                category_file = category_dir / "_category.yaml"
                if category_file.exists():
                    dest_file = WEB_DOCS_ROOT / web_relative_path(category_file.relative_to(DOCS_ROOT))
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(category_file, dest_file)
                    print(f"✅ Synced: {category_file} -> {dest_file}")
                    category_count += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Summary:")
    print(f"   ✅ Synced: {synced_count} documents")
    print(f"   ✅ Synced: {category_count} category files")
    if error_count > 0:
        print(f"   ❌ Errors: {error_count}")
    print(f"{'='*60}\n")
    
    print("💡 To sync more documents, edit SYNC_WHITELIST in scripts/sync-docs.py")
    
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    exit(main())
