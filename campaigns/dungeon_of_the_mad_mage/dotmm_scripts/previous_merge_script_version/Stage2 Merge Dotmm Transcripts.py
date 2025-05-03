#!/usr/bin/env python3
"""
Stage 2 – Merge DOTMM transcription chunks into a single Markdown (v1.0)

This script:
1. Prompts for or accepts a session folder under dotmm_transcripts.
2. Loads all chunk JSONs for that session across each track subfolder.
3. Flattens segments, assigns speaker (track folder name), and sorts chronologically.
4. Emits a Markdown file with YAML frontmatter per LoreBot conventions.

Usage:
    python stage2_merge_dotmm_transcripts.py --session session_001_transcript
    # or
    python stage2_merge_dotmm_transcripts.py  # uses Tkinter picker
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path

# Optional GUI
try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None

# Config
ROOT = Path("campaigns/dungeon_of_the_mad_mage")
TRANSCRIPTS_ROOT = ROOT / "dotmm_transcripts"
OUTPUT_ROOT = ROOT / "dotmm_output"
LOG_FILE = "stage2_merge_dotmm.log"

# Logging
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# Helper: pick session
def pick_session() -> Path:
    if not tk:
        sys.exit("Tkinter not available; please specify --session.")
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(
        title="Select session_transcript folder",
        initialdir=str(TRANSCRIPTS_ROOT)
    )
    if not folder:
        sys.exit("No session selected.")
    return Path(folder)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge DOTMM transcript chunks to Markdown.")
    parser.add_argument(
        "--session", help="Name of session folder under dotmm_transcripts (e.g. session_001_transcript)"
    )
    args = parser.parse_args()

    session_dir = (TRANSCRIPTS_ROOT / args.session) if args.session else pick_session()
    if not session_dir.exists():
        sys.exit(f"Invalid session folder: {session_dir}")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    all_segments: list[dict] = []

    # Iterate each track subfolder
    for track_dir in sorted(session_dir.iterdir()):
        if not track_dir.is_dir():
            continue
        speaker = track_dir.name
        for chunk_file in sorted(track_dir.glob("*.json")):
            try:
                data = json.loads(chunk_file.read_text(encoding="utf-8"))
                for seg in data.get("segments", []):
                    text = seg.get("text", "").strip()
                    start = seg.get("start")
                    if start is not None and text:
                        all_segments.append({
                            "start": float(start),
                            "speaker": speaker,
                            "text": text,
                            "source": chunk_file.name
                        })
                log.info(f"Loaded {chunk_file.name}")
            except Exception as e:
                log.error(f"Failed to parse {chunk_file}: {e}")

    if not all_segments:
        sys.exit("No segments found for merging.")

    # Sort by timestamp
    all_segments.sort(key=lambda s: s["start"])

    # Build Markdown
    fm = [
        "---",
        f"session: {session_dir.name}",
        "campaign: dungeon_of_the_mad_mage",
        f"first_appearance: {session_dir.name}",
        "tags: [transcription]",
        "summary: |",
        "  Auto-merged transcript. Please review and annotate.",
        "---",
        ""
    ]
    for seg in all_segments:
        timestamp = f"{seg['start']:.2f}s"
        fm.append(f"**[{timestamp} {seg['speaker']}]** {seg['text']}")
        fm.append("")

    output_file = OUTPUT_ROOT / f"{session_dir.name}_merged.md"
    output_file.write_text("\n".join(fm), encoding="utf-8")
    log.info(f"Merged Markdown saved: {output_file}")
    print(f"✓ Merged transcript written to {output_file}")

if __name__ == "__main__":
    main()
    