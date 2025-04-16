import json
import re
import logging
from pathlib import Path
from datetime import timedelta

# Configure logging
logging.basicConfig(
    filename="tools/convert_transcripts_to_markdown.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

TRANSCRIPT_DIR = Path("campaigns/experimental/transcripts")
OUTPUT_DIR = Path("campaigns/experimental/output")
INFO_FILE = Path("campaigns/experimental/raw_audio/info.txt")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def format_timestamp(seconds):
    return str(timedelta(seconds=round(seconds)))

def extract_speaker_name(filename):
    base = Path(filename).stem
    parts = base.split("_chunk_")[0].split("-")
    return parts[1] if len(parts) > 1 else "unknown"

def parse_info_file(info_path):
    metadata = {
        "session_id": "experimental_test",
        "session_title": "Untitled",
        "dm": "Unknown",
        "tags": [],
        "summary": "Placeholder summary. Replace this after review.",
        "exclude_from": []
    }

    if not info_path.exists():
        logging.warning("info.txt not found, using defaults.")
        return metadata

    content = info_path.read_text(encoding="utf-8")

    session_id = re.search(r"SESSION_ID:\s*(.+)", content)
    session_title = re.search(r"SESSION_TITLE:\s*(.+)", content)
    dm = re.search(r"DM:\s*(.+)", content)
    tags = re.findall(r"SESSION_TAGS:\s*(.+)", content)
    exclude = re.findall(r"EXCLUDE_FROM:\s*(.+)", content)
    summary_match = re.search(r"NOTES:\s*(.+)", content, re.DOTALL)

    if session_id: metadata["session_id"] = session_id.group(1).strip()
    if session_title: metadata["session_title"] = session_title.group(1).strip()
    if dm: metadata["dm"] = dm.group(1).strip()
    if tags: metadata["tags"] = [tag.strip() for tag in tags[0].split(",")]
    if exclude: metadata["exclude_from"] = [x.strip() for x in exclude[0].split(",")]
    if summary_match: metadata["summary"] = summary_match.group(1).strip()

    logging.debug(f"Parsed info.txt metadata: {metadata}")
    return metadata

def convert_json_to_markdown(json_file, meta):
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        logging.debug(f"Loaded {json_file.name}, keys: {list(data.keys())}")

        speaker = extract_speaker_name(data.get("chunk_file", json_file.name))
        base_name = json_file.stem
        md_file = OUTPUT_DIR / f"{base_name}.md"

        frontmatter = f"""---
session: {meta['session_id']}_{base_name}
title: {meta['session_title']}
campaign: experimental
dm: {meta['dm']}
location: Unknown
characters: []
npcs: []
tags: {meta['tags']}
tone: neutral
summary: |
  {meta['summary']}
---

"""

        with open(md_file, "w", encoding="utf-8") as md:
            md.write(frontmatter)

            segments = data.get("segments", None)

            if isinstance(segments, list) and segments:
                for seg in segments:
                    try:
                        start = format_timestamp(seg["start"])
                        end = format_timestamp(seg["end"])
                        line = f"**[{start}–{end}] {speaker}:** {seg['text'].strip()}\n\n"
                        md.write(line)
                    except Exception as e:
                        logging.error(f"Error writing segment in {json_file.name}: {e}")
            elif "error" in data:
                md.write(f"**Error during transcription:** {data['error']}\n")
            else:
                logging.warning(f"No segments or error field found in {json_file.name}")
                md.write("*No transcript or error message found.*\n")

        logging.info(f"✓ Converted {json_file.name} -> {md_file.name}")

    except Exception as e:
        logging.error(f"Failed to convert {json_file.name}: {e}")

def main():
    meta = parse_info_file(INFO_FILE)
    files = sorted(TRANSCRIPT_DIR.glob("*.json"))
    if not files:
        logging.warning("No transcripts found.")
        print("No transcripts found.")
        return
    for jf in files:
        convert_json_to_markdown(jf, meta)

if __name__ == "__main__":
    main()
