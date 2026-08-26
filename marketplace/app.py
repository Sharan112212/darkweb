"""
Mock dark web marketplace/forum — serves synthetic persona and post data
for the PS 26151 prototype demo. All data is fictional (see
/data/personas.json and /data/posts.json). Meant to be scraped by your
own Tor-aware scraper as a stand-in for real dark web sources.
"""
from flask import Flask, render_template
import json
import os

app = Flask(__name__)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_data():
    with open(os.path.join(DATA_DIR, "personas.json")) as f:
        personas = json.load(f)
    with open(os.path.join(DATA_DIR, "posts.json")) as f:
        posts = json.load(f)
    return personas, posts


@app.route("/")
def index():
    personas, posts = load_data()
    return render_template("index.html", personas=personas)


@app.route("/user/<handle>")
def user_profile(handle):
    personas, posts = load_data()
    persona = next((p for p in personas if p["handle"] == handle), None)
    user_posts = [p for p in posts if p["handle"] == handle]
    return render_template("profile.html", persona=persona, posts=user_posts)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
