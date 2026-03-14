import re
import subprocess

with open("dictionary.txt", encoding="utf-8") as f:
    text = f.read()

# Split on whitespace and punctuation, strip edges
# Dedup by lowercase but preserve original capitalization
seen = {}
for token in text.split():
    for part in re.split(r"[''`\u2019_!(,]", token):
        cleaned = re.sub(r"^\W+|\W+$", "", part)
        if cleaned and not cleaned[0].isdigit():
            key = cleaned.lower()
            if key not in seen or cleaned.islower():
                seen[key] = cleaned

words = set(seen.values())

# Use hunspell to find misspelled words (i.e. not in en_US dictionary)
hunspell = "/usr/local/Cellar/hunspell/1.7.2/bin/hunspell"
result = subprocess.run(
    [hunspell, "-d", "./en_US", "-l"],
    input="\n".join(words),
    capture_output=True, text=True,
)
math_words = set(result.stdout.strip().split("\n"))

print(f"Total unique words: {len(words)}")
print(f"Words not in en_US: {len(math_words)}")

with open("words.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(sorted(math_words, key=str.lower)) + "\n")

print(f"Wrote {len(math_words)} words to words.txt")
