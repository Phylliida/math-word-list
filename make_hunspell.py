#!/usr/bin/env python3
"""Generate hunspell .aff and .dic files from wordsfiltered.txt with affix tags."""

with open("wordsfiltered.txt", encoding="utf-8") as f:
    words = [w.strip() for w in f if w.strip()]

# Detect which words are already plural forms of other words in the list
word_set = {w.lower() for w in words}

def is_proper_noun(w):
    return w[0].isupper() and not w.isupper()

def is_acronym(w):
    return w.isupper() and len(w) >= 2

def is_already_plural(w):
    lo = w.lower()
    # word ends in s and the singular form exists
    if lo.endswith("ies") and (lo[:-3] + "y") in word_set:
        return True
    if lo.endswith("ces") and (lo[:-1]) in word_set:
        return True
    if lo.endswith("s") and not lo.endswith("ss") and lo[:-1] in word_set:
        return True
    return False

# Suffixes that suggest the word is an adjective
adj_endings = (
    "ive", "ble", "ous", "ic", "al", "ant", "ent", "ary",
    "wise", "free", "less", "like", "damped",
)
# Suffixes that suggest the word is a noun
noun_endings = (
    "tion", "sion", "ment", "ness", "ity", "ance", "ence",
    "ism", "ist", "oid", "oid", "ope", "ule", "rix",
    "ion", "oid", "raph", "dron", "tum", "mum",
    "oid", "ant", "ent", "ure",
)
# Suffixes that suggest verb
verb_endings = ("ize", "ise", "ate", "ify")

def get_flags(w):
    flags = set()
    lo = w.lower()

    # Skip if already a plural/derived form
    if is_already_plural(w):
        return flags

    # Acronyms: just add S for plural (RSA → RSAs)
    if is_acronym(w):
        flags.add("S")
        return flags

    # Proper nouns (mathematician names): add P for possessive-like ('s)
    # Actually hunspell doesn't do possessives well, so just S for plural usage
    if is_proper_noun(w):
        flags.add("S")
        return flags

    # Common words - determine type and add flags

    # Nouns and general words: add plural
    if lo.endswith("y") and len(lo) > 2 and lo[-2] not in "aeiou":
        flags.add("Y")  # -y → -ies
    elif lo.endswith(("s", "x", "z", "sh", "ch")):
        flags.add("E")  # → -es
    elif lo.endswith(("um",)):
        pass  # irregular plural (e.g. extremum → extrema), skip
    elif not lo.endswith(("ness", "ity", "ly")):
        flags.add("S")  # regular → -s
    else:
        flags.add("S")

    # Adjectives: add -ly
    if any(lo.endswith(e) for e in ("ive", "ble", "ous", "ic", "al", "ant", "ent", "wise")):
        if not lo.endswith("ly"):
            flags.add("L")

    # Verbs: add -ed, -ing, -s
    if any(lo.endswith(e) for e in verb_endings):
        flags.add("D")  # -ed / -d
        flags.add("G")  # -ing

    return flags

# Build tagged word list
tagged = []
for w in words:
    if is_already_plural(w):
        continue  # skip explicit plurals, affix rules will generate them
    flags = get_flags(w)
    if flags:
        tagged.append(f"{w}/{''.join(sorted(flags))}")
    else:
        tagged.append(w)

# Write .aff
aff_content = """SET UTF-8

# S: regular plural, add -s
SFX S Y 1
SFX S 0 s .

# E: plural for words ending in s/x/z/sh/ch, add -es
SFX E Y 1
SFX E 0 es .

# Y: plural for words ending in consonant+y, -y → -ies
SFX Y Y 1
SFX Y y ies [^aeiou]y

# L: adverb form, add -ly
SFX L Y 2
SFX L 0 ly [^l]
SFX L 0 ly ll

# D: past tense
SFX D Y 3
SFX D e ed [^aeiou]e
SFX D 0 d e
SFX D 0 ed [^e]

# G: gerund, add -ing
SFX G Y 3
SFX G e ing [^aeiou]e
SFX G 0 ing [^e]
SFX G 0 ing e
"""

with open("math.aff", "w", encoding="utf-8") as f:
    f.write(aff_content)

with open("math.dic", "w", encoding="utf-8") as f:
    f.write(f"{len(tagged)}\n")
    f.write("\n".join(tagged) + "\n")

print(f"Wrote {len(tagged)} entries to math.dic (removed {len(words) - len(tagged)} explicit plurals)")
