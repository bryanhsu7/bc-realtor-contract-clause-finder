"""Script to scrape FAQs from a website and save to knowledge base."""
import sys
import requests
from pathlib import Path
from bs4 import BeautifulSoup
import re
from typing import List, Tuple
from urllib.parse import urljoin, urlparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def extract_faqs_from_html(html_content: str, url: str = "") -> List[Tuple[str, str]]:
    """Extract FAQ questions and answers from HTML.
    
    Args:
        html_content: HTML content as string
        url: Source URL for reference
        
    Returns:
        List of (question, answer) tuples
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    faqs = []
    
    # Common FAQ patterns to look for
    patterns = [
        # Pattern 1: <dt>Q:</dt><dd>A:</dd> or similar
        lambda s: s.find_all(['dt', 'dd']),
        # Pattern 2: Elements with "question" or "answer" in class/id
        lambda s: s.find_all(class_=re.compile(r'question|faq-q|q-', re.I)),
        # Pattern 3: Elements with "answer" or "faq-a" in class/id
        lambda s: s.find_all(class_=re.compile(r'answer|faq-a|a-', re.I)),
        # Pattern 4: <h3>Question</h3><p>Answer</p> pattern
        lambda s: s.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']),
        # Pattern 5: <div> with question/answer classes
        lambda s: s.find_all('div', class_=re.compile(r'faq|question|answer', re.I)),
        # Pattern 6: <article> or <section> with FAQ content
        lambda s: s.find_all(['article', 'section'], class_=re.compile(r'faq', re.I)),
    ]
    
    # Try to find FAQ container
    faq_containers = soup.find_all(['div', 'section', 'article'], 
                                   class_=re.compile(r'faq|frequently-asked|questions', re.I))
    
    if faq_containers:
        # Focus on FAQ containers
        search_area = faq_containers
    else:
        # Search entire page
        search_area = [soup]
    
    # Method 1: Look for structured FAQ patterns (dt/dd, question/answer pairs)
    for container in search_area:
        # Pattern: <dt>Question</dt><dd>Answer</dd>
        dts = container.find_all('dt')
        dds = container.find_all('dd')
        if dts and dds and len(dts) == len(dds):
            for dt, dd in zip(dts, dds):
                q = clean_text(dt.get_text())
                a = clean_text(dd.get_text())
                if q and a:
                    faqs.append((q, a))
            if faqs:
                return faqs
        
        # Pattern: Elements with question/answer classes in pairs
        questions = container.find_all(class_=re.compile(r'question|faq-q|q-', re.I))
        answers = container.find_all(class_=re.compile(r'answer|faq-a|a-', re.I))
        if questions and answers and len(questions) == len(answers):
            for q_elem, a_elem in zip(questions, answers):
                q = clean_text(q_elem.get_text())
                a = clean_text(a_elem.get_text())
                if q and a:
                    faqs.append((q, a))
            if faqs:
                return faqs
    
    # Method 2: Look for heading + following content pattern
    for container in search_area:
        headings = container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            text = clean_text(heading.get_text())
            # Check if it looks like a question
            if '?' in text or text.lower().startswith(('what', 'how', 'why', 'when', 'where', 'who', 'can', 'do', 'is', 'are', 'will')):
                # Get following content as answer
                answer_parts = []
                next_elem = heading.find_next_sibling()
                while next_elem and next_elem.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    if next_elem.name in ['p', 'div', 'li']:
                        answer_text = clean_text(next_elem.get_text())
                        if answer_text:
                            answer_parts.append(answer_text)
                    next_elem = next_elem.find_next_sibling()
                
                if answer_parts:
                    answer = ' '.join(answer_parts)
                    if len(answer) > 20:  # Minimum answer length
                        faqs.append((text, answer))
    
    # Method 3: Look for Q: and A: patterns in text
    for container in search_area:
        text_content = container.get_text()
        # Pattern: Q: ... A: ...
        qa_pattern = re.compile(r'(?:Q|Question)[:\s]+(.+?)(?:A|Answer)[:\s]+(.+?)(?=(?:Q|Question)[:\s]|$)', 
                                re.IGNORECASE | re.DOTALL)
        matches = qa_pattern.findall(text_content)
        for q, a in matches:
            q = clean_text(q)
            a = clean_text(a)
            if q and a and len(a) > 20:
                faqs.append((q, a))
    
    # Method 4: Look for list items that might be FAQs
    for container in search_area:
        lists = container.find_all(['ul', 'ol'])
        for ul in lists:
            items = ul.find_all('li', recursive=False)
            for item in items:
                text = clean_text(item.get_text())
                # Check if item contains question mark and substantial content
                if '?' in text and len(text) > 50:
                    # Try to split on question mark
                    parts = text.split('?', 1)
                    if len(parts) == 2:
                        q = clean_text(parts[0] + '?')
                        a = clean_text(parts[1])
                        if q and a and len(a) > 20:
                            faqs.append((q, a))
    
    return faqs


def scrape_website(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Scrape FAQs from a website.
    
    Args:
        url: URL of the FAQ page
        
    Returns:
        Tuple of (page_title, list of (question, answer) tuples)
    """
    print(f"Fetching URL: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Get page title
        soup = BeautifulSoup(response.content, 'html.parser')
        title_tag = soup.find('title')
        page_title = title_tag.get_text().strip() if title_tag else urlparse(url).netloc
        
        print(f"Page title: {page_title}")
        print(f"Content length: {len(response.content)} bytes")
        
        # Extract FAQs
        faqs = extract_faqs_from_html(response.text, url)
        
        return page_title, faqs
        
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        raise
    except Exception as e:
        print(f"Error parsing content: {e}")
        raise


def save_faqs_to_file(faqs: List[Tuple[str, str]], output_path: Path, source_url: str = ""):
    """Save FAQs to a text file.
    
    Args:
        faqs: List of (question, answer) tuples
        output_path: Path to save the file
        source_url: Source URL for reference
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        if source_url:
            f.write(f"FAQs scraped from: {source_url}\n")
            f.write("=" * 80 + "\n\n")
        
        f.write("FREQUENTLY ASKED QUESTIONS\n\n")
        
        for i, (question, answer) in enumerate(faqs, 1):
            f.write(f"Q: {question}\n")
            f.write(f"A: {answer}\n\n")
    
    print(f"✅ Saved {len(faqs)} FAQs to {output_path}")


def main():
    """Main function to scrape FAQs."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape FAQs from a website")
    parser.add_argument(
        "url",
        type=str,
        help="URL of the FAQ page to scrape"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output filename (default: faqs_scraped.txt)"
    )
    
    args = parser.parse_args()
    
    # Scrape the website
    try:
        page_title, faqs = scrape_website(args.url)
        
        if not faqs:
            print("⚠️  No FAQs found on the page.")
            print("The page might use a different structure. You may need to manually extract the FAQs.")
            return
        
        print(f"\n✅ Found {len(faqs)} FAQ(s)")
        
        # Show preview
        print("\nPreview of first few FAQs:")
        for i, (q, a) in enumerate(faqs[:3], 1):
            print(f"\n{i}. Q: {q[:80]}...")
            print(f"   A: {a[:80]}...")
        
        if len(faqs) > 3:
            print(f"\n... and {len(faqs) - 3} more")
        
        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            kb_dir = Path(__file__).parent.parent / "knowledge_base"
            # Create a safe filename from URL
            domain = urlparse(args.url).netloc.replace('.', '_')
            output_path = kb_dir / f"faqs_{domain}.txt"
        
        # Ensure knowledge_base directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save FAQs
        save_faqs_to_file(faqs, output_path, args.url)
        
        print(f"\n✅ Success! FAQs saved to: {output_path}")
        print(f"\nNext step: Run 'python scripts/ingest_documents.py' to add these to the vector database.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
