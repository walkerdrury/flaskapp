# app.py
from flask import Flask, jsonify
from flask_cors import CORS  # Import CORS
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/api/events', methods=['GET'])
def get_events():
    url = 'https://streamed.su'
    response = requests.get(url)

    links = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a')
    else:
        return jsonify({"error": "Failed to retrieve the webpage."}), 500

    hrefs = [link.get('href') for link in links if link.get('href') is not None]
    filtered_hrefs = []
    for href in hrefs:
        if href.startswith('/watch/'):
            filtered_hrefs.append(href.split('/watch/')[1])

    names = list(set(filtered_hrefs))

    return jsonify(names)

if __name__ == '__main__':
    app.run(debug=True)
