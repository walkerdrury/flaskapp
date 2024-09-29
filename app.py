from flask import Flask, jsonify
from flask_cors import CORS
import requests
#from bs4 import BeautifulSoup
import os
import logging
import time
#import re
#import json5

app = Flask(__name__)
CORS(app)

# Configure logging with detailed formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def fetch_url(url, headers=None, retries=3, backoff_factor=0.3):
    """
    Fetches the content from the specified URL with retry logic.

    Args:
        url (str): The URL to fetch.
        headers (dict, optional): Headers to include in the request.
        retries (int, optional): Number of retry attempts.
        backoff_factor (float, optional): Factor for exponential backoff between retries.

    Returns:
        requests.Response or None: The HTTP response if successful, else None.
    """
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            logger.info(f"Successfully fetched URL: {url}")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(backoff_factor * (2 ** attempt))
    return None

@app.route('/api/events', methods=['GET'])
def get_events():
    """
    Endpoint to retrieve live match events.

    Returns:
        Flask Response: JSON response containing the list of processed events or an error message.
    """
    url = 'https://streamed.su'
    endpoint = "/api/matches/live"

    # Define custom headers to mimic a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/129.0.0.0 Safari/537.36'
    }

    # Fetch the URL with retries
    response = fetch_url(f"{url}{endpoint}", headers=headers)

    if not response:
        logger.error("Failed to retrieve the webpage after multiple attempts.")
        return jsonify({"error": "Failed to retrieve the webpage."}), 500
    print(response)

    # # Parse the HTML content
    # try:
    #     soup = BeautifulSoup(response.content, 'html.parser')
    #     script_tags = soup.find_all('script')
    #     logger.info(f"Found {len(script_tags)} <script> tags in the webpage.")
    # except Exception as e:
    #     logger.error(f"Error parsing HTML: {e}")
    #     return jsonify({"error": "Failed to parse the webpage content."}), 500

    # # Initialize variable to store the data object string
    # data_str = None

    # # Iterate through all script tags to find the one containing 'const data ='
    # for script in script_tags:
    #     if script.string and 'const data =' in script.string:
    #         # Use regex to extract the array assigned to data
    #         match = re.search(r'const\s+data\s*=\s*(\[\s*\{.*?\}\s*\]);', script.string, re.DOTALL)
    #         if match:
    #             data_str = match.group(1)
    #             logger.info("Successfully extracted data object string from <script> tag.")
    #             break

    # if not data_str:
    #     logger.error("Data object not found in any <script> tags.")
    #     return jsonify({"error": "Data object not found."}), 500

    # # Step 1: Replace standalone 'void 0' and 'undefined' with 'null' using word boundaries
    # data_str_cleaned = re.sub(r'\bvoid\s+0\b', 'null', data_str)
    # data_str_cleaned = re.sub(r'\bundefined\b', 'null', data_str_cleaned)

    # # Step 2: Remove trailing commas
    # data_str_cleaned = re.sub(r',\s*([}\]])', r'\1', data_str_cleaned)

    # # Step 3: Parse the cleaned string using json5
    # try:
    #     data_object = json5.loads(data_str_cleaned)
    #     logger.info("Successfully parsed data object using json5.")
    # except json5.JSONDecodeError as e:
    #     logger.error(f"Failed to parse JSON5: {e}")
    #     # Optionally, save the cleaned data to a file for manual inspection
    #     with open('cleaned_data.json5', 'w', encoding='utf-8') as f:
    #         f.write(data_str_cleaned)
    #     logger.info("The cleaned data has been saved to 'cleaned_data.json5' for further inspection.")
    #     return jsonify({"error": "Failed to parse data object."}), 500

    # # Extract liveMatches
    # try:
    #     live_matches = data_object[1]['data']['liveMatches']
    #     logger.info(f"Extracted {len(live_matches)} live matches from data object.")
    # except (IndexError, KeyError, TypeError) as e:
    #     logger.error(f"Error extracting liveMatches: {e}")
    #     return jsonify({"error": "Failed to extract live matches data."}), 500

    # Process liveMatches
    live_matches = response.json()
    base_url = "https://embedme.top/embed/"
    processed_matches = []
    skipped_events = 0
    filtered_afl_events = 0  # Counter for filtered out 'afl' events

    for event in live_matches:
        try:
            event_id = event.get('id')
            source = event.get('source', "alpha")

            if not all([event_id]):
                missing_fields = []
                if not event_id:
                    missing_fields.append('id')
                if not source:
                    missing_fields.append('source')
                logger.warning(f"Skipping event due to missing fields {missing_fields}: {event}")
                skipped_events += 1
                continue

            # Transform category from 'football' to 'soccer' if applicable
            category = event.get('category', '').strip().lower()
            if category == 'football':
                event['category'] = 'soccer'
                logger.info(f"Transformed category from 'football' to 'soccer' for event ID: {event_id}")

            # Filter out events with category 'afl'
            if category == 'afl':
                logger.info(f"Filtering out event with category 'afl': {event_id}")
                filtered_afl_events += 1
                continue

            # Construct defaultStream URL
            event['defaultStream'] = f"{base_url}{source}/{event_id}/1"

            # Append the entire event with the new 'defaultStream' field
            processed_matches.append(event)

        except Exception as e:
            logger.warning(f"Error processing event {event}: {e}")
            skipped_events += 1
            continue

    # Sort the matches by 'category' and then by 'date'
    try:
        processed_matches.sort(key=lambda x: (x.get('category', '').lower(), x.get('date', '')))
        logger.info("Successfully sorted processed matches by category and date.")
    except Exception as e:
        logger.warning(f"Error sorting events: {e}")

    logger.info(f"Fetched and processed {len(processed_matches)} live matches.")
    if skipped_events > 0:
        logger.info(f"Skipped {skipped_events} events due to missing fields or processing errors.")
    if filtered_afl_events > 0:
        logger.info(f"Filtered out {filtered_afl_events} 'afl' events.")

    return jsonify(processed_matches), 200

@app.route('/')
def home():
    return "Hello, from Flask!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
