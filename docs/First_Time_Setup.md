# First-Time Setup (Quickstart)

> Only needed when setting up a new machine or sharing with collaborators.

---

## ✅ Prerequisites

- **Operating System:** Windows 11 (Pro recommended)  
- **Python:** 3.11 or later  
- **Git & Git Bash** (ensure Git is installed and in your PATH)  
- **VS Code** with the Python extension  
- **OpenAI API Key** in a `.env` file at the project root  

---

## 🚀 Setup Steps

1. **Clone the LoreBot repository**  
   ```bash
   git clone <repo_url>
   cd LoreBot
   ```

2. **Install Python dependencies**  
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**  
   Create a `.env` file in the project root containing:  
   ```text
   OPENAI_API_KEY=sk-...
   ```

4. **Verify Stage 1 transcription script**  
   ```bash
   python scripts/stage1_transcribe_dotmm_v6.py      --session campaigns/dungeon_of_the_mad_mage/raw_audio
   ```

5. **Confirm directory structure**  
   - `/campaigns/<campaign>/raw_audio/`  
   - `/campaigns/<campaign>/dotmm_transcripts/` (Whisper JSON)  
   - `/campaigns/<campaign>/dotmm_output/<session>/_raw/` (merged Markdown)  
   - `/campaigns/<campaign>/dotmm_output/<session>/*_cleaned.md` (PII‑stripped)

---

You’re now ready to run the full 3‑stage pipeline:

1. **Stage 1**: Transcribe audio → JSON  
2. **Stage 2**: Merge JSON → raw Markdown  
3. **Stage 3**: Clean raw Markdown → final `_cleaned.md`

Happy transcribing!
