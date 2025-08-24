
"""
Corporate News Article Content Extraction System

This module extracts structured content (title, date, body) from individual 
news article URLs. Uses intelligent content classification to separate 
relevant article text from boilerplate sections like legal disclaimers,
company descriptions, and navigation elements.

Pipeline Integration:
- Input: Individual news article URLs
- Output: Clean HTML with labeled content sections (title, date, body, tables)
- Usage: Process URLs discovered by NewsGroupFinder to extract article content
"""




# Standard library imports
import time
import random
import re
import json
import copy
from datetime import datetime

# Third-party imports
import dateutil.parser
from bs4 import BeautifulSoup, NavigableString
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

"""
PIPELINE INTEGRATION GUIDE:

This module serves as the content extraction component in the news analysis pipeline:

1. INPUT: Individual news article URLs (from NewsGroupFinder output)
2. PROCESSING: Extracts title, date, and clean article body
3. OUTPUT: Structured HTML with labeled content sections

Typical integration pattern:
    extractor = ArticleExtractor()
    
    for article_url in discovered_urls:
        soup = extractor.extract_article(article_url)
        if soup:
            title = soup.find(attrs={'ali-zx9v8k2m4p-title-type': 'qw7x_article_title_p9m2'})
            date = soup.find(attrs={'ali-zx9v8k2m4p-date-type': 'qw7x_article_date_p9m2'}) 
            content = soup.find_all(attrs={'ali-zx9v8k2m4p-content-type': 'qw7x_article_content_p9m2'})
    
    extractor.close()
"""

class ArticleExtractor:
    
    """
    Intelligent article content extraction system for corporate press releases.
    
    This class processes individual news article URLs to extract structured content
    while filtering out boilerplate sections like legal disclaimers, company 
    descriptions, and navigation elements. Uses advanced content classification
    to separate relevant article text from noise.
    
    Key Features:
    - Multi-method title and date detection (meta tags, schema.org, text patterns)
    - Intelligent content filtering (removes "Forward Looking Statements", "About Us")
    - Table structure preservation with proper labeling
    - Sequential text node wrapping for precise content control
    
    Args:
        headless (bool): Whether to run browser in headless mode (default: True)
    """
    
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self.soup = None
        self.original_soup = None
        self._setup_driver()
        

    def _setup_driver(self):
        """Initialize Selenium WebDriver with enhanced anti-detection"""
        chrome_options = Options()
        
        # Standard options
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # Anti-detection options
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Cookie and privacy settings
        chrome_options.add_argument('--enable-cookies')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        
        # Mimic real browser
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument(f'--user-agent={self._get_random_user_agent()}')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # Post-initialization stealth settings
        self.driver.execute_cdp_cmd('Network.enable', {})
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    def _get_random_user_agent(self):
        """Return a random modern user agent"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0'
        ]
        return random.choice(user_agents)

    def _handle_cloudflare(self):
        """Handle Cloudflare protection"""
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "challenge-form"))
            )
            time.sleep(5)
            
            try:
                cookie_buttons = self.driver.find_elements(By.XPATH, 
                    "//button[contains(text(), 'Accept') or contains(text(), 'Allow') or contains(text(), 'Agree')]"
                )
                if cookie_buttons:
                    cookie_buttons[0].click()
            except Exception:
                pass
                
            return True
        except TimeoutException:
            return True
        except Exception as e:
            print(f"Error handling Cloudflare: {str(e)}")
            return False

    def extract_article(self, url):
        """
        Extract and structure article content from a given URL.
    
        Processes the article page to identify and label key content sections:
        - Title (from meta tags, schema.org, or H1 elements)
        - Publication date (from meta tags, schema.org, or text patterns)  
        - Article body (filtered to remove boilerplate content)
        - Tables and structured data
        
        Args:
            url (str): URL of the news article to process
            
        Returns:
            BeautifulSoup: Labeled soup object with marked content sections
            dict: Error information if extraction fails
        """
        try:
            self.driver.get(url)
            if not self._handle_cloudflare():
                raise Exception("Could not bypass protection")

            # Wait for content to load
            time.sleep(random.uniform(2, 4))
            
            self.soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # First wrap all text nodes and number them
            self._wrap_text_nodes(self.soup)
            
            # Then label all elements with unique IDs
            self._label_elements(self.soup)
            
            # Store original version
            self.original_soup = BeautifulSoup(str(self.soup), 'html.parser')
            
            # Mark different components in the soup
            self._mark_title(self.soup)
            self._mark_date(self.soup)
            self._mark_content(self.soup)
            self._mark_metadata(self.soup)
            
            return self.soup
            
        except Exception as e:
            return {'error': str(e), 'url': url}

    def _wrap_text_nodes(self, soup):
        """Wrap all text nodes in auxiliary tags with sequential numbering"""
        text_nodes = []
        for text in soup.find_all(string=True):
            if text.strip():  # Only process non-empty text nodes
                text_nodes.append(text)
        
        # Process each text node with sequential numbering
        for idx, text in enumerate(text_nodes, 1):
            if isinstance(text, NavigableString):
                # Create new auxiliary tag with unique name
                aux_tag = soup.new_tag('ali-tx9v8k2m4p')
                # Add sequence number attribute
                aux_tag['ali-tx9v8k2m4p-seq'] = f'qw7x_{idx}_p9m2'
                # Replace the text node with our new tag containing the text
                text.wrap(aux_tag)

    def _label_elements(self, soup):
        """Label all elements with unique IDs"""
        for idx, element in enumerate(soup.find_all()):
            element['ali-zx9v8k2m4p'] = f"q7y5n3j6h_{idx}"
            
    def _mark_title(self, soup):
        """Mark article title in the soup using multiple methods"""
        title_candidates = []
    
        # Try OpenGraph title
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title_candidates.append({
                'element': og_title,
                'text': og_title.get('content'),
                'ali_id': og_title.get('ali-zx9v8k2m4p')
            })
        
        # Try schema.org metadata
        schema = soup.find('script', type='application/ld+json')
        if schema:
            try:
                data = json.loads(schema.string)
                if isinstance(data, dict) and 'headline' in data:
                    title_candidates.append({
                        'element': schema,
                        'text': data['headline'],
                        'ali_id': schema.get('ali-zx9v8k2m4p')
                    })
            except:
                pass
        
        # Try main headline with article context
        article = soup.find('article')
        if article:
            h1 = article.find('h1')
            if h1:
                title_candidates.append({
                    'element': h1,
                    'text': h1.get_text(strip=True),
                    'ali_id': h1.get('ali-zx9v8k2m4p')
                })
        
        # Try page's main h1
        if not title_candidates:
            h1 = soup.find('h1')
            if h1:
                title_candidates.append({
                    'element': h1,
                    'text': h1.get_text(strip=True),
                    'ali_id': h1.get('ali-zx9v8k2m4p')
                })
        
        # Select the best candidate (longest that's not too long)
        valid_titles = [
            candidate for candidate in title_candidates 
            if candidate['text'] and len(candidate['text']) < 200
        ]
        
        # Mark the best candidate
        if valid_titles:
            best_title = max(valid_titles, key=lambda x: len(x['text']))
            element = soup.find(attrs={'ali-zx9v8k2m4p': best_title['ali_id']})
            if element:
                element['ali-zx9v8k2m4p-title-type'] = 'qw7x_article_title_p9m2'
    
    def _mark_date(self, soup):
       """Mark article date in the soup using multiple methods"""
       # Try meta tags first (most reliable) - meta content attributes aren't affected by text wrapping
       for meta in soup.find_all('meta'):
           if meta.get('property') in ['article:published_time', 'og:published_time']:
               try:
                   date = dateutil.parser.parse(meta['content'])
                   meta['ali-zx9v8k2m4p-date-type'] = 'qw7x_article_date_p9m2'
                   meta['ali-zx9v8k2m4p-parsed-date'] = str(date)
                   return
               except:
                   continue
               
       # Try schema.org metadata (second most reliable) - schema.string isn't affected by wrapping as it's in script
       schema = soup.find('script', type='application/ld+json')
       if schema:
           try:
               data = json.loads(schema.string)
               if isinstance(data, dict) and 'datePublished' in data:
                   date = dateutil.parser.parse(data['datePublished'])
                   schema['ali-zx9v8k2m4p-date-type'] = 'qw7x_article_date_p9m2'
                   schema['ali-zx9v8k2m4p-parsed-date'] = str(date)
                   return
           except:
               pass
    
       date_patterns = [
           r'\d{4}-\d{2}-\d{2}',
           r'\d{1,2}/\d{1,2}/\d{2,4}',
           r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}'
       ]
    
       pub_indicators = ['press', 'release', 'published', 'posted']
       candidate_dates = []
    
       # First pass: find all dates and score them
       for pattern in date_patterns:
           # Find all our wrapped text nodes
           text_nodes = soup.find_all('ali-tx9v8k2m4p')
           for text_node in text_nodes:
               try:
                   text = text_node.get_text()
                   match = re.search(pattern, text)
                   if match:
                       date_str = match.group()
                       parsed_date = dateutil.parser.parse(date_str)
                       
                       
                       # First check: Ignore future dates
                       if parsed_date > datetime.now():
                           continue
                       
                       score = 0
                       
                       # Check class names for news/date keywords
                       def has_news_date_class(tag):
                           if not tag.get('class'):
                               return False
                           class_text = ' '.join(tag.get('class')).lower()
                           return ('news' in class_text or 'new' in class_text) and 'date' in class_text
                       
                       # Check parent elements for news/date class
                       # Note: text_node is our ali-tx9v8k2m4p, so we start checking from its parent
                       if (hasattr(text_node.parent, 'get') and has_news_date_class(text_node.parent)) or \
                       any(has_news_date_class(p) for p in text_node.parent.parents if hasattr(p, 'get')):
                           score += 5
                       
                       # Check for publication indicators in surrounding text
                       # We need to check the text of neighboring text nodes too
                       surrounding_text = text_node.parent.get_text().lower()
                       
                       if any(indicator in surrounding_text for indicator in pub_indicators):
                           score += 5
                       
                       if score >= 0:  # Only add dates that got some score
                           candidate_dates.append({
                               'date': parsed_date,
                               'element': text_node,  # Store the actual text node we found
                               'score': score
                           })
                       
               except Exception as e:
                   continue
               
       # Mark the highest scoring date        
       if candidate_dates:
           best_candidate = max(candidate_dates, key=lambda x: x['score'])                     
           # Mark the text node itself
           best_candidate['element']['ali-zx9v8k2m4p-date-type'] = 'qw7x_article_date_p9m2'
           best_candidate['element']['ali-zx9v8k2m4p-parsed-date'] = str(best_candidate['date'])
                
    def _mark_content(self, soup):
        """Mark main article content in the soup"""
        # Remove unwanted elements
        unwanted_tags = {'nav', 'footer', 'aside', 'script', 'style', 'noscript'}

                
        # Try to find main article content
        content = None
        
        # Method 1: Try article tag
        article = soup.find('article')
        if article:
            content = article
                
        # Method 2: Try main content div
        if not content:
            content_patterns = [
                r'(article|post|entry).*content',
                r'main-content',
                r'story-content',
                r'news-content'
            ]
            for pattern in content_patterns:
                for div in soup.find_all('div', class_=re.compile(pattern, re.I)):
                    if len(div.get_text(strip=True)) > 200:
                        content = div
                        break
                if content:
                    break
            
        # Method 3: Try largest text block
        if not content:
            # Only consider text blocks that aren't in unwanted tags
            text_blocks = [block for block in soup.find_all(['div', 'section']) 
                          if not any(parent.name in unwanted_tags for parent in block.parents)]
            if text_blocks:
                content = max(text_blocks, key=lambda x: len(x.get_text(strip=True)))
    
        if not content:
            return
                
        skip_remaining = False
        processed_elements = set()
        
        def get_direct_text(element):
            """Get only the text directly inside this element, not from children"""
            return ' '.join(
                text.strip() 
                for text in element.strings 
                if text.parent == element and text.strip()
            )
        
        def process_element_recursively(element):
            """Process and mark an element and its children"""
            nonlocal skip_remaining, processed_elements
            
            if skip_remaining:
                return
                
            # Check if we've already processed this element
            element_id = element.get('ali-zx9v8k2m4p')
            if element_id in processed_elements:
                return
            processed_elements.add(element_id)  # Mark as processed
                
            # Get direct text from this element
            direct_text = get_direct_text(element)
            
            if direct_text:
                is_boilerplate, is_section_header = self._is_boilerplate(direct_text, element)
                
                if is_section_header:
                    skip_remaining = True
                    return
                    
                if not is_boilerplate:
                    element['ali-zx9v8k2m4p-content-type'] = 'qw7x_article_content_p9m2'
                    element['ali-zx9v8k2m4p-content-tag'] = element.name
            
            # Process children recursively
            for child in element.children:
                if hasattr(child, 'name') and child.name:  # Check if it's a tag and not just text
                    if child.name == 'table':  # Handle tables specially
                        if not skip_remaining:
                            if self._mark_table(child):  # Modified to mark instead of extract
                                child['ali-zx9v8k2m4p-content-type'] = 'qw7x_article_table_p9m2'
                                processed_elements.add(child['ali-zx9v8k2m4p'])
                        continue
                    process_element_recursively(child)
    
        # The main tags we're interested in
        target_tags = ['p', 'h2', 'h3', 'h4', 'ul', 'ol', 'table', 'blockquote']
        
        for element in content.find_all(target_tags):
            # Check if element is already processed
            if element.get('ali-zx9v8k2m4p') in processed_elements:
                continue
                
            # Check if this element or any of its parents is a table
            if element.name == 'table' or any(parent.name == 'table' for parent in element.parents):
                # If it's a table, mark it
                if element.name == 'table' and not skip_remaining:
                    if self._mark_table(element):
                        element['ali-zx9v8k2m4p-content-type'] = 'qw7x_article_table_p9m2'
                        processed_elements.add(element['ali-zx9v8k2m4p'])
                continue  # Skip elements that are part of tables
            
            # For non-table elements, process them recursively
            process_element_recursively(element)
    
    def _mark_table(self, table):
        """Mark table structure in the soup"""
        has_content = False
        
        # Mark headers
        for th in table.find_all('th'):
            if th.get_text(strip=True):
                th['ali-zx9v8k2m4p-content-type'] = 'qw7x_table_header_p9m2'
                has_content = True
        
        # Mark cells
        for td in table.find_all('td'):
            if td.get_text(strip=True):
                td['ali-zx9v8k2m4p-content-type'] = 'qw7x_table_cell_p9m2'
                has_content = True
        
        return has_content      

    def _mark_metadata(self, soup):
       """Mark metadata elements in the soup"""
       # Author
       author_elements = [
           ('meta', {'name': 'author'}),
           ('meta', {'property': 'article:author'}),
           ('a', {'rel': 'author'}),
           ('span', {'class': re.compile(r'author|byline', re.I)})
       ]
       
       for tag, attrs in author_elements:
           element = soup.find(tag, attrs)
           if element:
               element['ali-zx9v8k2m4p-metadate_type'] = 'qw7x_article_author_p9m2'
               if tag == 'meta':
                   element['ali-zx9v8k2m4p-author-value'] = element.get('content')
               else:
                   element['ali-zx9v8k2m4p-author-value'] = element.get_text(strip=True)
               break
       
       # Keywords/tags
       keywords = soup.find('meta', {'name': 'keywords'})
       if keywords:
           keywords['ali-zx9v8k2m4p-metadate_type'] = 'qw7x_article_keywords_p9m2'
           keywords_list = [k.strip() for k in keywords.get('content', '').split(',')]
           # Store keywords as a JSON string to preserve the list structure
           keywords['ali-zx9v8k2m4p-keywords-value'] = json.dumps(keywords_list)
       
       # Category
       category = soup.find('meta', {'property': 'article:section'})
       if category:
           category['ali-zx9v8k2m4p-metadate_type'] = 'qw7x_article_category_p9m2'
           category['ali-zx9v8k2m4p-category-value'] = category.get('content')

    def _is_boilerplate(self, text, element=None):
        """
        Enhanced boilerplate detection including financial/corporate specific sections.
        Returns (is_boilerplate, is_section_header)
        """
        # Regular boilerplate patterns (unchanged)
        basic_patterns = [
            r'copyright',
            r'all rights reserved',
            r'terms of (use|service)',
            r'privacy policy',
            r'contact us',
            r'share this',
            r'follow us',
            r'subscribe to'
        ]
        
        # Strict section header patterns that must match exactly
        strict_section_headers = [
            r'^forward[\s-]*looking[\s-]*statements?$',
            r'^safe\s+harbor\s+statements?$',
            r'^\s*about\s+[a-z\s]+$',  # Matches "About Company Name"
            r'^\s*[a-z\s]+[\']?s\s+safe\s+harbor\s+statement$'  # Matches "Company's Safe Harbor Statement"
        ]
        
        # Lenient section header patterns that require bold text
        lenient_section_headers = [
            r'^.*forward[\s-]*looking[\s-]*statements?.*$',
            r'^.*safe\s+harbor\s+statements?.*$',
            r'^.*about\s+[a-z\s]+.*$',
            r'^.*[a-z\s]+[\']?s\s+safe\s+harbor\s+statement.*$'
        ]
        
        # Check if it's a basic boilerplate
        if any(re.search(pattern, text, re.I) for pattern in basic_patterns):
            return True, False
        
        # Check strict section headers
        is_strict_section_header = any(
            re.search(pattern, text.strip().lower(), re.I) 
            for pattern in strict_section_headers
        )
        
        # Check lenient section headers (with bold condition)
        is_lenient_section_header = (
            element is not None and  # Ensure element is provided
            any(
                re.search(pattern, text.strip().lower(), re.I) 
                for pattern in lenient_section_headers
            ) and 
            (
                element.parent.name in ['b', 'strong'] or  # The element itself is a bold tag
                (element.parent.get('style', '').lower().find('font-weight: bold') != -1) or  # Inline CSS makes it bold
                (element.parent.get('class', '') and any('bold' in cls.lower() for cls in element.get('class')))  # CSS class makes it bold
            )
        )
        
        return False, (is_strict_section_header or is_lenient_section_header)
           
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()

    def __del__(self):
        """Ensure browser is closed on deletion"""
        self.close()
  


class SoupCleaner:
    def __init__(self, labeled_soup):
        """
        Initialize with a soup that has been processed by ArticleExtractor
        
        Args:
            labeled_soup: BeautifulSoup object with our special labels
        """
        self.original_soup = labeled_soup
        self.clean_soup = None
        
        # Define our label types
        self.content_labels = {
            'ali-zx9v8k2m4p-title-type',
            'ali-zx9v8k2m4p-date-type',
            'ali-zx9v8k2m4p-content-type',
            'ali-zx9v8k2m4p-metadate_type',
            'ali-zx9v8k2m4p-table_header_p9m2',
            'ali-zx9v8k2m4p-table_cell_p9m2'
        }
        
        # Define elements that should never be cleared
        self.structural_tags = {
            # Core structural elements
            'html', 'head', 'body', 'main', 'article',
            # Rendering-essential elements
            'style', 'script', 'link', 'meta',
            # Navigation and structure
            'nav', 'header', 'footer',
            # Interactive elements that might be needed
            'button', 'form'
        }
    
    def create_clean_soup(self):
        """Create a clean copy of the soup with unwanted elements toggled off"""
        self.clean_soup = copy.deepcopy(self.original_soup)
        
        # Start processing from body to preserve head
        body = self.clean_soup.find('body')
        if body:
            self._process_element(body)
            
        return self.clean_soup
    
    def _should_keep_element(self, element):
        """Check if an element has any of our special labels"""
        return any(element.get(label) for label in self.content_labels)
    
    def _has_labeled_descendant(self, element):
        """Check if element has any descendants with our labels"""
        return any(
            desc.get(label) 
            for desc in element.find_all(True) 
            for label in self.content_labels
        )
    
    def _is_structural_element(self, element):
        """Check if element is crucial for page structure or rendering"""
        return element.name in self.structural_tags
    
    def _process_element(self, element):
        """
        Process a single element according to our logic:
        1. If element is labeled, keep it entirely
        2. If element has no labeled descendants and isn't structural, clear it
        3. If element has labeled descendants, process children recursively
        """
        # Skip processing text nodes
        if isinstance(element, NavigableString):
            return
            
        # Case 1: Element is labeled - keep everything
        if self._should_keep_element(element):
            return
            
        # Case 2: Element has no labeled descendants
        if not self._has_labeled_descendant(element):
            if not self._is_structural_element(element):
                element.decompose()  # Remove element completely if it's not structural
            return
            
        # Case 3: Element has labeled descendants but isn't labeled itself
        # Process all child elements recursively
        for child in list(element.children):  # Create list to avoid modification during iteration
            if not isinstance(child, NavigableString):
                self._process_element(child)
    
    def get_clean_html(self):
        """Return the cleaned HTML as a string"""
        if not self.clean_soup:
            self.create_clean_soup()
        return str(self.clean_soup)
    
    def save_clean_html(self, filepath):
        """Save the cleaned HTML to a file"""
        if not self.clean_soup:
            self.create_clean_soup()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(str(self.clean_soup))
            
    def verify_clean_soup(self):
        """
        Verify that the cleaning process preserved all labeled elements
        Returns True if all labeled elements are preserved, False otherwise
        """
        if not self.clean_soup:
            self.create_clean_soup()
            
        # Check if all labeled elements from original soup exist in clean soup
        for label in self.content_labels:
            original_labeled = set(
                element.get('ali-zx9v8k2m4p') 
                for element in self.original_soup.find_all(attrs={label: True})
            )
            clean_labeled = set(
                element.get('ali-zx9v8k2m4p') 
                for element in self.clean_soup.find_all(attrs={label: True})
            )
            
            if original_labeled != clean_labeled:
                return False
        
        return True


if __name__ == "__main__":
    # Complete pipeline example: Extract + Clean
    extractor = ArticleExtractor()
    
    try:
        article_url = "https://news.archer.com/archer-hires-uae-leader-from-abu-dhabi-executive-office-and-gcaa-in-support-of-plan-to-commence-in-country-service-as-soon-as-late-next-year"
        print(f"Processing article: {article_url}")
        
        # Step 1: Extract and label content
        labeled_soup = extractor.extract_article(article_url)
        
        if isinstance(labeled_soup, dict):  # Error case
            print(f"Error extracting article: {labeled_soup['error']}")
        else:
            print("Article content extracted and labeled")
            
            # Step 2: Clean the soup (remove boilerplate, keep only labeled content)
            cleaner = SoupCleaner(labeled_soup)
            clean_soup = cleaner.create_clean_soup()
            
            # Verify cleaning process
            if cleaner.verify_clean_soup():
                print("Content successfully cleaned and verified")
            else:
                print("Warning: Some labeled content may have been lost during cleaning")
            
            # Step 3: Extract structured content from clean soup
            title_element = clean_soup.find(attrs={'ali-zx9v8k2m4p-title-type': 'qw7x_article_title_p9m2'})
            date_element = clean_soup.find(attrs={'ali-zx9v8k2m4p-date-type': 'qw7x_article_date_p9m2'})
            content = clean_soup.find_all(attrs={'ali-zx9v8k2m4p-content-type': 'qw7x_article_content_p9m2'})
            tables = clean_soup.find_all(attrs={'ali-zx9v8k2m4p-content-type': 'qw7x_article_table_p9m2'})
            
            # Extract title text based on element type
            if title_element:
                if title_element.name == 'meta':
                    title_text = title_element.get('content')
                else:
                    title_text = title_element.get_text(strip=True)
            else:
                title_text = 'Not found'
            
            # Extract date - use parsed date if available, otherwise element-specific extraction
            if date_element:
                # First try the parsed date stored during extraction
                date_text = date_element.get('ali-zx9v8k2m4p-parsed-date')
                if not date_text:
                    # Fallback to element-specific extraction
                    if date_element.name == 'meta':
                        date_text = date_element.get('content')
                    else:
                        date_text = date_element.get_text(strip=True)
            else:
                date_text = 'Not found'
            
            # Display results
            print(f"\nExtracted Content:")
            print(f"Title: {title_text}")
            print(f"Date: {date_text}")
            print(f"Content sections: {len(content)}")
            print(f"Tables: {len(tables)}")
            
            # Optional: Save clean HTML
            # cleaner.save_clean_html('extracted_article.html')
            print(f"\nPipeline complete. Clean HTML ready for next processing stage.")
            
    finally:
        extractor.close()
              
        
        
        
