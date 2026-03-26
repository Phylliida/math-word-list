#!/usr/bin/env python3
"""
Extract a spelling word list from corrected LaTeX math papers.

Usage:
    python3 collect_words.py papers/*.tex
    python3 collect_words.py papers/           # processes all .tex files recursively

Preprocessing: uses pylatexenc to parse LaTeX and extract only prose text,
skipping math mode, tikz pictures, comments, preamble commands, reference
keys, etc.  The cleaned text is then tokenized and filtered through hunspell
to find words not in the standard en_US dictionary (i.e. math-specific terms).

Output:
    words_raw.txt        — all unique words extracted from the papers
    words_notenglish.txt — words not in en_US (candidates for math dictionary)
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from pylatexenc.latex2text import LatexNodes2Text
from pylatexenc.latexwalker import (
    LatexWalker,
    LatexCharsNode,
    LatexCommentNode,
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexMathNode,
    LatexSpecialsNode,
    get_default_latex_context_db as get_walker_db,
)
from pylatexenc.macrospec import MacroSpec

# ---------------------------------------------------------------------------
# pylatexenc setup
# ---------------------------------------------------------------------------

# LatexNodes2Text handles accent commands (\'{e} -> é, \"{u} -> ü, etc.)
_L2T = LatexNodes2Text()

# Tell the parser about macros it doesn't know so their {args} are consumed
# rather than treated as body text.
_CUSTOM_MACRO_ARGSPECS = {
    # Package setup / visual
    "ytableausetup": "{", "ydiagram": "{", "ytableaushort": "{",
    "scalebox": "{", "resizebox": "{{",
    "hypersetup": "{", "definecolor": "{{{",
    "tikzset": "{", "pgfplotsset": "{", "usetikzlibrary": "{",
    # cedram metadata
    "subjclass": "[{", "keywords": "{", "DOI": "{",
    "datereceived": "{", "daterevised": "{", "dateaccepted": "{",
    "firstname": "{", "lastname": "{", "longthanks": "[{",
    "curraddr": "{",
    # Author / contact (appear in body for cedram/amsart)
    "email": "{", "urladdr": "{", "address": "{", "thanks": "{",
    "author": "{",
    # ct.sty metadata
    "affil": "[{", "MSC": "{", "specs": "{", "dateline": "{",
    # Custom cross-reference macros
    "MyCref": "{", "crefname": "{{{", "Crefname": "{{{",
    # Misc that appear in paper bodies
    "defn": "{", "looseness": "",
    "goodbreak": "", "smallbreak": "", "medbreak": "", "bigbreak": "",
}


def _get_walker_context():
    """Build a parser context that knows about our custom macros."""
    db = get_walker_db()
    db.add_context_category(
        "custom-parsing",
        prepend=True,
        macros=[MacroSpec(m, args) for m, args in _CUSTOM_MACRO_ARGSPECS.items()],
    )
    return db


_WALKER_DB = _get_walker_context()

# ---------------------------------------------------------------------------
# Configuration: what to skip and what to keep
# ---------------------------------------------------------------------------

# Environments whose body is discarded entirely.
SKIP_ENVIRONMENTS = {
    # TikZ / diagrams
    "tikzpicture", "tikzcd", "pgfpicture",
    # Math display
    "equation", "equation*", "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*",
    "eqnarray", "eqnarray*", "flalign", "flalign*",
    "math", "displaymath",
    # Matrix / array
    "matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix",
    "smallmatrix", "array", "cases",
    # Tables (mostly numeric / symbolic content)
    "tabular", "tabular*", "longtable",
    # Verbatim
    "verbatim", "verbatim*", "lstlisting", "minted",
    # Young tableaux
    "ytableau",
}

# Macros whose arguments are not prose and should be discarded.
SKIP_MACROS = {
    # References / citations
    "cite", "citet", "citep", "citealt", "citealp",
    "citeauthor", "citeyear", "citeurl", "nocite", "bibcite",
    "label", "ref", "eqref", "cref", "Cref", "autoref",
    "pageref", "nameref", "hyperref",
    "crefname", "Crefname", "MyCref",
    # Preamble-style commands that can appear in the body
    "usepackage", "RequirePackage",
    "newcommand", "renewcommand", "providecommand",
    "newenvironment", "renewenvironment",
    "DeclareMathOperator", "DeclareRobustCommand",
    "newtheorem", "theoremstyle", "numberwithin",
    "setcounter", "setlength", "addtolength",
    "definecolor", "tikzset", "pgfplotsset", "usetikzlibrary",
    # Layout / visual
    "hypersetup", "geometry", "pagestyle", "thispagestyle",
    "includegraphics", "graphicspath",
    "ytableausetup", "ytableaushort", "ydiagram",
    "scalebox", "resizebox", "rotatebox",
    "hspace", "vspace", "hfill", "vfill",
    "phantom", "hphantom", "vphantom",
    "color", "textcolor", "colorbox",
    "rule", "centering", "raggedright", "raggedleft",
    # Bibliography
    "bibliographystyle", "bibliography", "addbibresource",
    # Links
    "url", "href", "nolinkurl",
    # Internal
    "input", "include", "maketitle", "tableofcontents",
    # cedram metadata
    "subjclass", "keywords", "DOI",
    "datereceived", "daterevised", "dateaccepted",
    "firstname", "lastname", "longthanks",
    "email", "urladdr", "address", "curraddr", "thanks",
    # ct.sty metadata
    "affil", "MSC", "specs", "dateline",
    # Misc non-prose
    "defn", "looseness", "goodbreak", "smallbreak", "medbreak", "bigbreak",
}

# Macros that contain prose inside math mode (\text{words here}).
_TEXT_IN_MATH = {
    "text", "textrm", "textit", "textbf", "textsc", "textsf",
    "mbox", "hbox", "intertext",
}

# LaTeX accent macros — handled via pylatexenc's latex2text.
_ACCENT_MACROS = {
    "'", '"', "`", "^", "~", "=", ".",
    "u", "v", "H", "c", "d", "b", "t", "k",
}


# ---------------------------------------------------------------------------
# Preprocessing: strip environments the parser can't handle well
# ---------------------------------------------------------------------------

_STRIP_ENV_RE = re.compile(
    r"\\begin\{(?:tikzpicture|tikzcd|pgfpicture|lstlisting|minted|verbatim)\}"
    r".*?"
    r"\\end\{(?:tikzpicture|tikzcd|pgfpicture|lstlisting|minted|verbatim)\}",
    re.DOTALL,
)


def _preprocess(tex):
    """Regex-strip environments whose bodies confuse the LaTeX parser."""
    return _STRIP_ENV_RE.sub("", tex)


# ---------------------------------------------------------------------------
# AST walker
# ---------------------------------------------------------------------------

def _extract(nodes):
    """Walk AST nodes and return concatenated prose text.

    Uses direct string concatenation (no inserted spaces) so that words
    spanning multiple nodes — e.g. Sch{\\\"u}tzenberger — stay intact.
    Whitespace comes from the LatexCharsNodes themselves.
    """
    parts = []
    if not nodes:
        return ""
    for node in nodes:
        if isinstance(node, LatexCharsNode):
            parts.append(node.chars)

        elif isinstance(node, LatexCommentNode):
            pass

        elif isinstance(node, LatexMathNode):
            # Only harvest \\text{} and friends from inside math.
            math_parts = []
            _extract_math_text(node.nodelist, math_parts)
            if math_parts:
                parts.append(" " + " ".join(math_parts) + " ")

        elif isinstance(node, LatexEnvironmentNode):
            if node.environmentname in SKIP_ENVIRONMENTS:
                pass
            else:
                # Skip the environment's optional/required arguments (e.g. [htb])
                # but traverse the body — this keeps captions, theorem text, etc.
                parts.append(_extract(node.nodelist))

        elif isinstance(node, LatexMacroNode):
            if node.macroname in SKIP_MACROS:
                pass
            elif node.macroname in _ACCENT_MACROS:
                # Delegate to pylatexenc for proper unicode conversion.
                try:
                    parts.append(_L2T.node_to_text(node))
                except Exception:
                    pass
            elif node.macroname == "\\":
                parts.append(" ")
            else:
                # For everything else (\\emph, \\section, etc.) extract args.
                # Insert a space before to prevent word concatenation
                # (e.g. "truncation\footnote{The..." -> "truncation The...")
                if node.nodeargd and node.nodeargd.argnlist:
                    for arg in node.nodeargd.argnlist:
                        if arg is not None:
                            t = _arg_text(arg)
                            if t:
                                parts.append(" " + t)

        elif isinstance(node, LatexGroupNode):
            parts.append(_extract(node.nodelist))

        elif isinstance(node, LatexSpecialsNode):
            if hasattr(node, "specials_chars"):
                sc = node.specials_chars
                if sc in ("~", "--", "---"):
                    parts.append(" ")

    return "".join(parts)


def _arg_text(arg):
    """Extract text from a single macro/environment argument."""
    if hasattr(arg, "nodelist") and arg.nodelist is not None:
        return _extract(arg.nodelist)
    if isinstance(arg, LatexCharsNode):
        return arg.chars
    return ""


def _extract_math_text(nodes, parts):
    """Inside math, recurse only into \\text{}/\\mbox{}/etc."""
    if not nodes:
        return
    for child in nodes:
        if isinstance(child, LatexMacroNode) and child.macroname in _TEXT_IN_MATH:
            if child.nodeargd and child.nodeargd.argnlist:
                for arg in child.nodeargd.argnlist:
                    if arg is not None:
                        parts.append(_arg_text(arg))
        elif isinstance(child, LatexGroupNode):
            _extract_math_text(child.nodelist, parts)
        elif isinstance(child, LatexEnvironmentNode):
            _extract_math_text(child.nodelist, parts)


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------

def _extract_preamble_text(preamble):
    """Pull title and abstract from the preamble (before \\begin{document})."""
    parts = []

    # Title
    m = re.search(r"\\title\s*(?:\[[^\]]*\])?\s*\{", preamble)
    if m:
        title = _balanced_braces(preamble, m.end() - 1)
        if title:
            try:
                w = LatexWalker(title, latex_context=_WALKER_DB, tolerant_parsing=True)
                nodes, _, _ = w.get_latex_nodes()
                parts.append(_extract(nodes))
            except Exception:
                parts.append(_rough_detex(title))

    # Abstract
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", preamble, re.DOTALL)
    if m:
        try:
            w = LatexWalker(m.group(1), latex_context=_WALKER_DB, tolerant_parsing=True)
            nodes, _, _ = w.get_latex_nodes()
            parts.append(_extract(nodes))
        except Exception:
            parts.append(_rough_detex(m.group(1)))

    return " ".join(parts)


def _balanced_braces(s, start):
    """Return content inside balanced braces starting at *start*."""
    if start >= len(s) or s[start] != "{":
        return ""
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1 : i]
    return s[start + 1 :]


def _rough_detex(s):
    """Fallback: crudely strip LaTeX commands."""
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", " ", s)
    s = re.sub(r"[{}$\\]", " ", s)
    return s


def process_tex_file(filepath):
    """Parse a .tex file and return extracted prose text."""
    with open(filepath, encoding="utf-8", errors="replace") as f:
        tex = f.read()

    # Split at \begin{document}
    doc_match = re.search(r"\\begin\{document\}", tex)
    if doc_match:
        preamble = tex[: doc_match.start()]
        body = tex[doc_match.end() :]
    else:
        preamble, body = "", tex

    # Strip \end{document} and everything after (bibliography, etc.)
    end_match = re.search(r"\\end\{document\}", body)
    if end_match:
        body = body[: end_match.start()]

    preamble_text = _extract_preamble_text(preamble)
    body = _preprocess(body)

    try:
        w = LatexWalker(body, latex_context=_WALKER_DB, tolerant_parsing=True)
        nodes, _, _ = w.get_latex_nodes()
        body_text = _extract(nodes)
    except Exception as e:
        print(f"  Warning: failed to parse {filepath}: {e}", file=sys.stderr)
        body_text = ""

    return preamble_text + "\n" + body_text


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

def tokenize(text):
    """Split extracted text into word tokens."""
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    # Convert em/en-dashes to spaces (Bott--Samelson -> Bott Samelson)
    text = re.sub(r"--+", " ", text)
    # Rejoin line-break hyphenation (e.g. "Grass-\n mannian" -> "Grassmannian")
    text = re.sub(r"-\s+", "", text)

    words = set()
    for token in text.split():
        # Split on punctuation (keep hyphens inside words)
        for part in re.split(
            r"[''`\u2018\u2019\u201C\u201D\"_!?,;:().\[\]{}|/<>@#$%^&*=+~]",
            token,
        ):
            cleaned = part.strip("-")
            if not cleaned:
                continue
            # Skip purely numeric tokens
            if re.match(r"^[\d.]+$", cleaned):
                continue
            # Skip single-char fragments (except a, I)
            if len(cleaned) <= 1 and cleaned.lower() not in ("a", "i"):
                continue
            # Skip tokens containing digits (MSC codes, grant numbers, etc.)
            if re.search(r"\d", cleaned):
                continue
            # Skip likely URL/email fragments
            if re.match(r"^(https?|www|com|org|edu|net|io|ca)$", cleaned, re.I):
                continue
            words.add(cleaned)
    return words


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_tex_files(paths):
    """Resolve CLI paths to a list of .tex files."""
    files = []
    for p in paths:
        p = Path(p)
        if p.is_file() and p.suffix == ".tex":
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.rglob("ALCO_*.tex"))) #specialized for alco dataset.
        else:
            print(f"Warning: skipping {p}", file=sys.stderr)
    return files


def main():
    ap = argparse.ArgumentParser(
        description="Extract math spelling words from LaTeX papers.",
    )
    ap.add_argument("paths", nargs="+", help="LaTeX files or directories to process")
    ap.add_argument("--hunspell", default="hunspell", help="Path to hunspell binary")
    ap.add_argument("--dict", default="en_US", help="Hunspell dictionary (default: en_US)")
    ap.add_argument("-o", "--output", default="words_notenglish.txt",
                    help="Output file for non-English words")
    ap.add_argument("--raw-output", default="words_raw.txt",
                    help="Output file for all extracted words")
    args = ap.parse_args()

    tex_files = find_tex_files(args.paths)
    if not tex_files:
        print("No .tex files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(tex_files)} file(s)...")

    all_words = set()
    for fpath in tex_files:
        print(f"  {fpath}")
        text = process_tex_file(fpath)
        all_words |= tokenize(text)

    print(f"Total unique words extracted: {len(all_words)}")

    with open(args.raw_output, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(all_words, key=str.lower)) + "\n")
    print(f"Wrote {len(all_words)} words to {args.raw_output}")

    # Filter through hunspell
    try:
        result = subprocess.run(
            [args.hunspell, "-d", args.dict, "-l"],
            input="\n".join(all_words),
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"hunspell error: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        math_words = set(result.stdout.strip().split("\n")) - {""}
        print(f"Words not in {args.dict}: {len(math_words)}")

        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(math_words, key=str.lower)) + "\n")
        print(f"Wrote {len(math_words)} words to {args.output}")

    except FileNotFoundError:
        print(
            f"hunspell not found at '{args.hunspell}'. "
            f"Raw words written to {args.raw_output}; skipping hunspell filtering.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
