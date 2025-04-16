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

logging.info("Markdown merge + conversion started")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

json_files = sorted(TRANSCRIPT_DIR.glob("*.json"))

if not json_files:
    logging.warning(f"No JSON transcripts found in {TRANSCRIPT_DIR}")
    print("No JSON transcripts found.")
    exit()

# Define a single output Markdown file
combined_md_file = OUTPUT_DIR / "experimental_combined_transcript.md"

# Start by building the YAML front matter for the combined transcript
# Adjust these metadata fields as needed
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
    "---\n",
]

all_segments_found = False

# Process each JSON file, appending its segments
for json_file in json_files:
    try:
        with open(json_file, encoding="utf-8") as jf:
            transcript = json.load(jf)
        
        segments = transcript.get("segments", [])

        # If this file has segments, append them to the combined markdown
        if segments:
            all_segments_found = True
            # Optional: Provide a small heading for each file’s content
            md_content.append(f"## Source file: {json_file.name}\n")
            
            # Append each segment
            for segment in segments:
                start_time = segment.get("start", "unknown")
                # Use the JSON filename stem (minus extension) for speaker
                speaker = json_file.stem.split("_")[0]
                text = segment.get("text", "[NO TEXT FOUND]").strip()
                
                # Format time as float if it’s numeric
                try:
                    start_time = f"{float(start_time):.2f}s"
                except (TypeError, ValueError):
                    # keep as 'unknown' if conversion fails
                    pass
                
                md_content.append(f"**[{start_time} - {speaker}]** {text}\n")

        else:
            logging.warning(f"No segments found in {json_file.name}")
            md_content.append(f"*No transcript segments found for {json_file.name}.*\n")

        logging.info(f"Merged {json_file.name} into combined transcript")

    except Exception as e:
        logging.error(f"Failed to merge {json_file.name}: {e}")
        print(f"✗ Failed {json_file.name}: {e}")

# If no segments were found at all, add a message
if not all_segments_found:
    md_content.append("*No transcript segments found in any JSON file.*\n")

# Finally, write out the combined Markdown
with open(combined_md_file, "w", encoding="utf-8") as mf:
    mf.write("\n".join(md_content))

logging.info("Markdown merge + conversion complete")
print(f"✓ Combined transcript created: {combined_md_file.name}")
