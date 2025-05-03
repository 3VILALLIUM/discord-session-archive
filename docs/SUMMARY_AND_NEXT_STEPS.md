from pathlib import Path, PurePosixPath

summary_content = """# LoreBot – Summary & Next Steps  
_Date: 3 May 2025_

---

## 🚀 Key Accomplishments (April → May 2025)

| Area | Milestone |
|------|-----------|
| **Repo & CI Guardrails** | • Pre‑commit hook (`.githooks/pre-commit`) blocks raw merged Markdown. <br>• GitHub Actions workflow (`guard-raw-transcripts.yml`) fails any PR/push containing raw transcripts. |
| **Stage 1 Transcription** | `scripts/stage1_transcribe_dotmm_v6.py` <br>• 2‑min / 5‑s overlap chunks <br>• Concurrent Whisper uploads <br>• UTF‑8 per‑session logs in `logs/` |
| **Stage 2 Merge** | `scripts/stage2_merge_dotmm_transcripts_v3.py` <br>• Filters duplicates & low‑confidence text <br>• Scene‑gap insertion <br>• Outputs raw Markdown to `_raw/` |
| **Stage 3 Clean Names** | `scripts/stage3_clean_names.py` <br>• Replaces Discord handles & real names <br>• Normalises speaker tags <br>• Writes `_cleaned.md` (only file tracked) |
| **Bulk Re‑clean Helper** | `scripts/reclean_all.sh` – one‑shot regenerate all `_cleaned.md` after Stage 3 tweaks |
| **Docs & Maps** | • Master Infrastructure Map <br>• Master Instructions <br>• First‑Time Setup Quickstart <br>• Best Practices & File Manifest |
| **Ignore Policy** | `.gitignore` excludes `*.aac *.flac *.json *.log` and any `_raw/*.md` |

_Note:_ Pipeline now works end‑to‑end for **Dungeon of the Mad Mage (DOTMM)**.

---

## ⏭️ Next‑Step Roadmap

| Priority | Task | Notes |
|----------|------|-------|
| 1️⃣ | **Auto‑clean flag** – `stage2_merge … --auto-clean` | Invoke Stage 3 automatically after merge |
| 2️⃣ | **Speaker Attribution** | Map track IDs → character names via `info.txt`; inject into Stage 2 output |
| 3️⃣ | **YAML Front‑Matter Helper** | Auto‑populate `session`, `campaign`, `date`, `participants` |
| 4️⃣ | **Generalise Stage 1 Template** | Parametrise paths so a single script handles any campaign |
| 5️⃣ | **Apply Pipeline to _The Fold_** | Replicate folder scaffold & run Stages 1‑3 |
| 6️⃣ | **Enrichment Stage (GPT‑4o)** | Scene summaries, tags, NPC extraction → `/docs/lore_archive/` |
| 7️⃣ | **CI: transcribe‑on‑push** | GitHub Action that runs Stage 1 on new audio pushed to `raw_audio/` |
| 8️⃣ | **Health‑Check Dashboard** | Script to scan `logs/` for failures / gaps; output Markdown report |
| 9️⃣ | **NotebookLM Ingest** | Copy cleaned Markdown to `/notebooklm_ready/` per campaign |

---

## 🗒️ Quick Commands

```bash
# Stage 1 – transcribe DOTMM session
python scripts/stage1_transcribe_dotmm_v6.py \
  --session campaigns/dungeon_of_the_mad_mage/raw_audio/session_002_audio

# Stage 2 – merge (and soon auto‑clean)
python scripts/stage2_merge_dotmm_transcripts_v3.py \
  --session session_002_transcript --scene-gap 10

# Manual clean (if auto‑clean not yet enabled)
python scripts/stage3_clean_names.py \
  campaigns/dungeon_of_the_mad_mage/dotmm_output/session_002_transcript/_raw/session_002_transcript_merged_v3.md \
  handle_map.csv realname_map.csv
