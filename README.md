# LinkedIn Profile Scraper

A Python script that scrapes LinkedIn profiles using proxy rotation to avoid rate limiting and authentication walls.

## Features

- Automated LinkedIn profile data extraction
- Proxy rotation using ProxyScrape API
- Detailed logging for debugging and monitoring
- CSV file handling for input/output
- Automatic IP rotation after 5 consecutive failures
- Random delays between requests to avoid detection

## Requirements

- Python 3.7+
- Chrome browser installed
- ChromeDriver (compatible with your Chrome version)

## Installation

1. Clone this repository
2. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Ensure your CSV file follows the format:
   - first_name
   - last_name
   - geo
   - prooflink
   - IP change

2. Run the script:
```bash
python linkedin_scraper.py
```

## Configuration

- The script uses maximum logging level for debugging
- Proxy rotation occurs after 5 consecutive authentication walls
- Random delays (2-5 seconds) between requests
- Headless browser mode enabled by default

## Notes

- The script handles CAPTCHA by rotating IPs
- All activities are logged in `scraper.log`
- The CSV file is updated in place with the scraped information