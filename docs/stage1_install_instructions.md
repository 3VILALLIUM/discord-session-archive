# Stage 1 – Whisper Transcription Setup

This guide walks you through everything needed to run `stage1_transcribe.py` and use OpenAI’s `whisper-1` API to transcribe raw audio into structured JSON files.

---

## ✅ Prerequisites

- Windows 11 (Pro preferred)
- Python 3.11 or later
- VS Code (with Python extension)
- Git (installed and configured)
- OpenAI account + API key

---

## 🧰 Install Git for Windows

1. Go to [https://git-scm.com/downloads](https://git-scm.com/downloads)
2. Use default settings **with these customizations**:
   - Default branch name: `main`
   - Use Git from command line and third-party software
   - Use bundled OpenSSH
   - Use native Windows Secure Channel
   - Checkout Windows-style, commit Unix-style
   - Use **MinTTY** as terminal
   - Enable file system caching

---

## 🐍 Install Python Packages

In the **VS Code terminal or Git Bash**, run:

```bash
pip install openai python-dotenv
