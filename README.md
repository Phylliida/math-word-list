# math-word-list

Hunspell-compatible dictionaries of mathematics terminology and names, intended as supplementary dictionaries for spellcheckers. Built from the [ALCO](https://www.math.uni-bonn.de/ag/algkomb/) (Algebraic Combinatorics) research paper corpus.

## Dictionaries

| Dictionary | Description | Words |
|---|---|---|
| `math.aff` / `math.dic` | General mathematics terms and names | 723 |
| `math_terms.aff` / `math_terms.dic` | Specialist terms common in combinatorics papers | 160 |
| `math_names.aff` / `math_names.dic` | Mathematician surnames and proper nouns | 1270 |

All three share the same `.aff` suffix rules (plurals, adverbs, Latin/Greek inflections, etc.) and use UTF-8 encoding.

## Usage

Copy the `.aff` and `.dic` pairs into your hunspell dictionary directory and add them as extra dictionaries in your editor or spellchecker. For example, in LibreOffice: Tools > Options > Language Settings > Writing Aids > Edit > Add.

## Building

- `collect_words.py` / `collect_words_alco.py` — extract candidate words from source papers
- `clean.py` — normalize and filter the raw word list
- `find_rare_words.py` — split terms by frequency into common and rare sets
- `make_hunspell.py` — generate `.aff` / `.dic` files
