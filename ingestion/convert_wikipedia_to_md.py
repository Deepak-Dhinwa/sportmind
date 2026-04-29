"""
Convert Wikipedia .txt files → .md files in knowledge_base/wikipedia/
so the existing load_weaviate.py can index them without changes.

Detection heuristic for section headers:
  - Line is not empty
  - Line is short (< 80 chars)
  - Does not end with sentence punctuation (. ! ?)
  - Preceded by an empty line (or start of file)
  - Not the # title line

Run: python -m ingestion.convert_wikipedia_to_md
"""
import re
from pathlib import Path

SRC_DIRS = {
    Path("knowledge_base/wikipedia/players"): Path("knowledge_base/wikipedia/players"),
    Path("knowledge_base/wikipedia/teams"):   Path("knowledge_base/wikipedia/teams"),
}


def _is_section_header(line: str, prev_blank: bool) -> bool:
    s = line.strip()
    if not s:
        return False
    if not prev_blank:
        return False                        # must follow a blank line
    if s.startswith("#"):
        return False                        # already a markdown heading
    if len(s) > 80:
        return False                        # too long to be a heading
    if s[-1] in ".!?,;:":
        return False                        # ends with punctuation → sentence
    if re.search(r"\d{4}", s) and len(s) > 30:
        return False                        # long lines with years are likely sentences
    # Must look like a title: mostly title-case or ALL CAPS words
    words = s.split()
    if len(words) == 0:
        return False
    return True


# Sections to drop entirely — no useful content for RAG
_JUNK_SECTIONS = {
    "see also", "references", "external links", "notes", "bibliography",
    "further reading", "filmography", "discography", "videography",
    "television", "media", "personal life and philanthropy",
    "business ventures", "other ventures", "endorsements",
    "off the court", "off-court", "legal issues", "controversies",
    "social media", "charity", "foundation",
}


def convert_txt_to_md(txt_path: Path) -> str:
    lines = txt_path.read_text(encoding="utf-8").split("\n")
    out   = []
    prev_blank  = True
    skip_section = False   # True when inside a junk section

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Keep existing # title as-is
        if stripped.startswith("# ") and i < 3:
            out.append(line)
            prev_blank = False
            skip_section = False
            continue

        # Blank line
        if not stripped:
            out.append("")
            prev_blank = True
            continue

        # Section header detection
        if _is_section_header(stripped, prev_blank):
            # Check if this section should be skipped
            if stripped.lower() in _JUNK_SECTIONS:
                skip_section = True
                prev_blank = False
                continue   # don't emit the header
            else:
                skip_section = False
                out.append(f"## {stripped}")
                prev_blank = False
                continue

        # Skip content inside junk sections
        if skip_section:
            prev_blank = False
            continue

        out.append(line)
        prev_blank = False

    return "\n".join(out)


def run():
    total = 0
    for src_dir, out_dir in SRC_DIRS.items():
        out_dir.mkdir(parents=True, exist_ok=True)
        txt_files = list(src_dir.glob("*.txt"))
        print(f"\n{src_dir}: {len(txt_files)} files")
        for txt in txt_files:
            md_path = out_dir / (txt.stem + ".md")
            md_text = convert_txt_to_md(txt)

            # Quick quality check: count ## headers found
            headers = [l for l in md_text.split("\n") if l.startswith("## ")]
            words   = len(md_text.split())

            md_path.write_text(md_text, encoding="utf-8")
            print(f"  {txt.stem}: {words:,} words, {len(headers)} sections -> {md_path.name}")
            total += 1

    print(f"\nConverted {total} files total.")
    print("Now run: python -m ingestion.load_weaviate")


if __name__ == "__main__":
    run()
