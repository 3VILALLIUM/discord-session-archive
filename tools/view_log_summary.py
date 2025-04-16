import re
from pathlib import Path

LOG_DIR = Path(".")
LOG_FILE_NAMES = sorted(LOG_DIR.glob("stage1_transcribe_*.log"))

def summarize_log(file_path):
    print(f"\n=== Summary for {file_path.name} ===")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    chunked_files = []
    transcribed = []
    errors = []
    duration = None

    for line in lines:
        if "Chunking" in line:
            chunked_files.append(line.strip())
        elif "Transcribing" in line:
            transcribed.append(line.strip())
        elif "Error" in line:
            errors.append(line.strip())
        elif "transcription complete in" in line:
            duration = line.strip()

    print(f"Chunks created: {len(chunked_files)}")
    print(f"Chunks transcribed: {len(transcribed)}")
    print(f"Errors: {len(errors)}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"- {e}")
    if duration:
        print(f"\n{duration}")
    print("\n")

def main():
    if not LOG_FILE_NAMES:
        print("No stage1_transcribe_*.log files found.")
        return

    print("Available log files:")
    for i, log_file in enumerate(LOG_FILE_NAMES, 1):
        print(f"{i}: {log_file.name}")

    choice = input("Select a log file number to summarize (or press Enter to exit): ").strip()
    if not choice:
        print("No file selected. Exiting.")
        return

    try:
        index = int(choice) - 1
        if index < 0 or index >= len(LOG_FILE_NAMES):
            raise IndexError
        summarize_log(LOG_FILE_NAMES[index])
    except (ValueError, IndexError):
        print("Invalid selection. Exiting.")

if __name__ == "__main__":
    main()
