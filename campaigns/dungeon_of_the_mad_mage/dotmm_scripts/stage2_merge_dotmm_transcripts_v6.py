#!/usr/bin/env python3
from __future__ import annotations
"""
Stage 2 – Merge DOTMM transcription chunks → raw Markdown  (v6)

Fixes from v5
• Filters one-word fillers, URLs, and any non-ASCII text early
• Caps identical repeated lines per speaker (default 10)
• Keeps other v5 improvements: sort-first, order-independent de-duplication,
  --force safety, logging in /logs/
"""

import argparse, json, logging, sys, re, hashlib
from pathlib import Path
from collections import Counter
from typing import Dict, List

VERSION = 6

# optional GUI picker
try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None
    filedialog = None  # type: ignore

# ── paths ───────────────────────────────
ROOT             = Path(__file__).resolve().parent.parent
TRANSCRIPTS_ROOT = ROOT / "dotmm_transcripts"
OUTPUT_ROOT      = ROOT / "dotmm_output"
LOG_DIR          = ROOT / "logs"; LOG_DIR.mkdir(exist_ok=True)
LOG_FILE         = LOG_DIR / "stage2_merge_dotmm.log"

# ── logging ─────────────────────────────
logging.basicConfig(filename=LOG_FILE,
                    level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
log = logging.getLogger(__name__)

# ── helpers ─────────────────────────────
def pick_session() -> Path:
    if not tk or filedialog is None:
        sys.exit("Tkinter unavailable – pass --session.")
    r = tk.Tk(); r.withdraw()
    d = filedialog.askdirectory(initialdir=str(TRANSCRIPTS_ROOT),
                                title="Select session_transcript folder")
    if not d:
        sys.exit("No folder selected.")
    return Path(d)

norm   = lambda t: re.sub(r"\s+", " ", t.lower().strip(" -*_—")).strip()
mdsafe = lambda t: t.replace("*", "\\*")

# basic regexes
# existing regexes
URL_RE   = re.compile(r'https?://|www\.|[a-zA-Z0-9-]+\.[a-zA-Z]{2,4}')
NON_LAT  = re.compile(r'[^\x00-\x7F]')
NUMERIC_ONLY = re.compile(r'^\d+(?:\.\d+)*$')

# new: match “1. Ychwanegwch …” / “Byddwn i’n …” / etc.
WELSH_UI = re.compile(
    r'\b(Ychwanegwch|Gwiriong|Gwrdd|Byddwn|Rydyn)\b', re.I
)

FILLERS  = {"you", "uh", "um", "er", "ah"}

# ── main ────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(
        description="Merge DOTMM chunks → raw Markdown (v6)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--session", help="session_###_transcript folder")
    p.add_argument("--scene-gap",  type=float, default=10.0,
                   help="Silence gap ⇒ scene break (seconds)")
    p.add_argument("--window",     type=float, default=6.0,
                   help="Secs two identical lines must be apart to keep both")
    p.add_argument("--max-repeats", type=int, default=5,
               help="Keep at most N identical lines per speaker (after filters)")
    p.add_argument("--force",      action="store_true",
                   help="Overwrite existing output")
    args = p.parse_args()

    ses_dir = (TRANSCRIPTS_ROOT / args.session) if args.session else pick_session()
    if not ses_dir.exists():
        sys.exit(f"Invalid session folder: {ses_dir}")

    out_dir  = OUTPUT_ROOT / ses_dir.name / "_raw"; out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{ses_dir.name}_merged_v{VERSION}.md"
    if out_file.exists() and not args.force:
        sys.exit(f"{out_file.name} exists – pass --force to overwrite")

    # ── load segments ──────────────────────────────────────
    segs: List[Dict] = []
    for track in ses_dir.iterdir():
        if not track.is_dir():
            continue
        speaker = track.name
        for jf in track.glob("*.json"):
            try:
                data = json.loads(jf.read_text("utf-8"))
            except Exception as e:
                log.error("Bad JSON %s: %s", jf, e)
                continue

            for s in data.get("segments", []):
                txt = s.get("text", "").strip()
                if not txt:
                    continue

                # 1) one-word fillers
                if txt.lower() in FILLERS:
                    continue
                # 2) links or non-ASCII
                if URL_RE.search(txt) or NON_LAT.search(txt):
                    continue
                # 3) numeric-only junk (countdowns, ruler ticks)
                if NUMERIC_ONLY.fullmatch(txt):
                    continue
                # 4) Welsh UI/prompts (garbled)
                if WELSH_UI.search(txt):
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
    if not segs:
        sys.exit("No segments loaded.")


    # ── throttle excessive repeats ──────
    counts = Counter((s['speaker'], norm(s['text'])) for s in segs)
    segs   = [s for s in segs if counts[(s['speaker'], norm(s['text']))] <= args.max_repeats]

    # ── sort first ──────────────────────
    segs.sort(key=lambda s: s["start"])

    # ── dedupe (order-independent) ──────
    WINDOW      = args.window
    last_seen: Dict[str, float] = {}
    filt: List[Dict] = []

    for s in segs:
        # skip super-short / low-conf
        if s["end"] - s["start"] < 0.5 or len(s["text"]) < 3 or s["conf"] < 0.5:
            continue
        if s["text"].count("-") and len(s["text"]) - s["text"].count("-") <= 6:
            continue

        key  = f"{s['speaker']}|{norm(s['text'])}"
        prev = last_seen.get(key, -1e9)
        if s["start"] - prev < WINDOW:
            continue
        last_seen[key] = s["start"]
        filt.append(s)

    if not filt:
        sys.exit("All segments filtered out – relax filters.")

    # ── micro-shift ties ─────────────────
    eps = 1e-4; last = -1.0; n = 0; prev_spk = None
    for s in filt:
        if s["speaker"] != prev_spk: n = 0
        if s["start"] <= last:
            n += 1
            s["start"] = last + eps * n
        else:
            n = 0
        prev_spk, last = s["speaker"], s["start"]

    # ── Markdown build ──────────────────
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
        if s["end"] > max_end: max_end = s["end"]
        if s["start"] - max_end >= args.scene_gap:
            md += [f"### Scene break at {s['start']:.2f}s", ""]
        md += [f"**[{s['start']:.2f}s {s['speaker']}]** {mdsafe(s['text'])}", ""]

    out_file.write_text("\n".join(md), encoding="utf-8")
    log.info("✓ Merged transcript → %s", out_file)
    print(f"✓ Merged transcript written to {out_file}")

if __name__ == "__main__":
    main()
