#!/usr/bin/env python3
"""
polish_phb_chapters.py
----------------------
• Reads every *.md in a folder
• Converts literal "\n" to real new‑lines (one pass is plenty)
• Deletes obvious OCR header/garbage lines
• Collapses 3‑plus blank lines
• Ensures ONE valid YAML block with title, chapter_index, source, slug
• Renames files to NN_<slug>.md (chapter numbers based on filename order unless you pass --start)
"""

from __future__ import annotations
import argparse, re, unicodedata, sys, textwrap
from pathlib import Path
from typing import Tuple
import yaml                          # pip install pyyaml

try:
    from tqdm import tqdm            # pip install tqdm (optional)
except ImportError:
    # Fallback: no progress bar, just iterate normally
    def tqdm(iterable, **_kwargs):   # type: ignore
        return iterable

    # Warn the user once
    print("⚠️  tqdm not installed; progress bars disabled.")



HEAD_RE       = re.compile(r'^#\s+(.*)', re.MULTILINE)
BAD_PREFIX_RE = re.compile(r'^(DUNGEONS.*DRAGONS|CONTENTS.*|PREFACE\b.*|INTRODUCTION\b.*)$', re.I)
LITERAL_NL_RE = re.compile(r'\\n')                 # backslash‑n → real newline
TOC_JUNK_RE   = re.compile(r'\\\.{2,}|\.{5,}|[a-z]{3,}\s*\\[\\\.]+', re.I)

# ---------------------------------------------------------------------------
# TEXT CLEAN‑UP UTILITIES
# ---------------------------------------------------------------------------

import re

def is_junk_line(ln: str) -> bool:
    # Remove lines with lots of dots, slashes, or repeated punctuation
    if re.search(r'(\\\.{2,}|\.{5,}|-{5,}|_{5,}|\/{5,})', ln):
        return True
    # Remove lines that are mostly non-letters
    letters = sum(c.isalpha() for c in ln)
    if len(ln.strip()) > 0 and letters / max(len(ln), 1) < 0.4:
        return True
    # Remove lines that look like page numbers or indexes
    if re.match(r'^\s*\d+\s*$', ln):
        return True
    # Remove lines that are very short and not sentences
    if len(ln.strip()) < 8 and not ln.strip().endswith('.'):
        return True
    # Remove lines that are mostly gibberish (few vowels)
    vowels = sum(c in 'aeiouAEIOU' for c in ln)
    if letters > 0 and vowels / letters < 0.2:
        return True
    return False

def filter_junk_lines(text: str) -> str:
    lines = text.splitlines()
    clean = [ln for ln in lines if not is_junk_line(ln)]
    return '\n'.join(clean)

def skip_garbage(lines):
    clean = []
    found_real = False
    for ln in lines:
        if not found_real:
            # Skip blank lines
            if not ln.strip():
                continue
            # Skip lines with lots of numbers, dots, or backslashes
            if re.match(r'^[\d\s\.\-\\\/]+$', ln):
                continue
            # Skip lines that are mostly non-letters or all uppercase
            if len(ln) > 20 and (ln.isupper() or sum(c.isalpha() for c in ln) < len(ln) * 0.5):
                continue
            # Skip lines that look like page headers/footers or known junk
            if BAD_PREFIX_RE.match(ln.strip()):
                continue
            # Skip lines that look like a table of contents
            if re.search(r'chapter|appendix|part|contents|page|section|index', ln, re.I) and len(ln) < 80:
                continue
            # Skip lines that look like OCR TOC gibberish
            if TOC_JUNK_RE.search(ln):
                continue
            # Skip lines that are under 3 words (likely junk)
            if len(ln.split()) < 3:
                continue
            # If we get here, it's probably real content
            found_real = True
        clean.append(ln)
    return clean

def remove_ocr_toc_block(txt: str) -> str:
    """
    Remove the first large block of lines that looks like an OCR table of contents or junk.
    This block is defined as consecutive lines where at least half the line is non-letter (dots, slashes, numbers, etc).
    """
    lines = txt.splitlines()
    new_lines = []
    skipping = True
    for ln in lines:
        # Calculate the ratio of non-letter to total characters
        letters = sum(c.isalpha() for c in ln)
        nonletters = len(ln) - letters
        # If more than half the line is non-letter, treat as junk
        is_junk = (len(ln.strip()) > 0 and nonletters / max(len(ln), 1) > 0.5)
        # Or if it matches a strong TOC/junk pattern
        is_junk = is_junk or re.search(r'\\\.{2,}|\.{5,}|chapter|appendix|contents|page|section|index', ln, re.I)
        if skipping and is_junk:
            continue
        # Stop skipping after the first non-junk line
        skipping = False
        new_lines.append(ln)
    return '\n'.join(new_lines).lstrip()

def normalise_text(txt: str) -> str:
    """Unicode NFC, fix literal newlines, drop garbage headers, collapse blanks."""
    txt = unicodedata.normalize('NFC', txt)
    txt = LITERAL_NL_RE.sub('\n', txt)              # convert literal "\n" once
    txt = re.sub(r'^(?:---[\s\S]*?---\s*)+', '', txt)
    txt = remove_ocr_toc_block(txt)  # <--- Add this line
    txt = filter_junk_lines(txt)     # <--- Add this line
    lines = skip_garbage(txt.splitlines())
    txt = '\n'.join(lines)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip() + '\n'


def ensure_yaml(block: str, chap_no: int, src: str = "D&D 5e Player’s Handbook") -> Tuple[dict, str]:
    """Guarantee a single, well‑formed YAML front‑matter block."""
    # strip any number of leading front-matter blocks (--- … ---)
    body = re.sub(r'^(?:---[\s\S]*?---\s*)+', '', block)


    # derive title from first H1 heading, else fallback
    match = HEAD_RE.search(body)
    title = match.group(1).strip() if match else f"Chapter {chap_no}"
    slug  = re.sub(r'[^\w]+', '-', title.lower()).strip('-')

    meta = {
        'title':         title,
        'chapter_index': chap_no,
        'source':        src,
        'slug':          slug,
    }

    yaml_block = '---\n' + yaml.safe_dump(meta, sort_keys=False).strip() + '\n---\n\n'
    return meta, yaml_block + body.lstrip()

# ---------------------------------------------------------------------------
# MAIN PROCESSOR
# ---------------------------------------------------------------------------

def process_folder(folder: Path, *, start_num: int = 1, src_name: str, dry: bool = False) -> None:
    print("Looking for .md files in:", folder)
    md_files = sorted(folder.glob('*.md'))
    print("Found files:", [str(f) for f in md_files])
    if not md_files:
        sys.exit(f"No .md files found in {folder}")

    for idx, path in tqdm(enumerate(md_files, start=start_num), total=len(md_files),
                          bar_format="{l_bar}{bar} {n_fmt}/{total_fmt}"):
        raw_text = path.read_text(encoding='utf-8')
        meta, cleaned = ensure_yaml(normalise_text(raw_text), idx, src_name)

        num  = f"{idx:02d}"
        safe = re.sub(r'[^\w]+', '_', meta['slug']).strip('_')[:60]
        new_path = path.with_name(f"{num}_{safe}.md")

        if dry:
            print(f"[dry‑run] would write {new_path.name}")
            continue

        new_path.write_text(cleaned, encoding='utf-8')
        if new_path != path:
            path.unlink()

    print(f"\n✅  Polished {len(md_files)} chapter files in '{folder}'")

# ---------------------------------------------------------------------------
# CLI WRAPPER
# ---------------------------------------------------------------------------

def cli():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""
        Clean up per‑chapter Markdown files exported from the PHB EPUB.

        examples
        --------
        # normal run
        python polish_phb_chapters.py --chapters "C:\path\to\dnd_5e_phb"

        # first chapter in folder should be counted as 0
        python polish_phb_chapters.py --chapters . --start 0

        # see what would change without writing files
        python polish_phb_chapters.py --chapters . --dry
        """))
    ap.add_argument('--chapters', required=True, help='Folder of .md files to clean')
    ap.add_argument('--source',   default='D&D 5e Player’s Handbook', help='YAML "source" field')
    ap.add_argument('--start',    type=int, default=1, help='Chapter index of the first file (default 1)')
    ap.add_argument('--dry',      action='store_true', help='Dry‑run: preview without modifying files')
    args = ap.parse_args()

    process_folder(Path(args.chapters).expanduser().resolve(),
                   start_num=args.start,
                   src_name=args.source,
                   dry=args.dry)


if __name__ == '__main__':
    cli()
