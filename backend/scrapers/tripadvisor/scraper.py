"""
TripAdvisor COMPLETE Scraper - PRODUCTION VERSION
=================================================
Extracts ALL data from TripAdvisor reviews:
- Username
- Country/Nationality (KEY FEATURE!)
- Rating (1-5 bubbles)
- Review Text
- Date

Usage:
    python scraper.py <tripadvisor_url> [max_reviews]

Example:
    python scraper.py "https://www.tripadvisor.com/Restaurant_Review-g295371-d735117-Reviews-Nautika-Dubrovnik.html" 500

Output:
    CSV file with all review data
"""

try:
    import undetected_chromedriver as uc
except ImportError:
    print("ERROR: undetected-chromedriver not installed!")
    print("Run: pip install undetected-chromedriver")
    exit(1)

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import time
import random
import os
import sys
from datetime import datetime
import re


class TripAdvisorScraper:
    def __init__(self, base_url, max_reviews=500, headless=True):
        """
        Complete scraper with all fields including nationality
        Optimized for better speed

        Args:
            base_url: TripAdvisor restaurant URL
            max_reviews: Maximum reviews to scrape
            headless: Run in headless mode (required for servers)
        """
        self.base_url = base_url
        self.max_reviews = max_reviews
        self.reviews = []
        self.start_time = time.time()
        self.main_window = None
        self.location_cache = {}

        # Initialize undetected Chrome
        options = uc.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

        if headless:
            options.add_argument('--headless=new')
        else:
            options.add_argument('--start-maximized')

        options.add_argument('--disable-images')
        options.add_argument('--blink-settings=imagesEnabled=false')

        print("Initializing browser...")
        self.driver = uc.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 15)
        self.main_window = self.driver.current_window_handle
        print("Browser ready\n")

    def human_delay(self, min_s=2, max_s=4):
        """Human-like delays"""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)

    def quick_scroll(self):
        """Quick scrolling"""
        total_height = self.driver.execute_script("return document.body.scrollHeight")
        current = 0

        while current < total_height:
            scroll = random.randint(500, 800)
            current += scroll
            self.driver.execute_script(f"window.scrollTo(0, {current});")
            time.sleep(random.uniform(0.2, 0.4))

    def accept_cookies(self):
        """Accept cookies"""
        try:
            print("Checking for cookies...")
            time.sleep(random.uniform(1, 2))

            cookie_btn = self.wait.until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            )
            cookie_btn.click()
            print("Cookies accepted\n")
            self.human_delay(1, 2)
        except TimeoutException:
            print("No cookie popup\n")

    def close_ad_popup(self):
        """Close advertisement popup"""
        try:
            print("Checking for ads...")
            time.sleep(random.uniform(1, 2))

            close_selectors = [
                "button[aria-label='Close']",
                "button[class*='close']",
                "div[role='button'][aria-label='Close']",
                "svg[class*='close']",
                "[data-testid='close-button']"
            ]

            for selector in close_selectors:
                try:
                    close_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if close_btn.is_displayed():
                        close_btn.click()
                        print("Ad popup closed\n")
                        self.human_delay(1, 2)
                        return
                except:
                    continue

            print("No ad popup found\n")
        except Exception as e:
            print(f"No ads: {e}\n")

    def extract_rating(self, review_elem):
        """Extract rating from bubble element"""
        try:
            bubble = review_elem.find_element(By.CSS_SELECTOR, "svg.UctUV[aria-label]")
            aria = bubble.get_attribute('aria-label')
            match = re.search(r'(\d+\.?\d*)\s*of\s*5', aria)
            if match:
                return float(match.group(1))
        except:
            pass
        return None

    def extract_date(self, review_elem):
        """Extract review date"""
        try:
            date_elem = review_elem.find_element(By.CSS_SELECTOR, "div.biGQs._P.pZUbB.ncFvv.osNWb")
            date_text = date_elem.text

            if 'wrote a review' in date_text.lower():
                date_match = re.search(r'(\w+\s+\d{4})', date_text)
                if date_match:
                    return date_match.group(1)
        except:
            pass
        return None

    def extract_username(self, review_elem):
        """Extract username"""
        try:
            username_elem = review_elem.find_element(By.CSS_SELECTOR, "a.BMQDV._F.G-.wSSLS.SwZTJ.FGwzt")
            return username_elem.text
        except:
            pass
        return "Anonymous"

    def extract_review_text(self, review_elem):
        """Extract full review text"""
        try:
            text_container = review_elem.find_element(By.CSS_SELECTOR, "div.biGQs._P.pZUbB.KxBGd")

            try:
                read_more = text_container.find_element(By.CSS_SELECTOR, "button span")
                if 'Read more' in read_more.text or 'more' in read_more.text.lower():
                    read_more.click()
                    time.sleep(0.5)
            except:
                pass

            return text_container.text
        except:
            pass
        return ""

    def get_user_location_fast(self, review_elem):
        """Extract user location - FAST VERSION"""
        try:
            contrib_elem = review_elem.find_element(By.CSS_SELECTOR, "div.biGQs._P.pZUbB.osNWb")
            text = contrib_elem.text

            if ' contribution' in text.lower():
                lines = text.split('\n')
                for line in lines:
                    if ' contribution' not in line.lower():
                        location = line.strip()
                        if location and len(location) > 2:
                            return location
        except:
            pass

        # Try profile link method
        try:
            profile_link = review_elem.find_element(By.CSS_SELECTOR, "a.BMQDV._F.G-.wSSLS.SwZTJ.FGwzt")
            href = profile_link.get_attribute('href')

            if href and href in self.location_cache:
                return self.location_cache[href]

            if href:
                self.driver.execute_script("window.open(arguments[0], '_blank');", href)
                time.sleep(0.3)

                windows = self.driver.window_handles
                if len(windows) > 1:
                    self.driver.switch_to.window(windows[-1])

                    try:
                        location_elem = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "span.default-typography_heading-s__fuO7P"))
                        )
                        location = location_elem.text
                        self.location_cache[href] = location
                        return location
                    except:
                        pass
                    finally:
                        self.driver.close()
                        self.driver.switch_to.window(self.main_window)
        except:
            pass

        return "Unknown"

    def scrape_page(self):
        """Scrape reviews from current page"""
        reviews_on_page = []

        try:
            review_cards = self.driver.find_elements(By.CSS_SELECTOR, "div[data-automation='reviewCard']")

            if not review_cards:
                review_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.reviewSelector")

            print(f"  Found {len(review_cards)} reviews on page")

            for i, card in enumerate(review_cards):
                if len(self.reviews) >= self.max_reviews:
                    break

                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                    time.sleep(0.2)

                    review = {
                        'username': self.extract_username(card),
                        'location': self.get_user_location_fast(card),
                        'rating': self.extract_rating(card),
                        'date': self.extract_date(card),
                        'text': self.extract_review_text(card)
                    }

                    if review['rating'] is not None:
                        reviews_on_page.append(review)
                        total = len(self.reviews) + len(reviews_on_page)

                        if total % 10 == 0:
                            elapsed = time.time() - self.start_time
                            rate = total / (elapsed / 60) if elapsed > 0 else 0
                            print(f"    Collected: {total}/{self.max_reviews} ({rate:.1f}/min)")
                except Exception as e:
                    continue

        except Exception as e:
            print(f"  Error on page: {e}")

        return reviews_on_page

    def go_to_next_page(self):
        """Navigate to next page"""
        try:
            next_btn = self.driver.find_element(By.CSS_SELECTOR, "a.ui_button.nav.next.primary")

            if 'disabled' in next_btn.get_attribute('class'):
                return False

            next_btn.click()
            self.human_delay(2, 3)
            return True
        except:
            return False

    def run(self):
        """Main scraping loop"""
        print(f"TARGET: {self.base_url}")
        print(f"MAX REVIEWS: {self.max_reviews}")
        print("=" * 60)

        self.driver.get(self.base_url)
        self.human_delay(2, 3)

        self.accept_cookies()
        self.close_ad_popup()
        self.quick_scroll()

        page = 1
        while len(self.reviews) < self.max_reviews:
            print(f"\n--- PAGE {page} ---")

            page_reviews = self.scrape_page()
            self.reviews.extend(page_reviews)

            if len(self.reviews) >= self.max_reviews:
                print(f"\nReached target: {len(self.reviews)} reviews")
                break

            if not self.go_to_next_page():
                print("\nNo more pages")
                break

            page += 1

        # Save results
        elapsed = time.time() - self.start_time
        print(f"\n{'=' * 60}")
        print(f"COMPLETE!")
        print(f"Total reviews: {len(self.reviews)}")
        print(f"Time: {elapsed/60:.1f} minutes")
        print(f"Rate: {len(self.reviews)/(elapsed/60):.1f} reviews/min")

        self.driver.quit()
        return self.reviews

    def save_results(self, output_dir=None):
        """Save to CSV"""
        if not self.reviews:
            print("No reviews to save!")
            return None

        df = pd.DataFrame(self.reviews)

        # Extract restaurant name from URL
        name_match = re.search(r'Reviews-([^-]+)-', self.base_url)
        restaurant_name = name_match.group(1) if name_match else "restaurant"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tripadvisor_{restaurant_name}_{timestamp}.csv"

        # Save to output folder
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'output')
        os.makedirs(output_dir, exist_ok=True)

        filepath = os.path.join(output_dir, filename)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')

        print(f"\nSaved to: {filepath}")
        return filepath


def main():
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <tripadvisor_url> [max_reviews]")
        print("\nExample:")
        print('  python scraper.py "https://www.tripadvisor.com/Restaurant_Review-g295371-d735117-Reviews-Nautika-Dubrovnik.html" 500')
        sys.exit(1)

    url = sys.argv[1]
    max_reviews = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    scraper = TripAdvisorScraper(url, max_reviews, headless=False)
    scraper.run()


if __name__ == "__main__":
    main()
