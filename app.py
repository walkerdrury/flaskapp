from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
import logging
import time

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_url(url, headers=None, retries=3, backoff_factor=0.3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(backoff_factor * (2 ** attempt))
    return None

@app.route('/api/events', methods=['GET'])
def get_events():
    try:
        url = 'https://streamed.su'
        
        # Define custom headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/129.0.0.0 Safari/537.36'
        }
        
        # Fetch the URL with retries
        response = fetch_url(url, headers=headers)
        
        if not response:
            logger.error("Failed to retrieve the webpage after multiple attempts.")
            return jsonify({"error": "Failed to retrieve the webpage."}), 500

        # Parse the HTML content
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a')
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return jsonify({"error": "Failed to parse the webpage content."}), 500

        # Extract href attributes
        hrefs = [link.get('href') for link in links if link.get('href')]
        filtered_hrefs = []
        for href in hrefs:
            if href.startswith('/watch/'):
                try:
                    filtered_hrefs.append(href.split('/watch/')[1])
                except IndexError:
                    logger.warning(f"Unexpected href format: {href}")
                    continue

        names = list(set(filtered_hrefs))
        logger.info(f"Fetched {len(names)} events.")
        return jsonify(names), 200

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/')
def home():
    return "Hello, Heroku!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
