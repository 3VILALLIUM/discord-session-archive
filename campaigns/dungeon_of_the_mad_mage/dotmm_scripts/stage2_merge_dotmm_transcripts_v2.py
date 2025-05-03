#!/usr/bin/env python3
"""
Stage 2 – Merge DOTMM transcription chunks into a single Markdown (v1.2)

This script:
1. Prompts for or accepts a session folder under dotmm_transcripts.
2. Loads all chunk JSONs for that session across each track subfolder.
3. Flattens segments, assigns speaker (track folder name), and filters out noise/spelled-out gibberish.
4. Sorts chronologically and emits a Markdown file with YAML frontmatter per LoreBot conventions.

Usage:
    python stage2_merge_dotmm_transcripts_v2.py --session session_001_transcript
    # or
    python stage2_merge_dotmm_transcripts_v2.py  # uses Tkinter picker
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

# Determine project root relative to this script
ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_ROOT = ROOT / "dotmm_transcripts"
OUTPUT_ROOT = ROOT / "dotmm_output"
LOG_FILE = ROOT / "stage2_merge_dotmm.log"

# Logging
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# Helper: pick session via GUI
def pick_session() -> Path:
    if tk is None:
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
        "--session", help="Session folder name under dotmm_transcripts, e.g. session_001_transcript"
    )
    args = parser.parse_args()

    # Resolve session directory
    if args.session:
        session_dir = TRANSCRIPTS_ROOT / args.session
    else:
        session_dir = pick_session()
    if not session_dir.exists():
        sys.exit(f"Invalid session folder: {session_dir}")

    # Prepare output directory for this session
    session_out = OUTPUT_ROOT / session_dir.name
    session_out.mkdir(parents=True, exist_ok=True)

    all_segments: list[dict] = []

    # Load and collect all segments
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
                    end = seg.get("end", start)
                    if start is None or not text:
                        continue
                    all_segments.append({
                        "start": float(start),
                        "end": float(end),
                        "speaker": speaker,
                        "text": text,
                        "source": chunk_file.name
                    })
                log.info(f"Loaded {chunk_file.name}")
            except Exception as e:
                log.error(f"Failed to parse {chunk_file.name}: {e}")

    if not all_segments:
        sys.exit("No segments found for merging.")

    # Filter out noise and gibberish
    filtered: list[dict] = []
    seen: set[tuple] = set()
    for seg in all_segments:
        duration = seg["end"] - seg["start"]
        text = seg["text"]
        key = (round(seg["start"], 2), text)
        # skip very short blips
        if duration < 0.5:
            continue
        # skip spelled-out gibberish like 'P-O-N-T-E'
        if text.count("-") >= 1 and len(text.replace("-", "")) <= 6:
            continue
        if key in seen:
            continue
        seen.add(key)
        filtered.append(seg)

    # Sort chronologically
    filtered.sort(key=lambda s: s["start"])

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
    for seg in filtered:
        ts = f"{seg['start']:.2f}s"
        fm.append(f"**[{ts} {seg['speaker']}]** {seg['text']}")
        fm.append("")

    # Write out merged markdown
    output_file = session_out / f"{session_dir.name}_merged.md"
    output_file.write_text("\n".join(fm), encoding="utf-8")
    log.info(f"Merged Markdown saved: {output_file}")
    print(f"✓ Merged transcript written to {output_file}")

if __name__ == "__main__":
    main()
