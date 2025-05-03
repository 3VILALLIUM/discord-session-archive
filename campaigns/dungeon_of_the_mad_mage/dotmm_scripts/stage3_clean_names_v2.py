import re
import sys
import csv
import tempfile
import argparse
from pathlib import Path
from typing import Dict

def load_map(csv_file: Path) -> Dict[str, str]:
    """Load a semicolon-delimited CSV mapping into a dict."""
    mapping: Dict[str, str] = {}
    with csv_file.open(encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=';')
        for row in reader:
            if len(row) == 2:
                key, val = row[0].strip(), row[1].strip()
                mapping[key] = val
    return mapping


def build_realname_pattern(realname_map: Dict[str, str]) -> re.Pattern:
    """Build a regex pattern to match keys for real name replacements."""
    escaped = [re.escape(k) for k in realname_map.keys()]
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    return re.compile(pattern)


def process_file(input_path: Path, discord_map: Dict[str, str], realname_map: Dict[str, str], output_dir: Path, force: bool) -> Path:
    """Read the merged transcript, apply mappings, and write a cleaned file."""
    # Determine output directory
    if output_dir:
        out_dir = output_dir
    else:
        parent = input_path.parent
        if parent.name == '_raw':
            out_dir = parent.parent
        else:
            out_dir = parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Construct output path
    cleaned_name = input_path.stem + '_cleaned.md'
    out_path = out_dir / cleaned_name

    # Check overwrite guard
    if out_path.exists() and not force:
        print(f"Error: '{out_path}' already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    # Prepare regex patterns
    mention_pattern = re.compile(r"@\w+")
    realname_pattern = build_realname_pattern(realname_map)

    # Atomic write to temp file
    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(out_dir), encoding='utf-8') as tmpf:
        with input_path.open(encoding='utf-8') as infile:
            for line in infile:
                # Replace Discord handles
                line = mention_pattern.sub(lambda m: discord_map.get(m.group(0), m.group(0)), line)
                # Replace real names
                line = realname_pattern.sub(lambda m: realname_map.get(m.group(0), m.group(0)), line)
                tmpf.write(line)
        tmp_name = tmpf.name

    # Rename temp file to final
    Path(tmp_name).replace(out_path)
    print(f"Cleaned transcript written to '{out_path}'")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Clean a merged transcript by replacing handles and real names."
    )
    parser.add_argument('input_file', type=Path, help='Path to merged transcript .md file')
    parser.add_argument('handle_map', type=Path, help='CSV file for Discord handle mappings')
    parser.add_argument('real_map', type=Path, help='CSV file for real name mappings')
    parser.add_argument('--output-dir', type=Path, default=None,
                        help='Directory to write cleaned file (default: same folder, or parent of _raw)')
    parser.add_argument('--force', action='store_true', help='Overwrite existing cleaned file')
    args = parser.parse_args()

    # Validate inputs
    if not args.input_file.exists():
        print(f"Error: input file '{args.input_file}' not found.", file=sys.stderr)
        sys.exit(1)
    for csv_file in (args.handle_map, args.real_map):
        if not csv_file.exists():
            print(f"Error: CSV mapping file '{csv_file}' not found.", file=sys.stderr)
            sys.exit(1)

    discord_map = load_map(args.handle_map)
    realname_map = load_map(args.real_map)
    process_file(args.input_file, discord_map, realname_map, args.output_dir, args.force)

if __name__ == '__main__':
    main()
