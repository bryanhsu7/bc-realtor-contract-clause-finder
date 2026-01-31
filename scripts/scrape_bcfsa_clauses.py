"""Script to scrape BCFSA clauses and save to knowledge base for the Realtor Clause Assistant."""
import sys
import re
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple

# Add parent directory to path so we can run from project root or scripts/
_script_dir = Path(__file__).resolve().parent
_root = _script_dir.parent
sys.path.insert(0, str(_root))

BCFSA_CLauses_URL = "https://www.bcfsa.ca/industry-resources/real-estate-professional-resources/knowledge-base/clauses/clauses"
CLAUSE_DELIMITER = "\n---CLAUSE---\n"


def clean_text(text: str) -> str:
    """Normalize whitespace and strip."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_clauses_from_html(html: str) -> List[Dict[str, str]]:
    """
    Parse BCFSA clauses page HTML into a list of clause records.
    Each record has: section, clause_name, body, considerations.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Find main content: BCFSA often uses main, article, or content divs
    main = soup.find("main") or soup.find("article")
    if not main:
        main = soup.find("div", id=re.compile(r"content|main", re.I))
    if not main:
        main = soup.find("body")

    if not main:
        return []

    # Strip script/style/nav
    for tag in main.find_all(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # Get all headings and following content by walking the tree
    clauses: List[Dict[str, str]] = []
    current_section = ""
    current_clause_name = ""
    current_body: List[str] = []
    current_considerations: List[str] = []
    in_considerations = False

    # Use a text-based parse on the flattened structure: many CMS outputs
    # produce section titles and clause titles as headings. We'll get all
    # elements in order and treat h2 as section, h3/h4 as clause title.
    for elem in main.find_all(["h2", "h3", "h4", "p", "div", "li"]):
        name = elem.name
        text = elem.get_text(separator=" ", strip=True)
        if not text or len(text) > 2000:
            continue

        # Section heading (usually h2)
        if name == "h2":
            # Flush previous clause if any
            if current_clause_name or current_section:
                body_str = "\n".join(current_body).strip()
                consid_str = "\n".join(current_considerations).strip()
                if body_str or current_clause_name:
                    clauses.append({
                        "section": current_section or "General",
                        "clause_name": current_clause_name or current_section,
                        "body": body_str,
                        "considerations": consid_str,
                    })
            current_section = clean_text(re.sub(r"\[.*?\]", "", text))
            current_clause_name = ""
            current_body = []
            current_considerations = []
            in_considerations = False
            continue

        # Clause heading (h3 or h4, or list item that looks like "### Name")
        if name in ("h3", "h4") or (name == "li" and text.startswith("### ")):
            if current_clause_name or current_body:
                body_str = "\n".join(current_body).strip()
                consid_str = "\n".join(current_considerations).strip()
                if body_str or current_clause_name:
                    clauses.append({
                        "section": current_section or "General",
                        "clause_name": current_clause_name or "Untitled",
                        "body": body_str,
                        "considerations": consid_str,
                    })
            raw = re.sub(r"\[.*?\]", "", text).strip()
            raw = re.sub(r"^\*?\s*#+\s*", "", raw)
            current_clause_name = clean_text(raw) if raw else "Untitled"
            current_body = []
            current_considerations = []
            in_considerations = False
            continue

        # Body or considerations
        low = text.lower()
        if "considerations" in low and len(text) < 100:
            in_considerations = True
            continue
        if in_considerations:
            current_considerations.append(text)
        else:
            current_body.append(text)

    # Flush last
    if current_clause_name or current_body:
        body_str = "\n".join(current_body).strip()
        consid_str = "\n".join(current_considerations).strip()
        clauses.append({
            "section": current_section or "General",
            "clause_name": current_clause_name or "Untitled",
            "body": body_str,
            "considerations": consid_str,
        })

    return clauses


def extract_clauses_from_text(full_text: str) -> List[Dict[str, str]]:
    """
    Fallback: parse when structure is "## Section" and "* ### Clause name" in plain text.
    """
    clauses: List[Dict[str, str]] = []
    current_section = ""
    blocks = re.split(r"\n##\s+", full_text)
    for block in blocks:
        if not block.strip():
            continue
        lines = block.split("\n")
        section_line = lines[0] if lines else ""
        section_name = clean_text(re.sub(r"\[.*?\]", "", section_line))
        if section_name:
            current_section = section_name
        # Split remainder by clause headings: * ### Name or ### Name
        rest = "\n".join(lines[1:])
        clause_parts = re.split(r"\n\*?\s*###\s+", rest)
        for i, part in enumerate(clause_parts):
            if not part.strip():
                continue
            lines_part = part.strip().split("\n")
            clause_name = clean_text(re.sub(r"\[.*?\]", "", lines_part[0])) if lines_part else "Untitled"
            body_lines = []
            consid_lines = []
            in_consid = False
            for line in lines_part[1:]:
                if re.match(r"^\s*\*\*Considerations\*\*\s*$", line, re.I):
                    in_consid = True
                    continue
                if in_consid:
                    consid_lines.append(line.strip())
                else:
                    body_lines.append(line.strip())
            body_str = "\n".join(body_lines).strip()
            consid_str = "\n".join(consid_lines).strip()
            clauses.append({
                "section": current_section or "General",
                "clause_name": clause_name or "Untitled",
                "body": body_str,
                "considerations": consid_str,
            })
    return clauses


def fetch_and_parse(url: str) -> List[Dict[str, str]]:
    """Fetch BCFSA page and return list of clause records."""
    print(f"Fetching {url} ...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    html = resp.text

    clauses = extract_clauses_from_html(html)
    if len(clauses) < 5:
        # Fallback: get full text and parse markdown-like structure
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        full_text = soup.get_text(separator="\n")
        clauses = extract_clauses_from_text(full_text)
    return clauses


def format_clause_block(c: Dict[str, str]) -> str:
    """Format one clause as a block for the knowledge base file."""
    parts = [
        f"Section: {c['section']}",
        f"Clause: {c['clause_name']}",
        "",
        c["body"] or "(No clause text)",
    ]
    if c.get("considerations"):
        parts.extend(["", "Considerations:", c["considerations"]])
    return "\n".join(parts)


def save_clauses(clauses: List[Dict[str, str]], output_path: Path) -> None:
    """Write clauses to a single file with ---CLAUSE--- delimiter."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "BCFSA Clauses for Contract of Purchase and Sale.\n"
        f"Source: {BCFSA_CLauses_URL}\n"
        "Content is for educational use only. Refer to bcfsa.ca for the latest version.\n"
    )
    blocks = [header.strip()]
    for c in clauses:
        blocks.append(format_clause_block(c))
    content = CLAUSE_DELIMITER.join(blocks)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {len(clauses)} clauses to {output_path}")


def main() -> int:
    url = BCFSA_CLauses_URL
    clauses = fetch_and_parse(url)
    if not clauses:
        print("No clauses extracted. Check the page structure.")
        return 1
    kb_dir = _root / "knowledge_base"
    out = kb_dir / "bcfsa_clauses.txt"
    save_clauses(clauses, out)
    print(f"Done. Next: python scripts/ingest_bcfsa_clauses.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
