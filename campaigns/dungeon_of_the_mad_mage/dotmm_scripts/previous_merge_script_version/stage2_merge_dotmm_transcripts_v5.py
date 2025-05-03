#!/usr/bin/env python3
from __future__ import annotations
"""
Stage 2 – Merge DOTMM transcription chunks → raw Markdown  (v5)
──────────────────────────────────────────────────────────────
Fixes duplicates by:
• Sorting segments first
• Dedupe window keyed on (speaker | normalized text)
• Order-independent last_seen map (no deque window issues)

Run:
    python stage2_merge_dotmm_transcripts_v5.py --session session_002_transcript
"""

import argparse, json, logging, sys, hashlib, re
from pathlib import Path
from typing import Dict, List

VERSION = 5

# GUI picker (optional)
try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None

# ── paths ───────────────────────────────────────────────────
ROOT             = Path(__file__).resolve().parent.parent
TRANSCRIPTS_ROOT = ROOT / "dotmm_transcripts"
OUTPUT_ROOT      = ROOT / "dotmm_output"
LOG_DIR          = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE         = LOG_DIR / "stage2_merge_dotmm.log"

# ── logging ─────────────────────────────────────────────────
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
log = logging.getLogger(__name__)

# ── helpers ─────────────────────────────────────────────────
def pick_session() -> Path:
    if not tk:
        sys.exit("Tkinter unavailable – pass --session.")
    r = tk.Tk(); r.withdraw()
    d = filedialog.askdirectory(
        title="Select session_transcript folder",
        initialdir=str(TRANSCRIPTS_ROOT),
    )
    if not d: sys.exit("No folder selected.")
    return Path(d)

norm   = lambda t: re.sub(r"\s+", " ", t.lower().strip(" -*_—")).strip()
mdsafe = lambda t: t.replace("*", "\\*")

# ── main ───────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Merge DOTMM chunks → raw Markdown (v5)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--session", help="session_###_transcript under dotmm_transcripts/")
    ap.add_argument("--scene-gap",  type=float, default=10.0, help="Silence gap ⇒ scene break (s)")
    ap.add_argument("--window",     type=float, default=6.0,  help="Secs two identical lines must be apart to keep both")
    ap.add_argument("--force",      action="store_true",      help="Overwrite existing output")
    args = ap.parse_args()

    ses_dir = (TRANSCRIPTS_ROOT / args.session) if args.session else pick_session()
    if not ses_dir.exists():
        sys.exit(f"Invalid session folder: {ses_dir}")

    out_dir  = OUTPUT_ROOT / ses_dir.name / "_raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{ses_dir.name}_merged_v{VERSION}.md"
    if out_file.exists() and not args.force:
        sys.exit(f"{out_file.name} exists – use --force to overwrite")

    # ── load segments ──────────────────────────────────────
    segs: List[Dict] = []
    for track in ses_dir.iterdir():
        if not track.is_dir():
            continue
        speaker = track.name
        for jf in track.glob("*.json"):
            try:
                for s in json.loads(jf.read_text(encoding="utf-8")).get("segments", []):
                    txt = s.get("text", "").strip()
                    if not txt:
                        continue

                    # ☑️ Filler-word filter
                    if txt.lower() in {"you", "uh", "um", "er", "ah"}:
                        continue

                    segs.append(
                        dict(
                            start=float(s["start"]),
                            end=float(s.get("end", s["start"])),
                            speaker=speaker,
                            text=txt,
                            conf=float(s.get("confidence", 1.0)),
                        )
                    )
            except Exception as e:
                log.error("Failed JSON %s: %s", jf.name, e)
    if not segs:
        sys.exit("No segments loaded.")

    # ── sort first ─────────────────────────────────────────
    segs.sort(key=lambda s: s["start"])

    # ── dedupe (order-independent) ────────────────────────
    WINDOW = args.window
    last_seen: Dict[str, float] = {}
    filt: List[Dict] = []

    for s in segs:
        # quick junk filters
        if s["end"] - s["start"] < 0.5 or len(s["text"]) < 3 or s["conf"] < 0.5:
            continue
        if s["text"].count("-") and len(s["text"]) - s["text"].count("-") <= 6:
            continue

        key = f"{s['speaker']}|{norm(s['text'])}"
        prev = last_seen.get(key, -1e9)
        if s["start"] - prev < WINDOW:
            continue            # duplicate within window → skip

        last_seen[key] = s["start"]
        filt.append(s)

    if not filt:
        sys.exit("All segments filtered out – relax --window or filters.")

    # ── micro-shift ties ──────────────────────────────────
    eps = 1e-4; last = -1.0; cnt = 0; prev_spk = None
    for s in filt:
        if s["speaker"] != prev_spk:
            cnt = 0
        if s["start"] <= last:
            cnt += 1
            s["start"] = last + eps * cnt
        else:
            cnt = 0
        prev_spk, last = s["speaker"], s["start"]

    # ── Markdown build ────────────────────────────────────
    md = [
        "---",
        f"session: {ses_dir.name}",
        "campaign: dungeon_of_the_mad_mage",
        "tags: [transcription]",
        "summary: |",
        f"  Auto-merged transcript cleaned by v{VERSION}.",
        "---", ""]
    max_end = 0.0
    for s in filt:
        if s["end"] > max_end:
            max_end = s["end"]
        if s["start"] - max_end >= args.scene_gap:
            md += [f"### Scene break at {s['start']:.2f}s", ""]
        md += [f"**[{s['start']:.2f}s {s['speaker']}]** {mdsafe(s['text'])}", ""]

    out_file.write_text("\n".join(md), encoding="utf-8")
    log.info("✓ Merged transcript → %s", out_file)
    print(f"✓ Merged transcript written to {out_file}")

if __name__ == "__main__":
    main()
