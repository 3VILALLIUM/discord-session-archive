import json
import logging
from pathlib import Path

# Directories
TRANSCRIPT_DIR = Path("./campaigns/experimental/transcripts")
OUTPUT_DIR = Path("./campaigns/experimental/output")

# Logging Configuration
logging.basicConfig(
    filename="transcript_to_md.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
)

logging.info("Markdown merge + chronological sort started")

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load all transcript chunks
json_files = sorted(TRANSCRIPT_DIR.glob("*.json"))
if not json_files:
    logging.warning(f"No JSON transcripts found in {TRANSCRIPT_DIR}")
    print("No JSON transcripts found.")
    exit()

all_segments = []

# Parse all JSON files and extract segments
for json_file in json_files:
    try:
        with open(json_file, encoding="utf-8") as jf:
            transcript = json.load(jf)

        segments = transcript.get("segments", [])
        if not segments:
            logging.warning(f"No segments found in {json_file.name}")
            continue

        speaker = json_file.stem.split("_")[0]
        for segment in segments:
            start = segment.get("start", None)
            text = segment.get("text", "").strip()
            if start is not None and text:
                all_segments.append({
                    "start": float(start),
                    "speaker": speaker,
                    "text": text,
                    "source": json_file.name
                })

        logging.info(f"Collected segments from {json_file.name}")

    except Exception as e:
        logging.error(f"Failed to parse {json_file.name}: {e}")
        print(f"✗ Failed {json_file.name}: {e}")

# Sort all segments by timestamp
all_segments.sort(key=lambda s: s["start"])

# YAML Frontmatter
md_content = [
    "---",
    "session: experimental_combined",
    "campaign: experimental",
    "location: Unknown",
    "characters: []",
    "npcs: []",
    "tags: [test, transcription]",
    "tone: neutral",
    "summary: |",
    "  Placeholder summary for merged transcript. Replace/update after review.",
    "---\n"
]

# Append sorted transcript content
for segment in all_segments:
    timestamp = f"{segment['start']:.2f}s"
    md_content.append(f"**[{timestamp} - {segment['speaker']}]** {segment['text']}\n")

# Save final markdown file
combined_md_file = OUTPUT_DIR / "experimental_combined_transcript.md"
with open(combined_md_file, "w", encoding="utf-8") as mf:
    mf.write("\n".join(md_content))

logging.info("Markdown merge + sort complete")
print(f"✓ Combined transcript created and sorted: {combined_md_file.name}")
