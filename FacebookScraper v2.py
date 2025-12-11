#!/usr/bin/env python
# coding: utf-8

# In[3]:


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import time
import random
import json
import re
from datetime import datetime, timedelta

class FacebookScraper:
    def __init__(self, email, password, max_post_age_days=730):
        self.email = email
        self.password = password
        self.driver = None
        self.last_height = 0
        self.scroll_attempts = 0
        self.max_scroll_attempts = 8
        self.max_post_age_days = max_post_age_days  # 730 days = 2 years by default
        
    def initialize_driver(self):
        """Initialize the Edge webdriver with custom options"""
        options = webdriver.EdgeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        self.driver = webdriver.Edge(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def simulate_human_typing(self, element, text):
        """Simulate human-like typing patterns"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))
            if random.random() < 0.1:
                time.sleep(random.uniform(0.3, 0.7))
                
    def login(self):
        """Login to Facebook"""
        self.driver.get("https://www.facebook.com/login")
        
        email_input = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        self.simulate_human_typing(email_input, self.email)
        
        password_input = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "pass"))
        )
        self.simulate_human_typing(password_input, self.password)
        
        login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
        ActionChains(self.driver)            .move_to_element(login_button)            .pause(random.uniform(0.2, 0.4))            .click()            .perform()
            
        time.sleep(15)
        
    def navigate_to_profile(self, profile_url):
        """Navigate to a specific Facebook profile or page"""
        self.driver.get(profile_url)
        time.sleep(random.uniform(4, 6))
    
    def navigate_to_page(self, page_url):
        """Alias for navigate_to_profile"""
        return self.navigate_to_profile(page_url)
        
    def click_see_more_buttons(self):
        """Click all 'See More' buttons to expand truncated posts"""
        try:
            see_more_selectors = [
                "//div[contains(@class, 'x1i10hfl') and (contains(text(), 'voir plus') or contains(text(), 'See more') or contains(text(), 'En voir plus'))]",
                "//div[@role='button' and (contains(text(), 'voir plus') or contains(text(), 'See more'))]",
                "//span[contains(text(), 'voir plus') or contains(text(), 'See more')]"
            ]
            
            for selector in see_more_selectors:
                try:
                    buttons = self.driver.find_elements(By.XPATH, selector)
                    for button in buttons[:5]:
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                            time.sleep(random.uniform(0.3, 0.6))
                            self.driver.execute_script("arguments[0].click();", button)
                            time.sleep(random.uniform(0.5, 1))
                        except:
                            continue
                except:
                    continue
        except:
            pass
    
    def smart_scroll(self):
        """Improved scrolling with detection of page end"""
        current_height = self.driver.execute_script("return document.body.scrollHeight")
        
        if current_height == self.last_height:
            self.scroll_attempts += 1
        else:
            self.scroll_attempts = 0
            self.last_height = current_height
        
        if self.scroll_attempts >= self.max_scroll_attempts:
            print("Reached end of page or no new content loading.")
            return False
        
        scroll_amount = random.randint(400, 700)
        self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(2, 4))
        
        self.click_see_more_buttons()
        return True
    
    def clean_text(self, text):
        """Clean extracted text from noise and artifacts"""
        if not text:
            return None
        
        # Remove weird domain patterns like "puNokSLc.com", "uDScu3WQv.comAli"
        text = re.sub(r'\b[a-zA-Z0-9]{5,15}\.com(?:Ali)?', '', text)
        
        # Remove all Learn More patterns (multiple variations)
        text = re.sub(r'-+L-*e-*a-*r-*n-*-*M-*o-*r-*e-*-+', '', text)
        text = re.sub(r'-+L-+-+e-*a-*r-*-*n-+-+M-+-+o-*r-*e-+-+', '', text)
        
        # Remove Facebook auto-translation - keep only the dominant language part
        # Method 1: Split by common translation patterns
        if re.search(r'[A-Za-z]{20,}.*[\u0600-\u06FF]{10,}', text) or re.search(r'[\u0600-\u06FF]{10,}.*[A-Za-z]{20,}', text):
            # Mixed French/English and Arabic - split and keep longest
            parts = re.split(r'\s{2,}', text)  # Split by multiple spaces
            if len(parts) > 1:
                # Keep the longest part
                text = max(parts, key=len).strip()
        
        # Remove button texts that got mixed in
        button_patterns = [
            r'J\'aime\s+Commenter\s+Partager',
            r'\b(J\'aime|Commenter|Partager)\s+\1+',
            r'\d+\s+commentaires\s+\d+\s+partages\s+J\'aime',
        ]
        for pattern in button_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove excessive dashes and underscores
        text = re.sub(r'-{2,}', '', text)
        text = re.sub(r'_{2,}', '', text)
        
        # Clean multiple spaces and trim
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def is_post_within_age_limit(self, time_str):
        """Check if post is within the age limit (default: 2 years)"""
        if not time_str:
            # If no timestamp, we can't determine age, so include it
            return True
        
        time_str = time_str.lower().strip()
        
        try:
            # Parse different time formats
            # Minutes
            if 'min' in time_str:
                return True
            
            # Hours
            elif 'h' in time_str or 'heure' in time_str:
                return True
            
            # Days/Jours
            elif 'jour' in time_str or 'day' in time_str or 'j' == time_str[-1]:
                match = re.search(r'(\d+)', time_str)
                if match:
                    days = int(match.group(1))
                    return days <= self.max_post_age_days
                return True
            
            # Weeks/Semaines
            elif 'semaine' in time_str or 'week' in time_str or 'sem' in time_str:
                match = re.search(r'(\d+)', time_str)
                if match:
                    weeks = int(match.group(1))
                    days = weeks * 7
                    return days <= self.max_post_age_days
                return True
            
            # Months/Mois
            elif 'mois' in time_str or 'month' in time_str or 'mo' in time_str:
                match = re.search(r'(\d+)', time_str)
                if match:
                    months = int(match.group(1))
                    days = months * 30  # Approximate
                    return days <= self.max_post_age_days
                return True
            
            # Years/Ans/Années
            elif 'an' in time_str or 'year' in time_str or 'yr' in time_str:
                match = re.search(r'(\d+)', time_str)
                if match:
                    years = int(match.group(1))
                    days = years * 365
                    return days <= self.max_post_age_days
                # If it mentions years without a number, assume it's too old
                return False
            
            # Yesterday/Hier
            elif 'hier' in time_str or 'yesterday' in time_str:
                return True
            
            # If we can't parse it, include it to be safe
            return True
            
        except Exception as e:
            # If there's any error parsing, include the post
            return True if text and len(text) > 5 else None
    
    def clean_metadata(self, text, field_type):
        """Clean metadata fields (likes, comments, shares, time)"""
        if not text:
            return None
        
        # Remove noise characters
        text = re.sub(r'-+', '', text)
        text = re.sub(r'_+', '', text)
        text = text.strip()
        
        if field_type == "time":
            # Extract actual time patterns only
            time_match = re.search(r'(\d+\s*(h|min|jour|semaine|mois|an|day|week|month|year)s?|hier|yesterday)', text, re.IGNORECASE)
            if time_match:
                # Normalize format: ensure space between number and unit
                time_str = time_match.group(1)
                time_str = re.sub(r'(\d+)([a-z])', r'\1 \2', time_str, flags=re.IGNORECASE)
                return time_str
            return None
        
        elif field_type == "comments":
            # Extract number of comments - strict filtering
            match = re.search(r'(\d+)\s*commentaires?', text, re.IGNORECASE)
            if match:
                count = int(match.group(1))
                # Facebook posts realistically have < 5000 comments on most pages
                # Values like 16512, 26010 are clearly IDs
                if count > 5000:
                    return None
                return match.group(1) + " commentaires"
            return None
        
        elif field_type == "shares":
            # Extract number of shares, ignore "Partager" button
            if text.lower() == "partager" or text.lower() == "share":
                return None
            match = re.search(r'(\d+)\s*partages?', text, re.IGNORECASE)
            if match:
                count = int(match.group(1))
                # Similar validation for shares
                if count > 10000:
                    return None
                return match.group(1) + " partages"
            return None
        
        elif field_type == "likes":
            # Clean likes - extract only if it contains numbers
            if "réaction" in text.lower() and any(char.isdigit() for char in text):
                match = re.search(r'(\d+(?:\s*[kK])?)\s*réaction', text)
                if match:
                    return match.group(1) + " réactions"
            return None
        
        return text
        
    def extract_posts_with_bs(self):
        """Extract posts data using BeautifulSoup with improved selectors"""
        page_source = self.driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        posts_data = []
        
        # Find post containers
        posts = soup.find_all("div", {"class": "x1yztbdb x1n2onr6 xh8yej3 x1ja2u2z"})
        if not posts:
            posts = soup.find_all("div", {"class": "x1n2onr6 x1ja2u2z"})
        
        print(f"Found {len(posts)} post containers on page")
        
        for post in posts:
            try:
                # Extract raw data
                post_text = self.extract_post_text(post)
                likes = self.extract_likes(post)
                comments = self.extract_comments(post)
                shares = self.extract_shares(post)
                post_time = self.extract_time(post)
                
                # Clean all extracted data
                post_text = self.clean_text(post_text)
                likes = self.clean_metadata(likes, "likes")
                comments = self.clean_metadata(comments, "comments")
                shares = self.clean_metadata(shares, "shares")
                post_time = self.clean_metadata(post_time, "time")
                
                # Check if post is within age limit
                if not self.is_post_within_age_limit(post_time):
                    print(f"⏰ Skipping post older than {self.max_post_age_days} days: {post_time}")
                    continue
                
                # Only add if we have meaningful content
                if post_text and len(post_text) > 15:
                    posts_data.append({
                        "post_text": post_text,
                        "likes": likes,
                        "comments": comments,
                        "shares": shares,
                        "post_time": post_time
                    })
            except Exception as e:
                continue
                
        return posts_data
    
    def extract_post_text(self, post):
        """Extract post text with multiple fallback methods"""
        text = ""
        
        # Method 1: data-ad-preview="message"
        message_elements = post.find_all("div", {"data-ad-preview": "message"})
        if message_elements:
            text = " ".join([msg.get_text(separator=" ", strip=True) for msg in message_elements])
        
        # Method 2: data-ad-comet-preview="message"
        if not text:
            content_div = post.find("div", {"data-ad-comet-preview": "message"})
            if content_div:
                text = content_div.get_text(separator=" ", strip=True)
        
        # Method 3: Look for main text content divs
        if not text:
            text_divs = post.find_all("div", {"dir": "auto", "style": lambda x: x and "text-align" in x if x else False})
            if text_divs:
                text = " ".join([div.get_text(separator=" ", strip=True) for div in text_divs[:3]])
        
        return text if text else None
    
    def extract_likes(self, post):
        """Extract likes count"""
        try:
            # Look for spans that contain reaction counts
            all_text = post.get_text()
            
            # Pattern: "35 réactions" or "1 réaction"
            match = re.search(r'(\d+(?:\s*[kK])?)\s*réactions?', all_text, re.IGNORECASE)
            if match:
                return match.group(0)
            
            # Alternative: aria-label with reactions
            reaction_divs = post.find_all("div", {"aria-label": lambda x: x and "réaction" in x.lower() if x else False})
            for div in reaction_divs:
                label = div.get("aria-label", "")
                match = re.search(r'\d+', label)
                if match:
                    return match.group(0) + " réactions"
        except:
            pass
        return None
    
    def extract_comments(self, post):
        """Extract comments count with improved validation"""
        try:
            all_text = post.get_text()
            
            # Find all comment counts in the post
            matches = re.findall(r'(\d+)\s*commentaires?', all_text, re.IGNORECASE)
            if matches:
                # Convert to integers
                counts = [int(m) for m in matches]
                
                # Filter strategy:
                # 1. Remove obviously wrong values (>10000 are usually IDs)
                # 2. If multiple values remain, pick the smallest (most conservative)
                valid_counts = [c for c in counts if c <= 10000]
                
                if valid_counts:
                    # Use the smallest valid count
                    count = min(valid_counts)
                    return f"{count} commentaires"
                elif counts:
                    # If all are large, there might be a lot of comments
                    # But cap at reasonable limit
                    count = min(counts)
                    if count > 10000:
                        # Likely an ID, return None
                        return None
                    return f"{count} commentaires"
        except:
            pass
        return None
    
    def extract_shares(self, post):
        """Extract shares count"""
        try:
            all_text = post.get_text()
            
            # Pattern: "35 partages" or "1 partage"
            match = re.search(r'(\d+)\s*partages?', all_text, re.IGNORECASE)
            if match:
                return match.group(0)
        except:
            pass
        return None
    
    def extract_time(self, post):
        """Extract post timestamp"""
        try:
            # Find all links (timestamps are usually in links)
            time_links = post.find_all("a")
            for link in time_links:
                text = link.get_text(strip=True)
                # Check if it matches time patterns
                if re.search(r'\d+\s*(h|min|jour|semaine|mois)', text, re.IGNORECASE):
                    return text
                if text.lower() in ['hier', 'yesterday']:
                    return text
            
            # Fallback: search in all text
            all_spans = post.find_all("span")
            for span in all_spans:
                text = span.get_text(strip=True)
                if re.match(r'^\d+\s*(h|min)$', text, re.IGNORECASE):
                    return text
        except:
            pass
        return None
        
    def remove_duplicates(self, data_list):
        """Remove duplicate posts based on text content"""
        seen = set()
        unique_data = []
        for data in data_list:
            identifier = data.get("post_text", "")
            if identifier and identifier not in seen:
                seen.add(identifier)
                unique_data.append(data)
        return unique_data
        
    def scrape_posts(self, max_posts):
        """Scrape a specified number of posts"""
        all_posts = []
        no_new_posts_count = 0
        max_no_new_attempts = 20
        total_iterations = 0
        max_iterations = max_posts * 3  # Safety limit
        old_posts_count = 0  # Track posts rejected due to age
        
        print(f"Starting to scrape up to {max_posts} posts (max age: {self.max_post_age_days} days / ~{self.max_post_age_days/365:.1f} years)...")
        
        while len(all_posts) < max_posts and total_iterations < max_iterations:
            total_iterations += 1
            previous_count = len(all_posts)
            previous_old_count = old_posts_count
            
            posts = self.extract_posts_with_bs()
            all_posts.extend(posts)
            all_posts = self.remove_duplicates(all_posts)
            
            current_count = len(all_posts)
            new_posts = current_count - previous_count
            
            print(f"Extracted {current_count} unique posts so far (+{new_posts} new)")
            
            if new_posts == 0:
                no_new_posts_count += 1
                print(f"No new posts found. Attempt {no_new_posts_count}/{max_no_new_attempts}")
            else:
                no_new_posts_count = 0
            
            if no_new_posts_count >= max_no_new_attempts:
                print(f"No new posts found after {max_no_new_attempts} attempts. Stopping.")
                break
            
            if len(all_posts) >= max_posts:
                print(f"✅ Reached target of {max_posts} posts!")
                break
            
            if not self.smart_scroll():
                print("Reached end of scrollable content.")
                # Reset scroll attempts and try a few more times
                self.scroll_attempts = 0
                time.sleep(random.uniform(2, 3))
                if not self.smart_scroll():
                    break
            
            time.sleep(random.uniform(1, 2))
        
        print(f"\n🎯 Scraping completed: {len(all_posts)} posts extracted within age limit")
        return all_posts[:max_posts]

    def print_posts(self, posts_data):
        """Print the scraped posts data with better formatting"""
        print("\n" + "="*70)
        print(f"📊 FINAL RESULTS: {len(posts_data)} POSTS")
        print("="*70 + "\n")
        
        for idx, post in enumerate(posts_data, start=1):
            print(f"📝 Post {idx}:")
            
            # Display text (truncate if too long)
            text = post['post_text']
            if text and len(text) > 200:
                print(f"   Text: {text[:200]}...")
            else:
                print(f"   Text: {text or 'N/A'}")
            
            print(f"    Likes: {post['likes'] or 'N/A'}")
            print(f"    Comments: {post['comments'] or 'N/A'}")
            print(f"    Shares: {post['shares'] or 'N/A'}")
            print(f"    Time: {post['post_time'] or 'N/A'}")
            print("-" * 70)
    
    def save_to_json(self, posts_data, filename="facebook_posts.json"):
        """Save scraped data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(posts_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Data saved to {filename}")
    
    def get_statistics(self, posts_data):
        """Calculate statistics about scraped data"""
        if not posts_data:
            return None
            
        stats = {
            "total_posts": len(posts_data),
            "posts_with_likes": sum(1 for p in posts_data if p.get("likes")),
            "posts_with_comments": sum(1 for p in posts_data if p.get("comments")),
            "posts_with_shares": sum(1 for p in posts_data if p.get("shares")),
            "posts_with_time": sum(1 for p in posts_data if p.get("post_time")),
            "avg_text_length": sum(len(p.get("post_text", "")) for p in posts_data) / len(posts_data)
        }
        return stats
    
    def print_statistics(self, posts_data):
        """Print statistics about scraped data"""
        stats = self.get_statistics(posts_data)
        if not stats:
            return
            
        print("\n" + "="*70)
        print("📈 SCRAPING STATISTICS")
        print("="*70)
        print(f"✓ Total posts: {stats['total_posts']}")
        print(f"✓ Posts with likes: {stats['posts_with_likes']} ({stats['posts_with_likes']/stats['total_posts']*100:.1f}%)")
        print(f"✓ Posts with comments: {stats['posts_with_comments']} ({stats['posts_with_comments']/stats['total_posts']*100:.1f}%)")
        print(f"✓ Posts with shares: {stats['posts_with_shares']} ({stats['posts_with_shares']/stats['total_posts']*100:.1f}%)")
        print(f"✓ Posts with timestamp: {stats['posts_with_time']} ({stats['posts_with_time']/stats['total_posts']*100:.1f}%)")
        print(f"✓ Average text length: {stats['avg_text_length']:.0f} characters")
        print("="*70 + "\n")
            
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()

# Example usage
if __name__ == "__main__":
    # Initialize the scraper with 2-year limit (730 days)
    # You can change max_post_age_days to any value:
    # - 365 for 1 year
    # - 730 for 2 years (default)
    # - 90 for 3 months
    scraper = FacebookScraper("anass.oumouli@edu.uiz.ac.ma", "Anass@12345", max_post_age_days=730)
    
    try:
        scraper.initialize_driver()
        scraper.login()
        
        scraper.navigate_to_page("https://web.facebook.com/groups/1529125351399435/")
        
        posts_data = scraper.scrape_posts(max_posts=5000)
        
        scraper.print_posts(posts_data)
        scraper.print_statistics(posts_data)
        scraper.save_to_json(posts_data)
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


# In[ ]:




