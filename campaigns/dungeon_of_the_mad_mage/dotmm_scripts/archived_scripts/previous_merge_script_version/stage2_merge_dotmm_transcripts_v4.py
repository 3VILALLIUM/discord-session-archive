#!/usr/bin/env python3
from __future__ import annotations
"""Stage 2 (v4) – robust merge with order-independent de-duplication."""
import argparse, json, logging, sys, hashlib, re
from pathlib import Path
from typing import Dict, List

VERSION = 4
try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None

ROOT             = Path(__file__).resolve().parent.parent
TRANSCRIPTS_ROOT = ROOT / "dotmm_transcripts"
OUTPUT_ROOT      = ROOT / "dotmm_output"
LOG_DIR          = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE         = LOG_DIR / "stage2_merge_dotmm.log"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
log = logging.getLogger(__name__)

def pick_session() -> Path:
    if not tk:
        sys.exit("Tkinter missing – use --session.")
    r = tk.Tk(); r.withdraw()
    d = filedialog.askdirectory(initialdir=str(TRANSCRIPTS_ROOT),
                                title="Select session_transcript folder")
    if not d: sys.exit("No folder chosen.")
    return Path(d)

norm   = lambda t: re.sub(r"\s+", " ", t.lower().strip(" -*_—")).strip()
mdsafe = lambda t: t.replace("*", "\\*")

def main() -> None:
    p = argparse.ArgumentParser(description="Merge DOTMM chunks → raw MD (v4)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--session")
    p.add_argument("--scene-gap",  type=float, default=10.0)
    p.add_argument("--window",     type=float, default=6.0,
                   help="secs two identical lines must be apart to be kept")
    p.add_argument("--bucket",     type=float, default=0.5,
                   help="round start-time to this size before hashing")
    p.add_argument("--force",      action="store_true")
    args = p.parse_args()

    ses_dir = (TRANSCRIPTS_ROOT / args.session) if args.session else pick_session()
    if not ses_dir.exists():
        sys.exit(f"Session folder not found: {ses_dir}")

    out_dir  = OUTPUT_ROOT / ses_dir.name / "_raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{ses_dir.name}_merged_v{VERSION}.md"
    if out_file.exists() and not args.force:
        sys.exit(f"{out_file.name} exists – pass --force to overwrite")

    # ── load segments ───────────────────────────────────────
    segs: List[Dict] = []
    for track in ses_dir.iterdir():
        if not track.is_dir(): continue
        speaker = track.name
        for jf in track.glob("*.json"):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                for s in data.get("segments", []):
                    txt = s.get("text", "").strip()
                    if not txt: continue
                    segs.append(dict(
                        start=float(s["start"]),
                        end=float(s.get("end", s["start"])),
                        speaker=speaker,
                        text=txt,
                        conf=float(s.get("confidence", 1.0))))
            except Exception as e:
                log.error("Bad JSON %s: %s", jf.name, e)
    if not segs: sys.exit("No segments loaded.")

    # ── order-independent de-dupe ───────────────────────────
    last_seen: Dict[bytes, float] = {}
    filt: List[Dict] = []
    for s in segs:
        if s["end"] - s["start"] < .5 or len(s["text"]) < 3 or s["conf"] < .5:
            continue
        if s["text"].count("-") and len(s["text"]) - s["text"].count("-") <= 6:
            continue
        tbin = round(s["start"] / args.bucket) * args.bucket
        key  = hashlib.blake2b(f"{s['speaker']}|{norm(s['text'])}".encode(),
                               digest_size=6).digest()
        prev = last_seen.get(key, -1e9)
        if s["start"] - prev < args.window:
            continue                       # duplicate within window → drop
        last_seen[key] = s["start"]
        filt.append(s)

    if not filt:
        sys.exit("Everything was filtered out – relax --window or filters.")

    # ── stable sort & tie-shift ─────────────────────────────
    filt.sort(key=lambda x: x["start"])
    eps = 1e-4; last = -1.0; count = 0; prev_spk = None
    for s in filt:
        if s["speaker"] != prev_spk: count = 0
        if s["start"] <= last:
            count += 1
            s["start"] = last + eps * count
        else:
            count = 0
        prev_spk, last = s["speaker"], s["start"]

    # ── render Markdown ─────────────────────────────────────
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
