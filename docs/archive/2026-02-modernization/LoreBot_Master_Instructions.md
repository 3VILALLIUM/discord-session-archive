# LoreBot Archive – Master Instructions

Welcome to the **LoreBot Project**, a privacy-first, multi-campaign system for transcribing, merging, cleaning, and enriching Dungeons & Dragons session content.

---

## 📦 Repository Purpose

This repo supports:

- **Multi-campaign archive** (`/campaigns/the_fold`, `/campaigns/dungeon_of_the_mad_mage`, etc.)
- **Stage 1 Transcription** using OpenAI Whisper (`whisper-1` API)
- **Stage 2 Markdown Merge** for session-level transcripts
- **Stage 3 PII Cleaning** for safe, shareable Markdown
- **Future Enrichment** (scene tagging, AI summaries, lore extraction)
- **Version control & CI/CD** with GitHub Actions
- **NotebookLM / Recap Bot** compatibility via `/notebooklm_ready`

---

## 🛠️ Setup Checklist

- [ ] Git & Git Bash (or POSIX shell) installed
- [ ] Repo cloned & remote set to a **private** GitHub repository
- [ ] `.gitignore` configured to exclude raw audio, JSON, logs, and `_raw/*.md`
- [ ] `OPENAI_API_KEY` stored in a `.env` file at project root
- [ ] Dependencies installed (e.g., `pip install -r requirements.txt`)
- [ ] Scripts folder set up:
  - `scripts/stage1_transcribe_dotmm_v6.py`
  - `scripts/stage2_merge_dotmm_transcripts_v3.py`
  - `scripts/stage3_clean_names.py`
  - `scripts/reclean_all.sh` (helper)
- [ ] `.githooks/pre-commit` in place and executable
- [ ] GitHub Actions workflow for raw-transcript guard in `.github/workflows/`

---

## 🚦 Workflow Overview

### 🔹 Stage 1: Transcribe
**Script:** `scripts/stage1_transcribe_dotmm_v6.py`

- Input: `/campaigns/<campaign>/raw_audio/*.aac/.m4a`
- Action: Chunk audio → call Whisper → save per-chunk JSON in `/campaigns/<campaign>/dotmm_transcripts/`
- Output: JSON files (ignored by Git)

### 🔹 Stage 2: Merge
**Script:** `scripts/stage2_merge_dotmm_transcripts_v3.py`

- Input: JSON transcripts
- Action: Concatenate segments into a single Markdown, inserting scene breaks
- Output: Raw merged Markdown in `/campaigns/<campaign>/dotmm_output/<session>/_raw/` (ignored)

### 🔹 Stage 3: Clean
**Script:** `scripts/stage3_clean_names.py`

- Input: Raw merged Markdown
- Action: Strip PII using handle & real-name maps → produce `_cleaned.md`
- Output: Clean Markdown in `/campaigns/<campaign>/dotmm_output/<session>/` (tracked)

### 🔹 Future Stages (TODO)
- **Enrich** with GPT-4 Turbo: summaries, tags, narrative highlights
- **Extract Lore**: generate NPC, location, item files
- **NotebookLM Prep**: copy cleaned Markdown to `/notebooklm_ready/`

---

## 🔐 Privacy & Security

- **Private repo only**: never public
- **.env** must be in `.gitignore`
- **Raw audio**, **JSON transcripts**, and **_raw Markdown** are always ignored
- **Pre-commit hook** blocks new/modified raw Markdown
- **CI workflow** fails on any raw file present in PRs/pushes to `main`

---

## 📁 Folder Overview
```plaintext
LoreBot/
├── .githooks/
│   └── pre-commit
├── .github/
│   └── workflows/
│       └── guard-raw-transcripts.yml
├── campaigns/
│   ├── <campaign_name>/
│   │   ├── raw_audio/           # raw .aac/.m4a (ignored)
│   │   ├── dotmm_scripts/       # campaign-specific configs
│   │   ├── dotmm_transcripts/   # Stage 1 JSON (ignored)
│   │   └── dotmm_output/        # Stage 2 & Stage 3 Markdown
│   │       └── <session>/
│   │           ├── _raw/        # raw merged Markdown (ignored)
│   │           │   └── *_merged_v*.md
│   │           └── *_cleaned.md # PII-stripped, tracked Markdown
│   └── <next_campaign>/
├── docs/
│   └── infrastructure_map.md    # update this when pipeline changes
├── scripts/
│   ├── stage1_transcribe_dotmm_v6.py
│   ├── stage2_merge_dotmm_transcripts_v3.py
│   ├── stage3_clean_names.py
│   └── reclean_all.sh
├── .env                         # OPENAI_API_KEY (ignored)
├── .gitignore
└── README.md
```

---

## 4. Key CI/Hook Enforcements

- **Pre-commit hook** (`.githooks/pre-commit`): Blocks any new or modified `_merged_v*.md` in `_raw/`.
- **CI workflow** (`.github/workflows/guard-raw-transcripts.yml`): Fails any push/PR that has raw merged Markdown.

---
