#!/usr/bin/env python3
"""
Validate that file paths referenced in markdown docs actually exist.
Scans all .md files and checks backticked paths and table references.
"""

import os
import re
import sys
from pathlib import Path


def find_markdown_files(root_dir: str) -> list[Path]:
    """Find all markdown files, excluding hidden dirs and node_modules."""
    md_files = []
    for path in Path(root_dir).rglob("*.md"):
        if any(part.startswith('.') for part in path.parts[len(Path(root_dir).parts):]):
            continue
        if 'node_modules' in path.parts:
            continue
        md_files.append(path)
    return md_files


def extract_paths(content: str) -> list[str]:
    """Extract potential file paths from markdown content."""
    paths = []

    # Backticked paths (e.g., `path/to/file.md`)
    backtick_pattern = r'`([^`]+\.[a-zA-Z]+)`'
    paths.extend(re.findall(backtick_pattern, content))

    # Paths in table cells (e.g., | `file.py` | or | path/file.md |)
    table_pattern = r'\|\s*`?([^|`\n]+\.[a-zA-Z]+)`?\s*\|'
    paths.extend(re.findall(table_pattern, content))

    # Filter to likely file paths
    filtered = []
    for p in paths:
        p = p.strip()
        # Skip URLs
        if p.startswith('http://') or p.startswith('https://'):
            continue
        # Skip obvious non-paths
        if ' ' in p and not '/' in p:
            continue
        # Must have a file extension
        if '.' in p:
            filtered.append(p)

    return list(set(filtered))


def resolve_path(ref_path: str, doc_path: Path, root_dir: Path) -> Path | None:
    """Try to resolve a referenced path relative to doc or root."""
    # Try relative to document
    relative_to_doc = doc_path.parent / ref_path
    if relative_to_doc.exists():
        return relative_to_doc

    # Try relative to root
    relative_to_root = root_dir / ref_path
    if relative_to_root.exists():
        return relative_to_root

    # Try without leading ./
    if ref_path.startswith('./'):
        return resolve_path(ref_path[2:], doc_path, root_dir)

    # Try without leading ../
    if ref_path.startswith('../'):
        parent_path = doc_path.parent.parent / ref_path[3:]
        if parent_path.exists():
            return parent_path

    return None


def validate_paths(root_dir: str) -> dict:
    """Validate all path references in markdown files."""
    root = Path(root_dir).resolve()
    md_files = find_markdown_files(root_dir)

    results = {
        'valid': [],
        'invalid': [],
        'skipped': []
    }

    for md_file in md_files:
        content = md_file.read_text()
        paths = extract_paths(content)

        for ref_path in paths:
            # Skip patterns that aren't real paths
            if ref_path.startswith('[') or ref_path.startswith('$'):
                results['skipped'].append((md_file, ref_path))
                continue

            resolved = resolve_path(ref_path, md_file, root)

            if resolved:
                results['valid'].append((md_file, ref_path, resolved))
            else:
                results['invalid'].append((md_file, ref_path))

    return results


def main():
    root_dir = sys.argv[1] if len(sys.argv) > 1 else '.'

    print(f"Validating paths in: {Path(root_dir).resolve()}\n")

    results = validate_paths(root_dir)

    if results['invalid']:
        print("❌ INVALID PATHS:\n")
        for doc, ref in results['invalid']:
            rel_doc = doc.relative_to(Path(root_dir).resolve())
            print(f"  {rel_doc}")
            print(f"    → {ref}\n")

    if results['valid']:
        print(f"✓ {len(results['valid'])} valid path(s) found")

    if results['invalid']:
        print(f"✗ {len(results['invalid'])} invalid path(s) found")
        sys.exit(1)
    else:
        print("\nAll paths valid.")
        sys.exit(0)


if __name__ == "__main__":
    main()
