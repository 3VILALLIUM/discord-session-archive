#!/usr/bin/env python3
VERSION = 3

"""
Stage 2 (v3) – Merge DOTMM transcription chunks → clean Markdown (enhanced)

Features:
• Length, confidence, and noise gates
• Dashed-gibberish filter optimized
• Duplicate suppression (5s window) via bounded deque + stable hash
• Micro-shift tie-breaker with minimal drift and speaker resets
• Configurable scene-gap threshold and dedupe-size via CLI
• Console logging for real-time feedback
• Enhanced CLI help with default values and usage examples
• Scene-break uses max end-time to avoid false gaps during overlaps
"""

from __future__ import annotations
import argparse, json, logging, sys, hashlib
from collections import deque
from pathlib import Path

# GUI import
try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None

# Paths
ROOT             = Path(__file__).resolve().parent.parent
TRANSCRIPTS_ROOT = ROOT / "dotmm_transcripts"
OUTPUT_ROOT      = ROOT / "dotmm_output"

# Ensure the campaign’s logs folder exists
LOG_DIR          = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# write your log into that folder
LOG_FILE         = LOG_DIR / "stage2_merge_dotmm.log"

# Logging: file + console
logging.basicConfig(
    filename=str(LOG_FILE), level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.getLogger().addHandler(console)
log = logging.getLogger(__name__)

# Helper: folder picker via GUI
def pick_session() -> Path:
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(
        title="Select session_transcript folder",
        initialdir=str(TRANSCRIPTS_ROOT)
    )
    if not folder:
        sys.exit("No session selected.")
    return Path(folder)

# Escape Markdown characters
def md_safe(text: str) -> str:
    return text.replace("*", "\\*")

# Main merge function
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge DOTMM transcript chunks into cleaned Markdown.",
        epilog="Examples:\n  python %(prog)s --session session_001_transcript --dedupe-size 500\n  python %(prog)s --scene-gap 15 --dedupe-size 2000",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--session",
        help="Session folder under dotmm_transcripts (e.g. session_001_transcript)"
    )
    parser.add_argument(
        "--scene-gap",
        type=float,
        default=10.0,
        help="Seconds of silence to insert a scene header"
    )
    parser.add_argument(
        "--dedupe-size",
        type=int,
        default=1000,
        help="Maximum entries to keep in dedupe window deque"
    )
    args = parser.parse_args()

    # If no session arg and no GUI available, error
    if args.session is None and tk is None:
        sys.exit("Tkinter unavailable; please specify --session.")

    # Determine session directory
    session_dir = (TRANSCRIPTS_ROOT / args.session) if args.session else pick_session()
    if not session_dir.exists():
        sys.exit(f"Invalid session folder: {session_dir}")

    # Create output directory for this session
    session_out = OUTPUT_ROOT / session_dir.name
    session_out.mkdir(parents=True, exist_ok=True)

    # Collect segments from JSON chunks
    segments: list[dict] = []
    for track in sorted(session_dir.iterdir()):
        if not track.is_dir():
            continue
        speaker = track.name
        for chunk_file in sorted(track.glob("*.json")):
            try:
                data = json.loads(chunk_file.read_text(encoding="utf-8"))
                for seg in data.get("segments", []):
                    text = seg.get("text", "").strip()
                    if not text:
                        continue
                    segments.append({
                        "start": float(seg["start"]),
                        "end":   float(seg.get("end", seg["start"])),
                        "speaker": speaker,
                        "text":  text,
                        "conf":   float(seg.get("confidence", 1.0))
                    })
            except Exception as e:
                log.error("Failed to parse %s: %s", chunk_file, e)

    if not segments:
        sys.exit("No segments to merge.")

    # Filter and dedupe using a bounded deque for performance with stable hashing
    filtered: list[dict] = []
    recent: deque[tuple[float, bytes]] = deque(maxlen=args.dedupe_size)
    seen_hashes: set[bytes] = set()
    window = 5.0

    for seg in segments:
        duration = seg["end"] - seg["start"]
        text = seg["text"]
        # Skip too short, low-confidence, or trivial text
        if duration < 0.5 or len(text) < 3 or seg["conf"] < 0.5:
            continue
        # Skip dashed gibberish without extra allocations
        dash_count = text.count("-")
        if dash_count and (len(text) - dash_count) <= 6:
            continue
        # Purge hashes older than time window
        while recent and seg["start"] - recent[0][0] > window:
            _, old_hash = recent.popleft()
            seen_hashes.discard(old_hash)
        # Stable hash via BLAKE2b
        h = hashlib.blake2b(text.encode("utf-8"), digest_size=4).digest()
        if h in seen_hashes:
            continue
        recent.append((seg["start"], h))
        seen_hashes.add(h)
        filtered.append(seg)

    if not filtered:
        sys.exit("All segments were filtered out; consider adjusting filters.")

    # Sort by start time and apply micro-shifts for identical timestamps
    filtered.sort(key=lambda s: s["start"])
    epsilon = 0.0001  # minimal drift per tie
    last_start = -1.0
    tie_multiplier = 0
    prev_speaker = None
    for seg in filtered:
        if seg["speaker"] != prev_speaker:
            tie_multiplier = 0
        if seg["start"] <= last_start:
            tie_multiplier += 1
            seg["start"] = last_start + epsilon * tie_multiplier
        else:
            tie_multiplier = 0
        prev_speaker = seg["speaker"]
        last_start = seg["start"]

    # Build Markdown output
    md_lines: list[str] = [
        "---",
        f"session: {session_dir.name}",
        "campaign: dungeon_of_the_mad_mage",
        "tags: [transcription]",
        "summary: |",
        "  Auto-merged transcript cleaned by v3.",
        "---",
        ""
    ]

    # Track highest end time to avoid false breaks
    max_end_time = 0.0
    for seg in filtered:
        # update max end time
        if seg["end"] > max_end_time:
            max_end_time = seg["end"]
        # Insert scene header on long gaps using max_end_time
        if seg["start"] - max_end_time >= args.scene_gap:
            md_lines.append(f"### Scene break at {seg['start']:.2f}s")
            md_lines.append("")
        timestamp = f"{seg['start']:.2f}s"
        md_lines.append(f"**[{timestamp} {seg['speaker']}]** {md_safe(seg['text'])}")
        md_lines.append("")

    raw_dir     = session_out / "_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_file = raw_dir / f"{session_dir.name}_merged_v{VERSION}.md"
    output_file.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"✓ Merged transcript written to {output_file}")

if __name__ == "__main__":
    main()
