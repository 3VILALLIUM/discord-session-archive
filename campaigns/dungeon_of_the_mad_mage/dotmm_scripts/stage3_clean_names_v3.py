#!/usr/bin/env python3
"""
Stage 3 – Clean Names (v3)
• Drag-and-drop friendly: accepts a file or directory path, or opens a picker.
• Batch-cleans every *_merged_v*.md it finds (recursively unless --no-recursive).
• Replaces   ① @discord handles
             ② real names
             ③ speaker tags like [1.23s 1-mathyieu_0]
• Mapping CSVs must be semicolon-delimited:  original;replacement
"""

from __future__ import annotations
import argparse, csv, re, sys, tempfile
from pathlib import Path
from typing import Dict, Iterable, List

# ── optional GUI picker ──────────────────────────────────────────────────────
try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:   # headless / minimal python
    tk = None

# ── helpers ─────────────────────────────────────────────────────────────────
def pick_path() -> Path:
    """Ask the user to pick a .md file or folder containing them."""
    if not tk:
        sys.exit("Tk-inter not available; pass a path on the command-line.")
    root = tk.Tk(); root.withdraw()
    choice = filedialog.askopenfilename(title="Select merged .md _or_ a folder",
                                        filetypes=[("Markdown", "*.md"), ("All", "*.*")])
    if not choice:
        choice = filedialog.askdirectory(title="…or pick a folder with merged transcripts")
    if not choice:
        sys.exit("Nothing selected; aborting.")
    return Path(choice)

def load_map(csv_file: Path) -> Dict[str, str]:
    """Load `key;value` pairs into a dict (whitespace trimmed, case-preserving)."""
    m: Dict[str, str] = {}
    with csv_file.open(encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter=";"):
            if len(row) == 2:
                k, v = row[0].strip(), row[1].strip()
                if k: m[k] = v
    return m

def build_realname_pattern(names: Iterable[str]) -> re.Pattern:
    """Single regex that matches any real-name key with word boundaries."""
    esc = [re.escape(n) for n in names if n]
    return re.compile(r"\b(?:" + "|".join(esc) + r")\b") if esc else re.compile(r"$^")

MENTION_RE     = re.compile(r"@\w+")
SPEAKER_RE     = re.compile(r"(\[\s*\d+\.\d+\s*s\s+)([\w-]+)(\s*\])")   # [12.34s 1-name_0]

def replace_handles(text: str, handle_map: Dict[str, str]) -> str:
    return MENTION_RE.sub(lambda m: handle_map.get(m.group(), m.group()), text)

def replace_realnames(text: str, real_pat: re.Pattern, real_map: Dict[str,str]) -> str:
    return real_pat.sub(lambda m: real_map.get(m.group(), m.group()), text)

def replace_speaker_tag(text: str, handle_map: Dict[str, str]) -> str:
    """Swap 1-mathyieu_0 → mapped replacement inside the […] tag."""
    def sub(m: re.Match) -> str:
        pre, tag, post = m.groups()
        try:
            _, rest = tag.split("-", 1)        # drop leading track-index
            handle  = "@" + rest.rsplit("_", 1)[0]
        except ValueError:
            return m.group(0)
        replacement = handle_map.get(handle, tag)
        return f"{pre}{replacement}{post}"
    return SPEAKER_RE.sub(sub, text)

def clean_line(line: str,
               handle_map: Dict[str, str],
               real_pat: re.Pattern,
               real_map: Dict[str, str]) -> str:
    line = replace_handles(line, handle_map)
    line = replace_realnames(line, real_pat, real_map)
    line = replace_speaker_tag(line, handle_map)
    return line

def destination_for(src: Path, out_dir: Path|None) -> Path:
    """Decide where the cleaned file should live."""
    if out_dir:                       # user overrode
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / (src.stem + "_cleaned.md")
    # default rules
    parent = src.parent
    if parent.name == "_raw":         # move one dir up (tracked)
        parent = parent.parent
    return parent / (src.stem + "_cleaned.md")

def process_file(src: Path,
                 handle_map: Dict[str,str],
                 real_pat: re.Pattern,
                 real_map: Dict[str,str],
                 out_dir: Path|None,
                 force: bool) -> Path:
    dst = destination_for(src, out_dir)
    if dst.exists() and not force:
        print(f"✗ {dst.name} exists; use --force to overwrite.", file=sys.stderr)
        return dst

    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(dst.parent),
                                     encoding="utf-8") as tmp, \
         src.open(encoding="utf-8") as inp:
        for line in inp:
            tmp.write(clean_line(line.rstrip("\n"),
                                 handle_map, real_pat, real_map) + "\n")
        temp_name = tmp.name
    Path(temp_name).replace(dst)
    print(f"✓ Cleaned → {dst}")
    return dst

def find_md_files(path: Path, recursive: bool=True) -> List[Path]:
    if path.is_file() and path.suffix.lower() == ".md":
        return [path]
    pattern = "**/*_merged_v*.md" if recursive else "*_merged_v*.md"
    return sorted(p for p in path.glob(pattern) if p.is_file())

# ── main CLI ────────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(
        description="Stage 3 – Clean PII from merged transcripts (v3)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("path", nargs="?",
                   help="Merged *.md file or folder containing them (drag-and-drop)")
    p.add_argument("handle_map", type=Path,
                   help="CSV mapping for @discord handles (@orig;Replacement)")
    p.add_argument("real_map",   type=Path,
                   help="CSV mapping for real names (Real;Replacement)")
    p.add_argument("--output-dir", type=Path,
                   help="Write cleaned file(s) here instead of alongside source")
    p.add_argument("--no-recursive", action="store_true",
                   help="Do NOT recurse into sub-folders when given a directory")
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing cleaned files")
    args = p.parse_args()

    # Pick path interactively?
    target = Path(args.path) if args.path else pick_path()
    if not target.exists():
        sys.exit(f"Path not found: {target}")

    # Load maps
    handle_map = load_map(args.handle_map)
    real_map   = load_map(args.real_map)
    real_pat   = build_realname_pattern(real_map.keys())

    md_files = find_md_files(target, recursive=not args.no_recursive)
    if not md_files:
        sys.exit("No *_merged_v*.md files found to clean.")

    for md in md_files:
        process_file(md, handle_map, real_pat, real_map,
                     args.output_dir, args.force)

if __name__ == "__main__":
    main()
