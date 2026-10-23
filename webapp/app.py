"""Python web server for the 'stay by my side' page.

Run it, then open the link it prints (in any browser, on any device that can reach it).
Python serves the page and your mp3 files, and looks up the synced lyrics.
"""
import json
import os
import socket
import threading
import urllib.parse
import urllib.request
import webbrowser

from flask import Flask, Response, abort, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
MUSIC = os.path.join(BASE, "music")           # put on_bended_knee.mp3, ill_be.mp3, photograph.mp3 here
CACHE = os.path.join(BASE, "lyrics_cache")

# key used by index.html -> (file name without .mp3, artist, title)
SONGS = {
    "main": ("on_bended_knee", "Boyz II Men", "On Bended Knee"),
    "final": ("ill_be", "Edwin McCain", "I'll Be"),
    "yes": ("photograph", "Ed Sheeran", "Photograph"),
}

app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory(BASE, "index.html")


@app.route("/<name>.mp3")
def music(name):
    # supports seeking, so the page can start a song partway through
    return send_from_directory(MUSIC, name + ".mp3", conditional=True)


def find_lyrics(artist, title):
    """Asks LRCLIB for time-synced lyrics. Returns .lrc text or None."""
    query = urllib.parse.urlencode({"artist_name": artist, "track_name": title})
    req = urllib.request.Request("https://lrclib.net/api/search?" + query,
                                 headers={"User-Agent": "stay-by-my-side/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        results = json.load(resp)
    best = None
    for item in results:
        if not item.get("syncedLyrics"):
            continue
        name = (item.get("trackName") or "").strip().lower()
        extra = name + " " + (item.get("albumName") or "").lower()
        exact = name == title.lower() and artist.lower() in (item.get("artistName") or "").lower()
        studio = not any(w in extra for w in ("live", "remix", "acoustic", "karaoke"))
        if best is None or (exact, studio) > best[0]:
            best = ((exact, studio), item["syncedLyrics"])
    return best[1] if best else None


@app.route("/api/lyrics/<key>")
def lyrics(key):
    if key not in SONGS:
        abort(404)
    stem, artist, title = SONGS[key]
    path = os.path.join(CACHE, stem + ".lrc")
    if os.path.exists(path):                       # saved from an earlier lookup (or your own file)
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    else:
        try:
            raw = find_lyrics(artist, title)
        except Exception as e:
            print(f"[lyrics] lookup failed for '{title}': {e}")
            raw = None
        if raw:
            os.makedirs(CACHE, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(raw)
    if not raw:
        abort(404)
    return Response(raw, mimetype="text/plain; charset=utf-8")


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  On this computer:      http://localhost:{port}/?to=TheirName&from=YourName")
    print(f"  Same Wi-Fi (phones):   http://{lan_ip()}:{port}/?to=TheirName&from=YourName\n")
    threading.Timer(1, lambda: webbrowser.open(f"http://localhost:{port}/")).start()
    app.run(host="0.0.0.0", port=port)