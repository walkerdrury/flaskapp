from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
import logging
import time
import re
import json
import json5

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
            script_tags = soup.find_all('script')
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return jsonify({"error": "Failed to parse the webpage content."}), 500

        # Initialize variable to store the data object string
        data_str = None

        # Iterate through all script tags to find the one containing 'const data ='
        for script in script_tags:
            if script.string and 'const data =' in script.string:
                # Use regex to extract the array assigned to data
                match = re.search(r'const\s+data\s*=\s*(\[\s*{.*?}\s*\]);', script.string, re.DOTALL)
                if match:
                    data_str = match.group(1)
                    break

        if not data_str:
            logger.error("Data object not found in any <script> tags.")
            return jsonify({"error": "Data object not found."}), 500

        # Step 1: Replace 'void 0' with 'null'
        data_str_cleaned = data_str.replace('void 0', 'null')

        # Optional: Replace other JavaScript-specific syntax if necessary
        data_str_cleaned = data_str_cleaned.replace('undefined', 'null')

        # Step 3: Remove trailing commas
        data_str_cleaned = re.sub(r',\s*([}\]])', r'\1', data_str_cleaned)

        # Step 4: Parse the cleaned string using json5
        try:
            data_object = json5.loads(data_str_cleaned)
            logger.info("Successfully parsed data object.")
        except json5.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON5: {e}")
            # Optionally, save the cleaned data to a file for manual inspection
            with open('cleaned_data.json5', 'w', encoding='utf-8') as f:
                f.write(data_str_cleaned)
            return jsonify({"error": "Failed to parse data object."}), 500

        # Extract liveMatches
        try:
            live_matches = data_object[1]['data']['liveMatches']
        except (IndexError, KeyError, TypeError) as e:
            logger.error(f"Error extracting liveMatches: {e}")
            return jsonify({"error": "Failed to extract live matches data."}), 500

        # Process liveMatches
        base_url = "https://embedme.top/embed/"
        processed_matches = []
        for event in live_matches:
            try:
                event_id = event.get('id')
                source = event.get('source')

                if not all([event_id, source]):
                    logger.warning(f"Incomplete event data: {event}")
                    continue

                # Transform category from 'football' to 'soccer' if applicable
                category = event.get('category', '').lower()
                if category == 'football':
                    event['category'] = 'soccer'

                # Construct defaultStream URL
                event['defaultStream'] = f"{base_url}{source}/{event_id}/1"

                # Append the entire event with the new 'defaultStream' field
                processed_matches.append(event)

            except Exception as e:
                logger.warning(f"Error processing event {event}: {e}")
                continue

        # Sort the matches by 'category' and then by 'date'
        try:
            processed_matches.sort(key=lambda x: (x.get('category', ''), x.get('date', '')))
        except Exception as e:
            logger.warning(f"Error sorting events: {e}")

        logger.info(f"Fetched and processed {len(processed_matches)} live matches.")
        return jsonify(processed_matches), 200

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/')
def home():
    return "Hello, from Flask!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
