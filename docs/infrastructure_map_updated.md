# LoreBot — Master Infrastructure Map
_Last updated: 2025-05-03_

---
## 1. High-Level Flow
```
Player Audio → Stage 1 Transcribe → Stage 2 Merge → Stage 3 Clean → Final Markdown  
      │                    ▲                   │  
      └───────── Git & VS Code ────────── GitHub Actions  
```

- **Stage 1**: `scripts/stage1_transcribe_dotmm_v6.py` (Whisper transcription)
- **Stage 2**: `scripts/stage2_merge_dotmm_transcripts_v3.py` (raw → `_raw/*.md`)
- **Stage 3**: `scripts/stage3_clean_names.py` (PII stripping → `_cleaned.md`)

Downstream: NotebookLM, Recap-Bots, and other AI interfaces.

---
## 2. Repository Layout
```plaintext
LoreBot/
├── .githooks/
│   └── pre-commit                     # blocks any *_merged_v*.md additions
├── .github/
│   └── workflows/
│       └── guard-raw-transcripts.yml # CI guard against raw Markdown
├── campaigns/
│   ├── dungeon_of_the_mad_mage/
│   │   ├── raw_audio/                 # raw .aac/.m4a (ignored)
│   │   ├── dotmm_scripts/             # campaign-specific configs
│   │   ├── dotmm_transcripts/         # Stage 1 JSON (ignored)
│   │   └── dotmm_output/              # Stage 2 & 3 Markdown
│   │       └── session_XXX/
│   │           ├── _raw/…_merged_v3.md       # ignored by git
│   │           └── …_merged_v3_cleaned.md   # tracked cleaned file
│   └── the_fold/
├── docs/                              # design & user docs
│   └── infrastructure_map.md          # this file—update to match above
├── scripts/
│   ├── stage1_transcribe_dotmm_v6.py
│   ├── stage2_merge_dotmm_transcripts_v3.py
│   ├── stage3_clean_names.py
│   └── reclean_all.sh                 # bulk re-clean helper
├── logs/                              # runtime log files (ignored)
├── .gitignore
└── README.md
```

---
## 3. Key CI/Hook Enforcements

- **Pre-commit hook** (`.githooks/pre-commit`): Blocks any new or modified `_merged_v*.md` in `_raw/`.
- **CI workflow** (`.github/workflows/guard-raw-transcripts.yml`): Fails any push/PR that has raw merged Markdown.

---
## 4. Action Items
1. **Replace** the existing `docs/infrastructure_map.md` with this updated version.  
2. **Commit** the changes:
   ```bash
   git add docs/infrastructure_map.md
   git commit -m "Update master infrastructure map to reflect current pipeline"
   ```
3. **Maintain** this file whenever the pipeline changes. 