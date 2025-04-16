import os
import time
import json
import logging
from pathlib import Path
from pydub import AudioSegment
from dotenv import load_dotenv
from openai import OpenAI
from logging.handlers import RotatingFileHandler

__version__ = "2.0.0"

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

RAW_AUDIO_DIR = Path("campaigns/experimental/raw_audio")
CHUNK_DIR = Path("campaigns/experimental/chunks")
TRANSCRIPT_DIR = Path("campaigns/experimental/transcripts")
LOG_FILE = "stage1_transcribe_experimental.log"

CHUNK_LENGTH_MS = 10 * 60 * 1000
SUPPORTED_EXTENSIONS = [".aac", ".mp3", ".wav", ".m4a", ".flac"]

handler = RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=3)
logging.basicConfig(
    handlers=[handler],
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def find_audio_files(folder):
    return [p for p in folder.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS]

def chunk_audio(file_path, output_dir):
    logging.info(f"Chunking {file_path.name}")
    audio = AudioSegment.from_file(file_path)
    chunks = []
    for i, start in enumerate(range(0, len(audio), CHUNK_LENGTH_MS)):
        chunk = audio[start:start + CHUNK_LENGTH_MS]
        chunk_path = output_dir / f"{file_path.stem}_chunk_{i:03}.flac"
        chunk.export(chunk_path, format="flac")
        chunks.append((chunk_path, i))
    return chunks

def transcribe_chunk(chunk_path, chunk_index):
    logging.info(f"Transcribing {chunk_path.name}")
    try:
        with open(chunk_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json"
            )
        offset = chunk_index * (CHUNK_LENGTH_MS / 1000)
        for segment in response.segments:
            segment["start"] += offset
            segment["end"] += offset
        return {
            "chunk_file": chunk_path.name,
            "segments": response.segments
        }
    except Exception as e:
        logging.error(f"Error transcribing {chunk_path.name}: {e}")
        return {
            "chunk_file": chunk_path.name,
            "error": str(e)
        }

def save_transcript(data, output_dir):
    output_file = output_dir / f"{Path(data['chunk_file']).stem}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logging.info(f"Saved transcript: {output_file.name}")

def ensure_dirs():
    for path in [RAW_AUDIO_DIR, CHUNK_DIR, TRANSCRIPT_DIR]:
        path.mkdir(parents=True, exist_ok=True)

def main():
    start = time.time()
    logging.info("Stage 1 transcription (v1.x SDK) started")
    ensure_dirs()

    audio_files = find_audio_files(RAW_AUDIO_DIR)
    if not audio_files:
        logging.warning("No audio files found.")
        print("No audio files found in raw_audio.")
        return

    for audio_file in audio_files:
        chunks = chunk_audio(audio_file, CHUNK_DIR)
        for chunk_path, index in chunks:
            result = transcribe_chunk(chunk_path, index)
            save_transcript(result, TRANSCRIPT_DIR)

    duration = time.time() - start
    logging.info(f"Transcription complete in {duration:.2f} seconds.")
    print("Transcription complete. See transcripts/ and stage1_transcribe_experimental.log.")

if __name__ == "__main__":
    main()
