import openai
import os
from dotenv import load_dotenv
import json
from pathlib import Path

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

chunk_path = Path("campaigns/experimental/chunks/2-3vilallium_0_chunk_003.flac")

with open(chunk_path, "rb") as f:
    response = openai.Audio.transcribe("whisper-1", f)

# Print transcript
print(response["text"])

# Optional: Save to JSON
output_path = Path("campaigns/experimental/transcripts/2-3vilallium_0_chunk_003.json")
with open(output_path, "w", encoding="utf-8") as out:
    json.dump({
        "chunk_file": chunk_path.name,
        "text": response["text"]
    }, out, indent=2, ensure_ascii=False)

print(f"✓ Transcript saved to {output_path}")
