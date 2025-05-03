import re
import sys
import csv
from pathlib import Path


def load_map(csv_file: Path) -> dict[str, str]:
    """Load a semicolon-delimited CSV mapping into a dict."""
    mapping: dict[str, str] = {}
    with csv_file.open(encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        for row in reader:
            if len(row) == 2:
                key, val = row[0].strip(), row[1].strip()
                mapping[key] = val
    return mapping


def build_realname_pattern(realname_map: dict[str, str]) -> re.Pattern:
    """Compile a regex pattern to match any real name with word boundaries."""
    if not realname_map:
        return re.compile(r"$^")  # never matches
    escaped = (re.escape(name) for name in realname_map.keys())
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    return re.compile(pattern)


def clean_line(
    line: str,
    mention_pattern: re.Pattern,
    discord_map: dict[str, str],
    realname_pattern: re.Pattern,
    realname_map: dict[str, str]
) -> str:
    """Replace Discord handles and real names in a single line."""
    # Replace Discord handles (@handle)
    line = mention_pattern.sub(lambda m: discord_map.get(m.group(), m.group()), line)
    # Replace real names
    line = realname_pattern.sub(lambda m: realname_map.get(m.group(), m.group()), line)
    return line


# Pre-compile a pattern to find speaker tags like [0.00s 1-mathyieu_0]
speaker_pattern = re.compile(r"(\[\s*\d+\.\d+s\s+)([\w-]+)(\s*\])")

def replace_speaker_tags(line: str, discord_map: dict[str, str]) -> str:
    """Swap out numeric-prefix speaker tags for their character names."""
    def sub(m: re.Match) -> str:
        prefix, tag, suffix = m.groups()
        # extract handle from tag: e.g. 1-mathyieu_0 -> @mathyieu
        try:
            _, rest = tag.split('-', 1)
            handle = '@' + rest.rsplit('_', 1)[0]
        except ValueError:
            return m.group(0)
        name = discord_map.get(handle, tag)
        return f"{prefix}{name}{suffix}"
    return speaker_pattern.sub(sub, line)


def process_file(
    input_path: Path,
    discord_map: dict[str, str],
    realname_map: dict[str, str]
) -> Path:
    """Read input, apply replacements, and write to output .md file."""
    mention_pattern = re.compile(r"@\w+")
    realname_pattern = build_realname_pattern(realname_map)

    out_path = input_path.with_name(input_path.stem + "_cleaned.md")
    with input_path.open(encoding='utf-8') as infile, out_path.open('w', encoding='utf-8') as outfile:
        for line in infile:
            cleaned = clean_line(
                line.rstrip('\n'),
                mention_pattern,
                discord_map,
                realname_pattern,
                realname_map
            )
            cleaned = replace_speaker_tags(cleaned, discord_map)
            outfile.write(cleaned + '\n')

    print(f"✓ Cleaned transcript written to {out_path}")
    return out_path


def main() -> None:
    if len(sys.argv) < 4:
        print(
            "Usage: python stage3_clean_names.py <input.md> <handle_map.csv> <realname_map.csv>",
            file=sys.stderr
        )
        sys.exit(1)

    input_file = Path(sys.argv[1])
    handle_map = Path(sys.argv[2])
    real_map = Path(sys.argv[3])

    discord_map = load_map(handle_map)
    realname_map = load_map(real_map)
    process_file(input_file, discord_map, realname_map)


if __name__ == "__main__":
    main()
