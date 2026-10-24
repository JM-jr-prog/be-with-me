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

from flask import Flask, Response, abort, request, send_from_directory

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


# MP3 frame tables (layer III), used to cut a song at a start time without any extra tools
BITRATES = {3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],      # MPEG 1
            2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],          # MPEG 2
            0: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}          # MPEG 2.5
SAMPLE_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def mp3_cut(data, start):
    """Returns (mp3 bytes beginning at the first frame at or after `start` seconds, that frame's time),
    or None if the file can't be read. A short song that begins at the right spot downloads fast
    and never has to seek, which is what makes phones play it reliably."""
    i, t, n = 0, 0.0, len(data)
    if data[:3] == b"ID3" and n > 10:                      # skip the ID3 tag at the front
        i = 10 + ((data[6] & 0x7F) << 21 | (data[7] & 0x7F) << 14 | (data[8] & 0x7F) << 7 | (data[9] & 0x7F))
    while i + 4 <= n:
        h = int.from_bytes(data[i:i + 4], "big")
        ver, layer, bri, sri = (h >> 19) & 3, (h >> 17) & 3, (h >> 12) & 15, (h >> 10) & 3
        if (h >> 21) != 0x7FF or ver == 1 or layer != 1 or bri in (0, 15) or sri == 3:
            i += 1
            continue
        rate, sr, pad = BITRATES[ver][bri] * 1000, SAMPLE_RATES[ver][sri], (h >> 9) & 1
        size, samples = (144 * rate // sr + pad, 1152) if ver == 3 else (72 * rate // sr + pad, 576)
        nxt = i + size
        if nxt + 2 <= n and not (data[nxt] == 0xFF and data[nxt + 1] & 0xE0 == 0xE0):
            i += 1                                          # not a real frame, keep looking
            continue
        if t >= start:
            return data[i:], t
        i, t = nxt, t + samples / sr
    return None


_cuts = {}


@app.route("/<name>.mp3")
def music(name):
    start = request.args.get("from", type=float)           # the page asks for the song from its start point
    path = os.path.join(MUSIC, name + ".mp3")
    if start and os.path.exists(path):
        if (name, start) not in _cuts:
            with open(path, "rb") as f:
                _cuts[(name, start)] = mp3_cut(f.read(), start)
        cut = _cuts[(name, start)]
        if cut:
            print(f"[music] {name}: sending {len(cut[0]) / 1e6:.1f} MB (from {cut[1]:.0f}s)")
            resp = Response(cut[0], mimetype="audio/mpeg")
            resp.headers["X-Trimmed-From"] = f"{cut[1]:.3f}"
            return resp
    # otherwise send the whole file (supports seeking)
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