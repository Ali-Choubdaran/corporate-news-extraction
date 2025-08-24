

"""
Corporate Press Release URL Discovery System

This module automatically discovers and extracts all news article URLs from 
corporate press release pages. It handles diverse website structures and 
navigation patterns including pagination, year selectors, and load-more buttons.

Pipeline Integration:
- Input: Corporate press release page URL (e.g., https://news.archer.com/)  
- Output: List of individual news article URLs
- Usage: Connect to a database of company press release URLs to systematically
  collect all news articles across publicly traded companies
"""



# Standard library imports
import time
import random
import re
from collections import defaultdict
from bs4 import BeautifulSoup

# Third-party imports  
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    ElementClickInterceptedException, 
    NoSuchElementException
)


"""
PIPELINE INTEGRATION GUIDE:

This module serves as the URL discovery component of a larger news analysis pipeline:

1. INPUT: Corporate press release page URLs (e.g., from Russell 2000 companies)
2. PROCESSING: Automatically discovers all individual news article URLs
3. OUTPUT: List of news article URLs ready for content extraction

Typical integration pattern:
    company_urls = load_company_press_urls()  # From database/file
    all_article_urls = []
    
    for company_url in company_urls:
        finder = NewsGroupFinder(company_url)
        news_groups = finder.find_all_news_groups()
        if news_groups:
            for group in news_groups:
                all_article_urls.extend(group['urls'].iloc[0])
    
    save_article_urls(all_article_urls)  # For next pipeline stage
"""


class NewsGroupFinder:
    """
    Automated news article URL discovery system for corporate press release pages.
    
    This class intelligently identifies and extracts news article URLs from corporate
    websites by analyzing HTML structure patterns, URL characteristics, and navigation
    elements. Handles diverse pagination schemes and anti-bot protection.
    
    Key Features:
    - Anti-detection web scraping with Selenium
    - Intelligent link classification and filtering  
    - Multi-modal pagination handling (year selectors, load more, numbered pages)
    - Robust error handling and fallback mechanisms
    
    Args:
        url (str): Base URL of the corporate press release page
        headless (bool): Whether to run browser in headless mode (default: True)
    """
    def __init__(self, url,headless=True):
        self.base_url = url
        self.driver = None
        self.soup = None
        self.df = None
        self.news_candidates = None
        self.headless = headless  # Add this line
        self._setup_driver()
        self.client_side_pagination = False
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
        
        # Hide webdriver flag
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
            # Wait for Cloudflare check
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "challenge-form"))
            )
            time.sleep(5)  # Give time for Cloudflare check
            
            # Check for cookie consent
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
            return True  # No Cloudflare challenge found
        except Exception as e:
            print(f"Error handling Cloudflare: {str(e)}")
            return False
        

        
    def _get_ancestry(self, element):
        """Get ancestry path of an element"""
        path = []
        current = element
        while current.parent:
            tag_info = current.parent.name
            if current.parent.get('id'):
                tag_info += f"#{current.parent['id']}"
            if current.parent.get('class'):
                tag_info += f".{'.'.join(current.parent['class'])}"
            path.append(tag_info)
            current = current.parent
        return ' > '.join(reversed(path))
    
    def _get_flexible_ancestry(self, element):
        """Get ancestry path using only tag names"""
        path = []
        current = element
        while current.parent:
            path.append(current.parent.name)
            current = current.parent
        return ' > '.join(reversed(path))
    
    def _is_social_media_url(self, url):
        """
        Check if a single URL is a social media link.
        
        Args:
            url (str): URL to check
            
        Returns:
            int: 1 if URL is social media, 0 otherwise
        """
        url_lower = url.lower()
        if '/x.com' in url_lower or 'www.x.com' in url_lower:
            return 1 
        
        social_patterns = [
            r'(?:^|[/.])?facebook\.com(?:/|$)',
            r'(?:^|[/.])?twitter\.com(?:/|$)',
            r'(?:^|[/.])?instagram\.com(?:/|$)',
            r'(?:^|[/.])?linkedin\.com(?:/|$)',
            r'(?:^|[/.])?youtube\.com(?:/|$)',
            r'(?:^|[/.])?tiktok\.com(?:/|$)',
            r'(?:^|[/.])?pinterest\.com(?:/|$)',
            r'(?:^|[/.])?reddit\.com(?:/|$)',
            r'(?:^|[/.])?whatsapp\.com(?:/|$)'  
        ]
        
        return 1 if any(re.search(pattern, url, re.IGNORECASE) for pattern in social_patterns) else 0


    def _find_twin_and_intersections(self, group_idx, all_urls_sets):
        """Find if group has twins or intersecting URLs"""
        current_set = all_urls_sets[group_idx]
        has_twin = has_intersection = False
        
        for other_idx, other_set in enumerate(all_urls_sets):
            if other_idx != group_idx:
                if current_set == other_set:
                    has_twin = True
                if current_set.intersection(other_set):
                    has_intersection = True
                if has_twin and has_intersection:
                    break
        return has_twin, has_intersection
    
    def _is_typical_url_v0(self, url):
        """Legacy version of typical URL detection (URL patterns only)"""
        typical_patterns = [
            r'^/legal(/|$)', r'^/privacy[-_]?policy(/|$)',
            r'^/terms[-_]?(of[-_]?use|service)(/|$)',
            r'^/about[-_]?(us)?(/|$)', r'^/contact[-_]?(us)?(/|$)',
            r'^/careers?(/|$)', r'^/faq(/|$)',
            r'^/investor[-_]?relations?(/|$)',
            r'^/press(/|$)',r'^/media(/|$)',
            r'^/login(/|$)', r'^/register(/|$)',
            r'^/search(/|$)', r'^/sitemap(/|$)'
        ]
        url_path = re.sub(r'^https?://[^/]+', '', url.lower())
        return any(re.search(pattern, url_path, re.IGNORECASE) for pattern in typical_patterns)
    
    
    def _is_typical_url(self, anchor):
        """
        Check if an anchor tag represents a typical website section.
        Takes a BeautifulSoup anchor tag as input and checks both URL and text content.
        Returns 1 if typical, 0 if not.
        """
        # List of exact URL patterns to check
        url_patterns = [
            '/legal', '/legal/',
            '/terms', '/terms/',
            '/privacy', '/privacy/',
            '/contact', '/contact/',
            '/careers', '/careers/',
            '/support', '/support/',
            '/blog', '/blog/',
            '/events', '/events/',
            '/about', '/about/',
            '/faq', '/faq/',
            '/investors', '/investors/',
            '/search', '/search/',
            '/sitemap', '/sitemap/',
            '/login', '/login/',
            '/register', '/register/',
            '/help', '/help/',
            '/company', '/company/'
        ]
        
        # Check URL first
        url = anchor['href']
        # Remove protocol and domain if present
        url_path = re.sub(r'^https?://[^/]+', '', url.lower())
        
        # Check for exact URL match
        if url_path in url_patterns:
            return 1
            
        # If URL check failed, check anchor text
        text = anchor.get_text(strip=True)
        if not text:  # Empty text
            return 0
            
        # Keywords that indicate typical navigation/utility links
        typical_keywords = {
            'legal', 'terms', 'policy', 'privacy', 'contact', 'careers', 
            'conditions', 'locations', 'faq', 'investors', 'about', 'settings',
            'cookies', 'blog', 'support', 'help', 'resources', 'events',
            'login', 'register', 'account', 'search', 'sitemap', 'media',
            'press', 'directory', 'community', 'company'
        }
        
        # Split text into words (handle both space and hyphen separation)
        words = [w.lower() for w in re.split(r'[\s-]+', text)]
        
        # Check conditions:
        # 1. Max 4 words
        # 2. Contains at least one typical keyword
        if len(words) <= 4 and any(keyword in words for keyword in typical_keywords):
            return 1
            
        return 0
        
    def _analyze_url_structure(self, url):
        """Analyze structural components of a URL for news article classification"""
        components = {
            'has_protocol': False, 'has_subdomain': False,
            'has_port': False, 'has_query': False,
            'has_fragment': False, 'has_file_extension': False,
            'is_relative_url': False, 'multi_level_path': False
        }
        
        try:
            components['has_protocol'] = bool(re.match(r'^https?://', url))
            url_without_protocol = re.sub(r'^https?://', '', url)
            
            domain_part = url_without_protocol.split('/')[0]
            components['has_subdomain'] = bool(re.match(r'^(?!www\.)[a-zA-Z0-9-]+\.', domain_part))
            components['has_port'] = bool(re.search(r':[0-9]+', domain_part))
            components['has_query'] = '?' in url
            components['has_fragment'] = '#' in url
            components['has_file_extension'] = bool(re.search(r'\.[a-zA-Z0-9]+$', url.split('?')[0]))
            components['is_relative_url'] = url.startswith('/')
            
            if components['is_relative_url']:
                components['multi_level_path'] = True
            else:
                path_part = url_without_protocol.split('?')[0].split('#')[0]
                if '/' in path_part:
                    path_segments = [seg for seg in path_part.split('/') if seg]
                    components['multi_level_path'] = len(path_segments) >= 2
        except Exception:
            pass
            
        return components
    def _get_last_path_length(self, url):
        """Get length of the last segment of URL path"""
        try:
            # Remove query parameters and fragments
            clean_url = url.split('?')[0].split('#')[0]
            
            # Remove trailing slash if exists
            clean_url = clean_url.rstrip('/')
            
            # Get last path segment
            segments = clean_url.split('/')
            if not segments:
                return 0
            last_segment = segments[-1] 
            if re.search(r'\.[a-zA-Z0-9]+$', last_segment):
                # If this is the only segment, return 0
                if len(segments) < 2:
                    return 0
                meaningful_segment = segments[-2]
            else:
                meaningful_segment = last_segment

            
            return len(meaningful_segment)
        except Exception as e:
            print(f"Error getting last path length: {str(e)}")
            return 0
    def _make_absolute_url(self, url):
        """Convert relative URL to absolute if needed"""
        if url.startswith('http'):
            return url
            
        # Remove leading slash if present
        url = url.lstrip('/')
        
        # Remove trailing slash from base url if present
        base = self.base_url.rstrip('/')
        
        return f"{base}/{url}"
    
    def _get_verb_variations(self, verb):
        """Generate variations of a verb (base, s-form, and past tense)"""
        variations = {verb}  # Base form
        
        # Add s-form
        variations.add(verb + 's')
        if verb.endswith('y'):
            variations.add(verb[:-1] + 'ies')
        
        # Get past tense from a predefined mapping for irregular verbs
        irregular_verbs = {
            'take': 'took',
            'give': 'gave',
            'make': 'made',
            'begin': 'began',
            'win': 'won',
            'set': 'set',
            'create': 'created',
            # Add more irregular verbs as needed
        }
        
        # Add past tense
        if verb in irregular_verbs:
            variations.add(irregular_verbs[verb])
        else:
            # Regular verb past tense rules
            if verb.endswith('e'):
                variations.add(verb + 'd')
            elif verb.endswith('y'):
                variations.add(verb[:-1] + 'ied')
            else:
                variations.add(verb + 'ed')
        
        return variations
    
    def _has_verb_with_context(self, url):
        """Check if URL contains a verb from the list with proper context"""
        verb_list = ['announce', 'start', 'end', 'finish', 'open', 'close', 'report', 
                     'initiate', 'terminate', 'invest', 'join', 'collaborate', 'hire', 
                     'agree', 'surpass', 'applaud', 'raise', 'deliver', 'unveil', 'plan', 
                     'showcase', 'introduce', 'present', 'grant', 'sign', 'invest', 
                     'complete', 'receive', 'grant', 'give', 'select', 'partner', 'signal', 
                     'continue', 'stop', 'win', 'launch', 'set', 'visit', 'achieve', 
                     'dismiss', 'take', 'accelerate', 'reach', 'indicate', 'enter', 'exit',
                     'produce', 'create', 'make', 'move', 'host', 'locate', 'forms']
        
        try:
            # Remove query parameters and fragments
            clean_url = url.split('?')[0].split('#')[0]
            
            # Remove trailing slash if exists
            clean_url = clean_url.rstrip('/')
            
            # Get last path segment
            segments = clean_url.split('/')
            if not segments:
                return False
                
            last_segment = segments[-1]
            
            # Handle file extensions
            if re.search(r'\.[a-zA-Z0-9]+$', last_segment):
                # If this is the only segment, return False
                if len(segments) < 2:
                    return False
                meaningful_segment = segments[-2]
            else:
                meaningful_segment = last_segment
                
            # Split the meaningful segment by non-word characters
            words = re.split(r'[-_\s.]', meaningful_segment)
            words = [w.lower() for w in words if w]  # Clean and lowercase words
            
            if len(words) <= 1:  # Skip if only one word
                return False
            
            # Check for verb variations
            for verb in verb_list:
                verb_variations = self._get_verb_variations(verb)
                if any(variation in words for variation in verb_variations):
                    return True
                    
            return False
            
        except Exception as e:
            print(f"Error in _has_verb_with_context: {str(e)}")
            return False

    
    def _is_element_hidden(self, element):
        """Check if an HTML element is hidden"""
        try:
            # Check direct style attribute
            if element.get('style') and 'display:none' in element['style'].replace(' ', ''):
                return True
                
            # Check classes
            if element.get('class') and any('hidden' in c.lower() for c in element['class']):
                return True
                
            # Check parent elements (up to 3 levels up)
            parent = element
            for _ in range(3):
                parent = parent.parent
                if parent is None:
                    break
                    
                if parent.get('style') and 'display:none' in parent['style'].replace(' ', ''):
                    return True
                    
                if parent.get('class') and any('hidden' in c.lower() for c in parent['class']):
                    return True
                    
            return False
            
        except Exception as e:
            print(f"Error checking if element is hidden: {str(e)}")
            return False
    
    
    def _find_year_selector(self):
        """
        Find and verify year selector element.
        Returns (selector_element, has_all_option) tuple if found, (None, False) if not found
        """
        try:
            # Look for all select elements
            year_selectors = self.driver.find_elements(By.CSS_SELECTOR, 
                # Original patterns
                "select[class*='year'], select[id*='year'], "
                "select[class*='archive'], select[id*='archive'], "
                "select[class*='date'], select[id*='date'], "
                # Additional patterns
                "select[name*='year'], "  # Match 'year' in name attribute
                "select[id*='Year'], "    # Case sensitive match for 'Year'
                "select[class*='dropdown'], "  # Common class for year dropdowns
                # Get any remaining select elements
                "select"  # This will get ALL select elements
            )
            
            for selector in year_selectors:
                try:
                    # Convert to Select object for easier handling
                    select = Select(selector)
                    options = select.options
                    
                    # Skip if too few options
                    if len(options) < 2:
                        continue
                    #print(f"selector found{selector}")
                    # Count how many options are years
                    year_count = sum(
                        1 for opt in options 
                        if opt.text.strip().isdigit() and len(opt.text.strip()) == 4
                    )

                    # Verify this is likely a year selector (most options should be years)
                    if year_count > len(options) * 0.7:  # 70% of options should be years
                        # Check for "All" option
                        has_all = any(
                            'all' in opt.text.strip().lower() 
                            for opt in options
                        )
                        
                        return selector, has_all
                
                except Exception as e:
                    print(f"Error processing selector: {str(e)}")
                    continue
            
            return None, False
            
        except Exception as e:
            print(f"Error finding year selector: {str(e)}")
            return None, False
    
    def _get_year_options(self):
        """
        Get list of all available years from the year selector.
        Returns list of options or None if selector not found.
        """
        try:
            selector, _ = self._find_year_selector()
            if not selector:
                return None
                
            select = Select(selector)
            return [option.text.strip() for option in select.options]
            
        except Exception as e:
            print(f"Error getting year options: {str(e)}")
            return None


    def _select_year(self, year=None):
        """
        Select specific year or 'All Years' if no year specified.
        Returns True if selection successful, False otherwise.
        
        Args:
            year (str/int, optional): Specific year to select. If None, tries to select 'All Years'
        """
        try:
            selector, has_all = self._find_year_selector()
            if not selector:
                return False
                
            select = Select(selector)
            options = select.options
            
            if year is None:
                # Try to find and select 'All' option (consistent with _find_year_selector)
                for option in options:
                    if 'all' in option.text.strip().lower():
                        select.select_by_visible_text(option.text.strip())
                        time.sleep(2)  # Wait for page to update
                        return True
                return False
            else:
                # Convert year to string for comparison
                year_str = str(year)
                for option in options:
                    if option.text.strip() == year_str:
                        select.select_by_visible_text(year_str)
                        time.sleep(2)  # Wait for page to update
                        return True
                return False
                
        except Exception as e:
            print(f"Error selecting year: {str(e)}")
            return False
        
    def _num_unique_strict_ancestry(self, anchor_list):
        """
        Calculate the number of unique strict ancestries in a list of anchors.
        
        Args:
            anchor_list (list): List of BeautifulSoup anchor elements
            
        Returns:
            int: Number of unique strict ancestries in the list
        """
        if not anchor_list:
            return 0
            
        # Get strict ancestry for each anchor and add to set
        unique_ancestries = {self._get_ancestry(anchor) for anchor in anchor_list}
        
        return len(unique_ancestries)
    
    

    def find_news_group(self,soup):
        """Main method to find news article group"""
        try:
            # Find and filter anchors
            invalid_hrefs = ['/', '', '#', 'javascript:void(0)']
            all_anchors = soup.find_all('a', href=True)
           
            anchors = [
                anchor for anchor in all_anchors 
                if (
                    anchor['href'] not in invalid_hrefs and
                    not anchor['href'].startswith('#') and
                    not anchor['href'].startswith('tel:') and
                    not anchor['href'].startswith('mailto:') and 
                    not self._is_social_media_url(anchor['href'])
                    
                )
            ]
            
            # Group by ancestry with unique URLs
            ancestry_groups = defaultdict(list)
            seen_urls = defaultdict(set)  # Track seen URLs for each ancestry
            
            for anchor in anchors:
                ancestry = self._get_flexible_ancestry(anchor)
                url = anchor['href']
                if url not in seen_urls[ancestry]:
                    ancestry_groups[ancestry].append(anchor)
                    seen_urls[ancestry].add(url)
            
            grouped_anchors = list(ancestry_groups.values())
            
            url_sets = [set(a['href'] for a in group) for group in grouped_anchors]
            
            # Create groups data
            groups_data = []
            for i, group in enumerate(grouped_anchors):
                urls = [a['href'] for a in group]
                anchor_elements = group
                
                # Analyze URL structure
                url_structure_counts = defaultdict(int)
                for url in urls:
                    for key, value in self._analyze_url_structure(url).items():
                        if value:
                            url_structure_counts[f'{key}_count'] += 1
                
                # Calculate percentages
                total_urls = len(urls)
                url_structure_percentages = {
                    key.replace('_count', '_pct'): (count / total_urls if total_urls > 0 else 0)
                    for key, count in url_structure_counts.items()
                }
                
                # Count URLs with verbs
                urls_with_verbs = sum(1 for url in urls if self._has_verb_with_context(url))
 
                # Calculate verb percentage
                verb_percentage = (urls_with_verbs / len(urls)) * 100 if urls else 0
 
                
                has_twin, has_intersection = self._find_twin_and_intersections(i, url_sets)
                url_last_lengths = [self._get_last_path_length(url) for url in urls]
                
                social_media_count = sum(self._is_social_media_url(url) for url in urls)
                total_urls = len(urls)
                group_info = {
                    'group_id': i,
                    'ancestry': self._get_flexible_ancestry(group[0]),
                    'num_unique_strict_ancestry': self._num_unique_strict_ancestry(anchor_elements),
                    'urls': urls,
                    'a': anchor_elements,
                    'url_count': len(urls),
                    'is_social_media_num': social_media_count,
                    'is_social_media_pct': (social_media_count / total_urls * 100) if total_urls > 0 else 0,
                    'twin_group': has_twin,
                    'non_excl_url': has_intersection,
                    'num_typical_url': sum(1 for anchor in anchor_elements if self._is_typical_url(anchor)),
                    'last_path_mean_length': sum(url_last_lengths) / len(url_last_lengths) if url_last_lengths else 0,
                    'last_path_median_length': sorted(url_last_lengths)[len(url_last_lengths)//2] if url_last_lengths else 0,
                    'urls_with_verbs': urls_with_verbs,  # New column
                    'verb_percentage': verb_percentage,   # New column

                    **url_structure_counts,
                    **url_structure_percentages
                }
                groups_data.append(group_info)
            
            # Create DataFrame and remove duplicate URL sets right away
            self.df = pd.DataFrame(groups_data)
            
            # Remove duplicate URL sets at DataFrame level
            self.df['urls_set'] = self.df['urls'].apply(frozenset)
            self.df = self.df.drop_duplicates(subset=['urls_set'])
            self.df = self.df.drop('urls_set', axis=1)
            
            
            self.news_candidates = self.df[
                (self.df['num_typical_url'] == 0) & 
                (self.df['url_count'] > 4) &
                (self.df['is_social_media_num']==0) &
                (self.df['multi_level_path_pct'] == 1)
            ].copy()
            
            # Apply verb percentage filter only if there are multiple candidates
            # and if applying it won't eliminate all candidates
            if len(self.news_candidates) > 1:
                high_verb_candidates = self.news_candidates[
                    self.news_candidates['verb_percentage'] > 20
                ]
                # Only use this filter if it doesn't eliminate all candidates
                if len(high_verb_candidates) > 0:
                    self.news_candidates = high_verb_candidates

    
            # If multiple candidates remain, select the one with highest median length
            if len(self.news_candidates) > 1:
                max_median_length = self.news_candidates['last_path_median_length'].max()
                self.news_candidates = self.news_candidates[
                    self.news_candidates['last_path_median_length'] == max_median_length
                ]
                
            # If multiple candidates remain, select the one with highest median length
            if len(self.news_candidates) > 1:
                max_url_count = self.news_candidates['url_count'].max()
                self.news_candidates = self.news_candidates[
                    self.news_candidates['url_count'] == max_url_count
                ]

            if len(self.news_candidates) == 1:
                # Make URLs absolute before returning
                self.news_candidates['urls'] = self.news_candidates['urls'].apply(
                lambda urls: [self._make_absolute_url(url) for url in urls]
                 )
                return self.news_candidates
            return None
            #return self.news_candidates if len(self.news_candidates) == 1 else None
            
        except Exception as e:
            raise Exception(f"Error finding news group: {str(e)}")
        
    def handle_load_more(self, max_attempts=1):
        """Try to click 'Load More' button and return True if successful"""
       
        try:
            load_more_patterns = [
                # Text variations
                "//li[contains(text(), 'More News')]",
                "//li[contains(text(), 'Load More')]",
                "//button[contains(text(), 'Load More')]",
                "//button[contains(text(), 'Show More')]",
                "//a[contains(text(), 'Show More')]",
                "//a[contains(text(), 'Load More')]",
                "//span[contains(text(), 'Load More')]",
                "//div[contains(text(), 'Load More')]",
                
                # Class variations
                "//div[contains(@class, 'load-more')]",
                "//div[contains(@class, 'loadMore')]",
                "//button[contains(@class, 'more')]",
                "//button[contains(@class, 'load-more')]",
                "//a[contains(@class, 'load-more')]",
                "//a[contains(@class, 'loadMore')]",
                
                # ID variations
                "//button[contains(@id, 'load-more')]",
                "//button[contains(@id, 'loadMore')]",
                "//div[contains(@id, 'load-more')]",
                
                # Common variations
                "//button[contains(text(), 'View More')]",
                "//a[contains(text(), 'View More')]",
                "//button[contains(text(), 'See More')]",
                "//a[contains(text(), 'See More')]",
                
                # Icon + text combinations
                "//button[.//i[contains(@class, 'more')] or contains(text(), 'More')]",
                
                # Language variations
                "//button[contains(text(), 'More') and not(contains(text(), 'Learn'))]",  # Exclude "Learn More"
                
                # Aria label variations
                "//*[@aria-label='Load more']",
                "//*[@aria-label='Show more']"
            ]
            
            for pattern in load_more_patterns:
                try:
                    #print(pattern)
                    """
                    button = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, pattern))
                    )
                    """
                    button = self.driver.find_element(By.XPATH, pattern)

                    # Try to scroll to button
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                    time.sleep(4)
                    
                    # Try to click
                    try:
                        button.click()
                    except ElementClickInterceptedException:
                        self.driver.execute_script("arguments[0].click();", button)
                    
                    # Wait for new content
                    time.sleep(6)
                    return True
                    
                except Exception as e:
                    continue
            
            return False  # No button found
            
        except Exception as e:
            print(f"Error in load more: {str(e)}")
            return False
        
    def handle_pagination(self):
        """Handle numbered pagination and return True if successfully navigated to next page"""
        
        try:
            # Try different patterns for next button container
            next_patterns = [
                # Original pattern
                "//li[contains(translate(@class, 'PAGE', 'page'), 'page') and contains(translate(@class, 'NEXT', 'next'), 'next')]",
                
                # Common icon patterns
                "//li//a//span[contains(@class, 'glyphicon-menu-right')]/..",  # Go up to <a>
                "//li//span[contains(@class, 'arrow-right') or contains(@class, 'next-arrow')]/..",
                "//li//i[contains(@class, 'fa-chevron-right') or contains(@class, 'fa-arrow-right')]/..",
                
                # Screen reader patterns
                "//li//span[contains(@class, 'sr-only') and contains(text(), 'Next')]/../..",
                "//li//span[@aria-label='Next']/..",
                
                # General next patterns
                "//li//a[contains(@href, 'page=') and descendant::*[contains(@class, 'next') or contains(@class, 'right')]]",
                "//li//a[contains(@href, 'page=') and (contains(@rel, 'next') or contains(@aria-label, 'Next'))]"
            ]
            
            # Try each pattern
            for pattern in next_patterns:
                try:
                    next_element = self.driver.find_element(By.XPATH, pattern)
                    
                    # If we found an anchor directly, use it
                    if next_element.tag_name == 'a':
                        clickable = next_element
                    else:
                        # Otherwise look for button or anchor inside
                        try:
                            clickable = next_element.find_element(By.TAG_NAME, 'button')
                        except:
                            try:
                                clickable = next_element.find_element(By.TAG_NAME, 'a')
                            except:
                                continue
                    
                    # Rest of clicking logic remains the same
                    current_url = self.driver.current_url
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", clickable)
                    time.sleep(0.5)
                    
                    try:
                        clickable.click()
                    except ElementClickInterceptedException:
                        self.driver.execute_script("arguments[0].click();", clickable)
                    
                    WebDriverWait(self.driver, 5).until(
                        lambda driver: driver.current_url != current_url
                    )
                    
                    return True
                    
                except NoSuchElementException:
                    continue
                
            return False
                
        except Exception as e:
            return False
        
        
    def _process_page_content(self, max_attempts, news_groups):
        """Helper function to process page content with pagination/load more"""
        # Get initial group
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        initial_group = self.find_news_group(soup)
        
        if initial_group is not None:
            # Check for client-side pagination
            anchor_list = initial_group['a'].iloc[0]
            total_anchors = len(anchor_list)
            
            if total_anchors > 0:
                hidden_count = sum(1 for anchor in anchor_list if self._is_element_hidden(anchor))
                hidden_ratio = hidden_count / total_anchors
                
                if hidden_ratio > 0.6:
                    print(f"Detected client-side pagination. {hidden_count}/{total_anchors} links are hidden.")
                    self.client_side_pagination = True
                    news_groups.append(initial_group)
                    return news_groups
            
            # If not client-side pagination, proceed with regular pagination
            news_groups.append(initial_group)
        
        # Try loading more
        attempts = 0
        while attempts < max_attempts:
            
            
            if self.handle_load_more():
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                group = self.find_news_group(soup)
                if group is not None:
                    news_groups.append(group)
                attempts += 1
                continue
            
            if self.handle_pagination():
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                group = self.find_news_group(soup)
                if group is not None:
                    news_groups.append(group)
                attempts += 1
                continue
            
            break
        
        return news_groups
                

        
    def find_all_news_groups(self, max_attempts=0):
        """    
        Discover all news article URLs from a corporate press release page.
    
        Handles multiple pagination scenarios:
        - Year-based filtering with dropdown selectors
        - Load more buttons and infinite scroll
        - Numbered pagination
        - Client-side pagination (hidden elements)
        
        Args:
            max_attempts (int): Maximum pagination attempts per section
            
        Returns:
            list: List of DataFrames containing discovered news groups with URLs
            
        Raises:
            Exception: If unable to bypass site protection or critical errors occur
        """
        try:
            self.driver.get(self.base_url)
            
            # Handle Cloudflare if present
            if not self._handle_cloudflare():
                raise Exception("Could not bypass protection")
                
            news_groups = []
            
            # Check for year selector
            selector, has_all = self._find_year_selector()
            
            # Scenario 1: No year selector - proceed with original logic
            if not selector:
                return self._process_page_content(max_attempts, news_groups)
                
            # Scenario 2: Year selector with "All" option
            if has_all:
                if self._select_year():  # Select "All" option
                    return self._process_page_content(max_attempts, news_groups)
                else:
                    print("Failed to select 'All' option")
                    return news_groups
            
            # Scenario 3: Year selector without "All" option
            years = self._get_year_options()
            if not years:
                print("Failed to get year options")
                return news_groups
                
            # Process each year
            for year in years:
                year_text = year.strip()
                if len(year_text) == 4 and year_text.isdigit():  # Only process numeric years
                    print(f"Processing year: {year_text}")
                    if self._select_year(year_text):
                        # Process all content for this year
                        self._process_page_content(max_attempts, news_groups)
                        if self.client_side_pagination:
                            print("Client-side pagination detected. Breaking year selection loop.")
                            break
                        
            return news_groups
            
        except Exception as e:
            raise Exception(f"Error finding all news groups: {str(e)}")
        
        finally:
            if self.driver:
                self.driver.quit()
     



if __name__ == "__main__":
    # Example usage
    press_release_url = "https://news.archer.com/"
    finder = NewsGroupFinder(press_release_url)
    news_groups = finder.find_all_news_groups()
    
    if news_groups:
        all_urls = []
        for group in news_groups:
            all_urls.extend(group['urls'].iloc[0])
        print(f"Successfully extracted {len(all_urls)} news article URLs")
    else:
        print("No news groups found")
