#!/usr/bin/env bash
#
# scripts/reclean_all.sh
# Bulk run stage3_clean_names.py on every raw-merged transcript.

echo "🔄 Re-cleaning all raw transcripts…"

find campaigns -name '*_merged_raw_v*.md' -print0 \
  | xargs -0 -n1 -P4 \
      python scripts/stage3_clean_names.py {} handle_map.csv realname_map.csv

echo "✅ Done re-cleaning."
