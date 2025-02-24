import os
import csv
import logging
import time
import random
from typing import Dict, Optional, Tuple
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LinkedInScraper:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.proxyscrape_url = "https://api.proxyscrape.com/v2/"
        self.consecutive_failures = 0
        self.current_proxy = None
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        """Initialize the Chrome WebDriver with proxy settings"""
        logger.info("Setting up Chrome WebDriver")
        chrome_options = Options()
        # Remove headless option to display the browser
        # chrome_options.add_argument('--headless')  # Commented out for debugging
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        if self.current_proxy:
            chrome_options.add_argument(f'--proxy-server={self.current_proxy}')
        
        if self.driver:
            self.driver.quit()
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)

    def validate_proxy(self) -> bool:
        """Validate the current proxy by making a request to a known site"""
        try:
            response = requests.get("http://httpbin.org/ip", proxies={"http": self.current_proxy, "https": self.current_proxy}, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Proxy validation failed: {str(e)}")
            return False

    def get_new_proxy(self) -> bool:
        """Fetch a new proxy from ProxyScrape API"""
        try:
            logger.info("Requesting new proxy from ProxyScrape")
            response = requests.get(
                f"{self.proxyscrape_url}?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&simplified=true&api_key={self.api_key}"
            )
            
            if response.status_code == 200:
                proxy = response.text.strip()
                logger.info(f"New proxy obtained: {proxy}")
                self.current_proxy = proxy
                
                # Validate the new proxy before setting it up
                if self.validate_proxy():
                    self.setup_driver()
                    return True
                else:
                    logger.error("New proxy is not valid.")
                    return False
            else:
                logger.error(f"Failed to get proxy. Status code: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error getting new proxy: {str(e)}")
            return False

    def extract_profile_info(self, profile_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract name and location from LinkedIn profile"""
        attempts = 0
        max_attempts = 5  # Set a maximum number of attempts

        while attempts < max_attempts:
            try:
                logger.info(f"Attempting to extract info from: {profile_url}")
                self.driver.get(profile_url)
                
                # Wait for the main content to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )

                # Pause to allow inspection of the page
                logger.info("Page loaded. Pausing for inspection...")
                time.sleep(10)  # Pause for 10 seconds (adjust as needed)

                # Check for Chrome error page
                if "error" in self.driver.title.lower() or "not found" in self.driver.page_source.lower():
                    logger.warning("Encountered a Chrome error page, switching proxy and retrying")
                    self.consecutive_failures += 1
                    if self.get_new_proxy():
                        attempts += 1  # Increment attempts
                        continue  # Retry with new proxy
                    return None, None

                # Check for login wall
                if "login" in self.driver.current_url or "authwall" in self.driver.current_url:
                    logger.warning("Hit login wall, switching proxy and retrying")
                    self.consecutive_failures += 1
                    if self.get_new_proxy():
                        attempts += 1  # Increment attempts
                        continue  # Retry with new proxy
                    return None, None

                # Check if the page is valid before extracting
                if "linkedin" not in self.driver.current_url:
                    logger.warning("Not on a LinkedIn profile page, switching proxy and retrying")
                    self.consecutive_failures += 1
                    if self.get_new_proxy():
                        attempts += 1  # Increment attempts
                        continue  # Retry with new proxy
                    return None, None

                # Extract name and location
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # You can inspect the page here and provide the correct selectors
                name_element = soup.find('h1', {'class': 'text-heading-xlarge'})
                location_element = soup.find('span', {'class': 'text-body-small'})

                name = name_element.text.strip() if name_element else None
                location = location_element.text.strip() if location_element else None

                if name is None or location is None:
                    logger.warning("Name or location extraction returned None, switching proxy and retrying")
                    self.consecutive_failures += 1
                    if self.get_new_proxy():
                        attempts += 1  # Increment attempts
                        continue  # Retry with new proxy
                    return None, None

                logger.info(f"Successfully extracted - Name: {name}, Location: {location}")
                self.consecutive_failures = 0
                return name, location

            except Exception as e:
                logger.error(f"Error extracting profile info: {str(e)}")
                self.consecutive_failures += 1
                attempts += 1  # Increment attempts

        logger.error("Max attempts reached. Unable to extract profile info.")
        return None, None

    def process_profiles(self, csv_file: str):
        """Process LinkedIn profiles from CSV file"""
        try:
            with open(csv_file, 'r') as file:
                reader = csv.DictReader(file)
                rows = list(reader)

            with open(csv_file, 'w', newline='') as file:
                fieldnames = ['first_name', 'last_name', 'geo', 'prooflink', 'IP change']
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()

                # Only process the first profile
                if rows:
                    profile_url = rows[0]['prooflink']
                    
                    if not profile_url:
                        logger.warning("No profile URL found.")
                        return

                    logger.info(f"Processing profile: {profile_url}")
                    
                    # Check if we need to rotate proxy
                    if self.consecutive_failures >= 5:
                        logger.warning("5 consecutive failures - rotating proxy")
                        self.get_new_proxy()
                        rows[0]['IP change'] = 'rotation'
                        self.consecutive_failures = 0
                    
                    name, location = self.extract_profile_info(profile_url)
                    
                    if name:
                        name_parts = name.split(' ', 1)
                        rows[0]['first_name'] = name_parts[0]
                        rows[0]['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
                    
                    if location:
                        rows[0]['geo'] = location
                    
                    writer.writerow(rows[0])
                    
                    # Add random delay between requests
                    time.sleep(random.uniform(2, 5))

        except Exception as e:
            logger.error(f"Error processing profiles: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()

def main():
    # get api key from .env
    api_key = os.getenv("PROXYSCRAPE_API_KEY")
    csv_file = "ProfilesListExample.csv"
    
    scraper = LinkedInScraper(api_key)
    scraper.process_profiles(csv_file)

if __name__ == "__main__":
    main() 