"""
Combine all HTML packet sheets in a directory into a single PDF.

Usage:
  python make_pdf.py [packet_dir] [output.pdf]

Examples:
  python make_pdf.py packets/sites2026
      → writes packets/sites2026.pdf  (teams A→Z, gate 1→7)

  python make_pdf.py packets/sites2026 out/sites2026-packets.pdf
      → writes to specified path
"""
import sys
import re
from pathlib import Path


def sort_key(path):
    """Sort by team name (alpha) then gate number (numeric)."""
    stem = path.stem  # e.g. "Eagles-gate-3"
    m = re.match(r"^(.+)-gate-(\d+)$", stem, re.IGNORECASE)
    if m:
        return (m.group(1).lower(), int(m.group(2)))
    return (stem.lower(), 0)


def main():
    try:
        from weasyprint import HTML
    except ImportError:
        print("WeasyPrint is required: pip install weasyprint")
        sys.exit(1)

    packet_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("packets/sites2026")
    if not packet_dir.is_dir():
        print(f"Directory not found: {packet_dir}")
        sys.exit(1)

    default_out = packet_dir.parent / (packet_dir.name + ".pdf")
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else default_out
    output.parent.mkdir(parents=True, exist_ok=True)

    html_files = sorted(packet_dir.glob("*.html"), key=sort_key)
    if not html_files:
        print(f"No HTML files found in {packet_dir}")
        sys.exit(1)

    total = len(html_files)
    print(f"Rendering {total} pages from {packet_dir}/")

    docs = []
    for i, path in enumerate(html_files, 1):
        print(f"  [{i:>3}/{total}] {path.name}")
        docs.append(HTML(filename=str(path.resolve())).render())

    print(f"\nMerging into {output} ...")
    all_pages = [page for doc in docs for page in doc.pages]
    docs[0].copy(all_pages).write_pdf(str(output))

    size_mb = output.stat().st_size / 1_048_576
    print(f"Done — {len(all_pages)} pages, {size_mb:.1f} MB → {output}")


if __name__ == "__main__":
    main()
