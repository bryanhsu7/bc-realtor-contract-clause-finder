"""Script to scrape all Robinhood retirement articles and save to knowledge base."""
import sys
import requests
from pathlib import Path
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Tuple
from urllib.parse import urljoin
import time

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


def extract_content_from_article(html_content: str, url: str = "") -> Dict[str, str]:
    """Extract title and content from a Robinhood support article.
    
    Args:
        html_content: HTML content as string
        url: Source URL for reference
        
    Returns:
        Dictionary with 'title' and 'content' keys
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Get title
    title = ""
    title_tag = soup.find('title')
    if title_tag:
        title = clean_text(title_tag.get_text())
    else:
        h1 = soup.find('h1')
        if h1:
            title = clean_text(h1.get_text())
    
    # Find main content area - Robinhood articles typically have content in article tags or main content divs
    content_parts = []
    
    # Try to find article or main content
    article = soup.find('article')
    if not article:
        article = soup.find('main')
    if not article:
        # Look for content divs
        article = soup.find('div', class_=re.compile(r'content|article|body', re.I))
    
    if article:
        # Remove script and style tags
        for script in article(['script', 'style', 'nav', 'footer', 'header']):
            script.decompose()
        
        # Get all text content
        content = article.get_text(separator='\n', strip=True)
        content_parts.append(content)
    else:
        # Fallback: get body text
        body = soup.find('body')
        if body:
            for script in body(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()
            content = body.get_text(separator='\n', strip=True)
            content_parts.append(content)
    
    full_content = '\n\n'.join(content_parts)
    
    return {
        'title': title,
        'content': clean_text(full_content)
    }


def extract_qa_from_content(content: str, title: str = "") -> List[Tuple[str, str]]:
    """Extract Q&A pairs from article content.
    
    Args:
        content: Article content text
        title: Article title
        
    Returns:
        List of (question, answer) tuples
    """
    qa_pairs = []
    
    # Pattern 1: Look for headings that are questions followed by content
    lines = content.split('\n')
    current_question = None
    current_answer = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if line looks like a question (contains ? or starts with question words)
        is_question = (
            '?' in line or 
            line.lower().startswith(('what', 'how', 'why', 'when', 'where', 'who', 'can', 'do', 'is', 'are', 'will', 'does', 'did'))
        )
        
        if is_question and len(line) < 200:  # Likely a question heading
            # Save previous Q&A if exists
            if current_question and current_answer:
                answer = ' '.join(current_answer).strip()
                if len(answer) > 20:
                    qa_pairs.append((current_question, answer))
            
            current_question = line
            current_answer = []
        else:
            # This is part of the answer
            if current_question:
                current_answer.append(line)
            elif title and not qa_pairs:
                # If we haven't found any Q&A yet, use title as question and content as answer
                pass
    
    # Save last Q&A if exists
    if current_question and current_answer:
        answer = ' '.join(current_answer).strip()
        if len(answer) > 20:
            qa_pairs.append((current_question, answer))
    
    # If no Q&A pairs found, create one from title and content
    if not qa_pairs and title and content:
        qa_pairs.append((title, content))
    
    return qa_pairs


def scrape_article(url: str) -> Dict[str, any]:
    """Scrape a single article.
    
    Args:
        url: URL of the article
        
    Returns:
        Dictionary with article data
    """
    print(f"Scraping: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        article_data = extract_content_from_article(response.text, url)
        qa_pairs = extract_qa_from_content(article_data['content'], article_data['title'])
        
        return {
            'url': url,
            'title': article_data['title'],
            'content': article_data['content'],
            'qa_pairs': qa_pairs
        }
        
    except requests.RequestException as e:
        print(f"  Error fetching {url}: {e}")
        return None
    except Exception as e:
        print(f"  Error parsing {url}: {e}")
        return None


def save_retirement_faqs(articles: List[Dict], output_path: Path):
    """Save retirement FAQs to knowledge base file.
    
    Args:
        articles: List of article dictionaries
        output_path: Path to save the file
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("Robinhood Retirement FAQs scraped from: https://robinhood.com/us/en/support/retirement/\n")
        f.write("=" * 80 + "\n\n")
        f.write("ROBINHOOD RETIREMENT FREQUENTLY ASKED QUESTIONS\n\n")
        
        total_qa = 0
        for article in articles:
            if not article:
                continue
            
            # Write article title as section header
            f.write(f"\n{'='*80}\n")
            f.write(f"ARTICLE: {article['title']}\n")
            f.write(f"URL: {article['url']}\n")
            f.write(f"{'='*80}\n\n")
            
            # Write Q&A pairs
            if article['qa_pairs']:
                for question, answer in article['qa_pairs']:
                    f.write(f"Q: {question}\n")
                    f.write(f"A: {answer}\n\n")
                    total_qa += 1
            else:
                # If no Q&A pairs, write the full content as answer to the title
                f.write(f"Q: {article['title']}\n")
                f.write(f"A: {article['content']}\n\n")
                total_qa += 1
        
        print(f"\n✅ Saved {total_qa} Q&A pairs from {len([a for a in articles if a])} articles to {output_path}")


def main():
    """Main function to scrape all retirement articles."""
    
    # List of retirement article URLs (from the support page structure)
    retirement_urls = [
        "https://robinhood.com/us/en/support/articles/ira-overview/",
        "https://robinhood.com/us/en/support/articles/ira-contributions/",
        "https://robinhood.com/us/en/support/articles/ira-adjustments/",
        "https://robinhood.com/us/en/support/articles/ira-withdrawals/",
        "https://robinhood.com/us/en/support/articles/transfers-and-rollovers/",
        "https://robinhood.com/us/en/support/articles/ira-match-faq/",
        "https://robinhood.com/us/en/support/articles/robinhood-gold-ira-transfer-bonus/",
        "https://robinhood.com/us/en/support/articles/529-plan-to-roth-ira-rollover/",
        "https://robinhood.com/us/en/support/articles/retirement-investing/",
        "https://robinhood.com/us/en/support/articles/ira-growth-potential/",
        "https://robinhood.com/us/en/support/articles/options-in-robinhood-retirement/",
        "https://robinhood.com/us/en/support/articles/roth-conversions/",
        "https://robinhood.com/us/en/support/articles/account-protection-with-sipc-for-no-additional-cost/",
    ]
    
    print(f"Scraping {len(retirement_urls)} retirement articles...\n")
    
    articles = []
    for i, url in enumerate(retirement_urls, 1):
        print(f"[{i}/{len(retirement_urls)}] ", end="")
        article = scrape_article(url)
        articles.append(article)
        
        # Be polite - wait between requests
        if i < len(retirement_urls):
            time.sleep(1)
    
    # Determine output path
    kb_dir = Path(__file__).parent.parent / "knowledge_base"
    kb_dir.mkdir(parents=True, exist_ok=True)
    output_path = kb_dir / "robinhood_retirement_faqs.txt"
    
    # Save FAQs
    save_retirement_faqs(articles, output_path)
    
    print(f"\n✅ Success! FAQs saved to: {output_path}")
    print(f"\nNext step: Run 'python scripts/ingest_documents.py' to add these to the vector database.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
