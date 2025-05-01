import os
import time
import json
import logging
from pathlib import Path
from pydub import AudioSegment
import openai
from logging.handlers import RotatingFileHandler

__version__ = "1.0.0"

openai.api_key = os.getenv("OPENAI_API_KEY")

RAW_AUDIO_DIR = r"./campaigns/the_fold/raw_audio"
CHUNK_DIR = r"./campaigns/the_fold/chunks"
TRANSCRIPT_DIR = r"./campaigns/the_fold/transcripts"
LOG_FILE = "stage1_transcribe_the_fold.log"

CHUNK_LENGTH_MS = 10 * 60 * 1000
SUPPORTED_EXTENSIONS = [".aac", ".mp3", ".wav", ".m4a", ".flac"]

handler = RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=3)
logging.basicConfig(
    handlers=[handler],
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Consider filtering out large non-audio files or scanning fewer directories if performance issues arise.

def find_audio_files(folder):
    return [p for p in Path(folder).rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS]

def chunk_audio(file_path, output_dir):
    logging.info(f"Chunking {file_path.name}")
    audio = AudioSegment.from_file(file_path)
    chunks = []
    # Potential improvement: handle edge cases where file is shorter than CHUNK_LENGTH_MS.
    for i, start in enumerate(range(0, len(audio), CHUNK_LENGTH_MS)):
        chunk = audio[start:start + CHUNK_LENGTH_MS]
        chunk_path = Path(output_dir) / f"{file_path.stem}_chunk_{i:03}.flac"
        chunk.export(chunk_path, format="flac")
        chunks.append(chunk_path)
    return chunks

def transcribe_chunk(chunk_path):
    logging.info(f"Transcribing {chunk_path.name}")
    try:
        with open(chunk_path, "rb") as f:
            response = openai.Audio.transcribe("whisper-1", f)
        return {
            "chunk_file": chunk_path.name,
            "text": response["text"]
        }
    except Exception as e:
        logging.error(f"Error transcribing {chunk_path.name}: {e}")
        return {
            "chunk_file": chunk_path.name,
            "error": str(e)
        }

# If errors are frequent, consider skipping saving or marking partial transcripts differently.
def save_transcript(data, output_dir):
    output_file = Path(output_dir) / f"{Path(data['chunk_file']).stem}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logging.info(f"Saved transcript: {output_file.name}")

def ensure_dirs():
    for path in [RAW_AUDIO_DIR, CHUNK_DIR, TRANSCRIPT_DIR]:
        Path(path).mkdir(parents=True, exist_ok=True)

# Optionally add concurrency for chunk processing if needed for large-scale usage.
def main():
    start = time.time()
    logging.info("Stage 1 transcription started")
    ensure_dirs()

    audio_files = find_audio_files(RAW_AUDIO_DIR)
    if not audio_files:
        logging.warning("No audio files found.")
        print("No audio files found in raw_audio.")
        return

    for audio_file in audio_files:
        chunks = chunk_audio(audio_file, CHUNK_DIR)
        for chunk in chunks:
            result = transcribe_chunk(chunk)
            save_transcript(result, TRANSCRIPT_DIR)

    duration = time.time() - start
    logging.info(f"Stage 1 transcription complete in {duration:.2f} seconds.")
    print("Transcription complete. See transcripts/ and stage1_transcribe.log.")

if __name__ == "__main__":
    main()
