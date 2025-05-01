# LoreBot — **Master Infrastructure Map**  
_Last updated: 2025‑05‑01_

---
## 1. High‑Level Overview
```
Player Audio  ─▶  Stage 1 Transcribe (Whisper)  ─▶  Stage 2 Enrich (GPT‑4 Turbo)  ─▶  Markdown Lore Archive  ─▶  NotebookLM / Recap Bots
                                ▲                                        │
                                │                                        ▼
                           GitHub Actions  ◀── Git + VS Code  ◀── Local Dev  
```
* **Local Dev (Windows 11 / VS Code / Git Bash)** — where audio is dropped & scripts are run.
* **GitHub** — private repo hosts code, docs, and GitHub Actions automation.
* **OpenAI APIs** — Whisper (via `audio.transcriptions`) & GPT‑4‑Turbo for enrichment.
* **NotebookLM / Recap Bot** — downstream knowledge interface for players/DM.

---
## 2. Repository Layout
```plaintext
LOREBOT/
├── campaigns/
│   ├── dungeon_of_the_mad_mage/   # DOTMM campaign assets
│   │   ├── raw_audio/             # un‑chunked .aac/.m4a
│   │   ├── chunks/                # 10‑min .flac slices
│   │   ├── transcripts/           # per‑chunk JSON (Whisper output)
│   │   ├── output/                # per‑chunk or merged .md
│   │   └── (characters|items|...)
│   ├── the_fold/
│   └── experimental/
├── docs/                          # user & design docs
│   ├── LOREBOT_INSTRUCTIONS.md
│   ├── stage1_install_instructions.md
│   ├── SUMMARY_AND_NEXT_STEPS.md
│   └── infrastructure_map_updated.md   ← _this file_
├── scripts/                       # one‑shot launchers
│   ├── stage1_transcribe_dotmm.py
│   ├── stage1_transcribe_the_fold.py
│   └── stage1_transcribe_experimental*.py
├── tools/                         # importable helper modules
│   ├── convert_transcripts_to_markdown.py
│   ├── transcribe_single_chunk.py
│   ├── view_log_summary.py
│   └── __init__.py
├── logs/                          # runtime .log files
├── .env                           # OPENAI_API_KEY (ignored)
├── .gitignore
└── README.md
```

---
## 3. Data‑Flow Pipeline
| Stage | Script / Action | Input ➜ Output | Cloud Calls | Notes |
|-------|-----------------|----------------|-------------|-------|
| **0** | _recording_ | Discord CraigBot ➜ `.aac` | — | Info saved in `info.txt`. |
| **1** | `stage1_transcribe_<campaign>.py` | `raw_audio/*` ➜ `chunks/*.flac` ➜ `transcripts/*.json` | Whisper 1 | Retries, per‑segment JSON (`verbose_json`). |
| **2** | `convert_transcripts_to_markdown.py` | JSON ➜ chunk `.md` | — | Adds YAML front‑matter. |
| **3** | **(TODO)** `merge_chunks.py` | chunk .md ➜ session .md | — | Concatenate & fix timestamps. |
| **4** | **(TODO)** `enrich_transcript.py` | session .md ➜ enriched .md | GPT‑4‑Turbo | Summaries, tags, speaker attribution. |
| **5** | GitHub Pages / NotebookLM | enriched .md ➜ searchable UI | — | Private deployment only. |

---
## 4. Automation & CI/CD
| Layer | Tool | Purpose |
|-------|------|---------|
| **GitHub Actions** | `transcribe-on-push.yml` (planned) | Auto‑run Stage 1 on new audio pushed to `raw_audio/` branch. |
| **Scheduled Action** | `weekly-health-check.yml` | Lint repo, scan for failed chunks, open issue if found. |
| **Secrets** | `OPENAI_API_KEY`, optional `GH_PAT` | Stored in repo → Settings → Secrets. |

---
## 5. Environments
| Environment | Host | Python | Purpose |
|-------------|------|--------|---------|
| **Local Dev** | Win 11 Pro, VS Code | 3.11.x | Running scripts interactively. |
| **GitHub Runner** | ubuntu‑latest | 3.11 | Automated CI jobs. |
| **NotebookLM** | Google | — | Query‑time AI summaries / Q&A. |

---
## 6. Key Scripts & Their Constants
```python
# Example: scripts/stage1_transcribe_dotmm.py
RAW_AUDIO_DIR   = "campaigns/dungeon_of_the_mad_mage/raw_audio"
CHUNK_DIR       = "campaigns/dungeon_of_the_mad_mage/chunks"
TRANSCRIPT_DIR  = "campaigns/dungeon_of_the_mad_mage/transcripts"
LOG_FILE        = "logs/dotmm_stage1.log"
```
Update these per campaign.

---
## 7. OpenAI Usage & Cost Controls
* Whisper 1 at ~$0.006 / minute. Use short test clips in `experimental/` to avoid cost spikes.
* GPT‑4‑Turbo usage gated to Stage 4 enrichment; can be toggled off via env flag `ENABLE_ENRICH=0`.
* Retry logic backs off after 3 attempts; 429 errors logged.

---
## 8. Major To‑Do Checklist (Tracking)
- [ ] **Finalize DOTMM Stage 1 script** (`scripts/stage1_transcribe_dotmm.py`).
- [ ] Build **merge_chunks.py** (Stage 3) to create session transcripts.
- [ ] Add **PII stripping** pass.
- [ ] Implement **speaker attribution** using `info.txt`.
- [ ] Auto‑front‑matter & GPT summary (Stage 4).
- [ ] GitHub Actions workflows for automated runs.
- [ ] Dashboard / CLI for failed‑chunk monitoring.
- [ ] NotebookLM ingestion notebooks.

---
### Quick Commands
```powershell
# Run transcription for DOTMM
python scripts/stage1_transcribe_dotmm.py

# Convert JSON → Markdown after transcription
python tools/convert_transcripts_to_markdown.py

# View summary of log files
python tools/view_log_summary.py
```

---
**Reference Docs:**  
`docs/LOREBOT_INSTRUCTIONS.md`, `docs/SUMMARY_AND_NEXT_STEPS.md`

Feel free to update this map as the infrastructure evolves.
