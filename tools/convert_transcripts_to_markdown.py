import json
from pathlib import Path

INPUT_DIR = Path("campaigns/experimental/transcripts")
OUTPUT_DIR = Path("campaigns/experimental/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def convert_json_to_markdown(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    base_name = json_file.stem
    md_file = OUTPUT_DIR / f"{base_name}.md"

    with open(md_file, "w", encoding="utf-8") as md:
        md.write(f"# Transcript: {base_name}\n\n")
        if "text" in data:
            md.write(data["text"])
        elif "error" in data:
            md.write(f"**Error during transcription:** {data['error']}\n")
        else:
            md.write("*No transcript or error message found.*\n")

    print(f"✓ Converted {json_file.name} -> {md_file.name}")

def main():
    json_files = list(INPUT_DIR.glob("*.json"))
    if not json_files:
        print("No JSON transcripts found.")
        return

    for jf in json_files:
        convert_json_to_markdown(jf)

if __name__ == "__main__":
    main()
