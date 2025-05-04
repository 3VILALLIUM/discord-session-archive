#!/usr/bin/env python3
"""
clean_phb_chapters.py
---------------------
Usage:
    python clean_phb_chapters.py \
        --chapters "C:/…/reference_materials/dnd_5e_phb" \
        --source   "D&D 5e Player’s Handbook"

Requires:  pip install pyyaml
"""

from pathlib import Path
from typing  import Tuple, List
import re, unicodedata, argparse, yaml

# ---------- CONFIGURABLE PATTERNS ----------
HEADING_RE     = re.compile(r'^#\s+(.*)', re.MULTILINE)
BAD_PREFIX_RE  = re.compile(r'^(DUNGEONS.*DRAGONS|CONTENTS.*?)$', re.I)
FRONT_RE       = re.compile(r'\A---.*?---\s*', re.DOTALL)  # 1st YAML block
# -------------------------------------------


# ---------- TEXT UTILITIES ----------
def normalise_text(text: str) -> str:
    """Unicode NFC, drop OCR junk, collapse >2 blank lines."""
    # NFC normalisation
    text = unicodedata.normalize('NFC', text)

    # Remove known noisy lines
    text = '\n'.join(
        ln for ln in text.splitlines()
        if not BAD_PREFIX_RE.match(ln.strip())
    )

    # Collapse triple-plus blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip() + '\n'


def ensure_yaml(text: str, idx: int, src: str) -> Tuple[dict, str]:
    """Strip any YAML, build fresh front-matter, return (meta, new_text)."""
    # Drop whatever YAML was at top
    body = FRONT_RE.sub('', text, count=1)

    m = HEADING_RE.search(body)
    title = m.group(1).strip() if m else f'Chapter {idx}'

    meta = {
        'title':          title,
        'chapter_index':  idx,
        'source':         src,
        'slug':           re.sub(r'[^\w]+', '-', title.lower()).strip('-')
    }

    yaml_block = '---\n' + yaml.safe_dump(meta, sort_keys=False).strip() + '\n---\n\n'
    return meta, yaml_block + body.lstrip()
# -------------------------------------------


def clean_folder(chapter_dir: Path, source_name: str) -> None:
    md_files: List[Path] = sorted(chapter_dir.glob('*.md'))
    if not md_files:
        raise SystemExit(f'No .md files found in {chapter_dir}')

    for idx, path in enumerate(md_files, start=1):
        raw      = path.read_text(encoding='utf-8')
        meta, out = ensure_yaml(normalise_text(raw), idx, source_name)

        num   = f'{idx:02d}'
        safe  = re.sub(r'[^\w]+', '_', meta["title"]).strip('_')
        new_name = f'{num}_{safe}.md'
        new_path = path.with_name(new_name)

        new_path.write_text(out, encoding='utf-8')
        if new_path != path:
            path.unlink()

        print(f'✔ {new_path.name}')

    print(f'\n✨ Cleaned {len(md_files)} chapter files in {chapter_dir}')


# ---------- CLI ---------- #
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="Clean & rename PHB chapter Markdown files.")
    ap.add_argument('--chapters', required=True,
                    help='Folder that already contains per-chapter .md files')
    ap.add_argument('--source', default='D&D 5e Player’s Handbook',
                    help='Value for the YAML “source” field')
    args = ap.parse_args()

    clean_folder(Path(args.chapters).expanduser().resolve(), args.source)
