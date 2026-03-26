#!/usr/bin/env python3
"""
Find rare words from words_terms.txt by counting how many ALCO papers contain each word.
Outputs words appearing in at most N papers (default: 4).

Memory-efficient: processes one paper at a time, keeping only a counter dict in memory.
"""

import argparse
import re
import sys
from pathlib import Path
from collections import defaultdict


def deduplicate_papers(papers_dir):
    """Find ALCO_*.tex files, deduplicated by paper identifier.

    When multiple copies exist (e.g. in subdirectories), prefer the
    shallowest path (closest to papers_dir root).
    """
    all_files = sorted(Path(papers_dir).rglob("ALCO_*.tex"))

    # Group by paper identifier (e.g. ALCO_Iwao_829)
    by_id = defaultdict(list)
    for f in all_files:
        stem = f.stem
        by_id[stem].append(f)

    # Pick the shallowest path for each paper
    selected = []
    for stem, paths in sorted(by_id.items()):
        shortest = min(paths, key=lambda p: len(p.parts))
        selected.append(shortest)

    return selected


def extract_words_from_tex(text):
    """Extract a set of lowercase words from raw tex, splitting on non-alpha."""
    # Simple tokenization: split on anything that isn't a letter
    return set(re.findall(r'[a-zA-Zéèêëüöäàâôûîïç]+', text))


def main():
    ap = argparse.ArgumentParser(description="Find rare words from words_terms.txt")
    ap.add_argument("papers_dir", help="Directory containing papers")
    ap.add_argument("--terms", default="words_terms.txt", help="Terms file to check")
    ap.add_argument("--max-papers", type=int, default=4,
                    help="Maximum number of papers for a word to be considered rare (default: 4)")
    ap.add_argument("-o", "--output", default="words_terms_rare.txt",
                    help="Output file for rare words")
    args = ap.parse_args()

    # Load terms
    terms_path = Path(args.terms)
    terms = [line.strip() for line in terms_path.read_text().splitlines() if line.strip()]
    print(f"Loaded {len(terms)} terms from {terms_path}")

    # Build lookup: for case-insensitive matching, map lowercase -> original term(s)
    terms_lower = {t.lower(): t for t in terms}

    # Find and deduplicate papers
    papers = deduplicate_papers(args.papers_dir)
    print(f"Found {len(papers)} unique papers")

    # Count: for each term, how many papers contain it
    paper_count = defaultdict(int)

    for i, paper_path in enumerate(papers):
        try:
            text = paper_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  Warning: could not read {paper_path}: {e}", file=sys.stderr)
            continue

        # Get all words in this paper (case-preserved set + lowercase set)
        paper_words_raw = extract_words_from_tex(text)
        paper_words_lower = {w.lower() for w in paper_words_raw}

        # Check which terms appear in this paper
        for term_lower in terms_lower:
            if term_lower in paper_words_lower:
                paper_count[term_lower] += 1

        # text is freed here (goes out of scope each iteration)
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(papers)} papers...")

    print(f"Processed all {len(papers)} papers.")

    # Collect rare words
    rare_words = []
    for term in terms:
        count = paper_count.get(term.lower(), 0)
        if count <= args.max_papers:
            rare_words.append((term, count))

    print(f"Found {len(rare_words)} words appearing in <= {args.max_papers} papers")

    # Write output (word + tab + count)
    with open(args.output, "w", encoding="utf-8") as f:
        for word, count in rare_words:
            f.write(f"{word}\t{count}\n")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
