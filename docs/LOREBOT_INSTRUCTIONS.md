# LoreBot Archive – Master Instructions

Welcome to the **LoreBot Project**, a privacy-first system for transcribing, enriching, and structuring Dungeons & Dragons campaign content.

---

## 📦 Repository Purpose

This repo is built for:

- Multi-campaign archive management (`/campaigns/the_fold`, `/dungeon_of_the_mad_mage`)
- Transcription workflows using OpenAI's Whisper (`whisper-1` API)
- Structured Markdown lore storage (NPCs, items, locations, etc.)
- Future AI enrichment (scene tagging, summaries, etc.)
- GitHub versioning with private-only access
- NotebookLM compatibility (via `/notebooklm_ready` folder)

---

## 🛠️ Setup Checklist

- [x] Git installed and initialized
- [x] Folder structure created for all campaigns
- [x] `.gitignore` in place to protect sensitive/large files
- [x] GitHub remote connected (private repo)
- [x] `OPENAI_API_KEY` in `.env` file
- [x] `stage1_transcribe.py` ready to use

---

## 🚦 Workflow Overview

### 🔹 Stage 1: Transcribe
> File: `stage1_transcribe.py`

- Pulls audio from `/campaigns/.../raw_audio/`
- Transcribes using OpenAI Whisper (`whisper-1`)
- Saves JSON transcript to `/transcripts/`

### 🔹 Stage 2: Format + Annotate *(coming soon)*
- Convert JSON → Markdown with YAML scene blocks
- Add tone, tags, and locations per scene
- Output clean `.md` files in `/output/`

### 🔹 Stage 3: Lore Extraction
- Identify recurring NPCs, locations, items
- Auto-generate individual lore files
- Store in `/characters/`, `/npcs/`, `/locations/`, etc.

### 🔹 Stage 4: Upload to NotebookLM
- Copy relevant `.md` files to `/notebooklm_ready/`
- Upload to private AI notebook
- Search using natural language prompts

---

## 🔐 Privacy & Security

- This repo is **private**
- `.env` and raw audio are **never tracked by Git**
- GitHub Actions (optional) will run in a locked-down environment
- NotebookLM is read-only and not publicly discoverable

---

## 📁 Folder Overview

