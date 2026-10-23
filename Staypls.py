import bisect
import json
import math
import os
import random
import re
import threading
import tkinter as tk
import tkinter.font as tkfont
import urllib.parse
import urllib.request

try:
    import pygame       
except ImportError:
    pygame = None

# ---------- Edit these two lines ----------
THEIR_NAME = "Their Name"
MY_NAME = "Your Name"

# ---------- Music (put your own audio files in the same folder as this script) ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SONG_MAIN = "on_bended_knee.mp3"     # plays at the start, fades out as "No" is clicked
MAIN_START_SECONDS = 205             # where "On Bended Knee" starts
MAIN_FADE_IN_MS = 50                 # 0.05 s fade-in

SONG_FINAL = "ill_be.mp3"            # fades in on the 10th "No" click
FINAL_START_SECONDS = 163            # where the bridge begins in "I'll Be" (2:43)
FINAL_FADE_IN_MS = 4000

SONG_YES = "photograph.mp3"          # plays when they click "Yes"
YES_START_SECONDS = 130
YES_FADE_IN_MS = 3000

FADE_STEP = 0.015                    # volume change every 50 ms while "No" fades the main song

# ---------- Lyrics ----------
# Lyrics are found automatically, in this order:
#   1) a file named like the song with .lrc (on_bended_knee.lrc) next to the script, if you add one
#   2) the lyrics_cache folder (saved from an earlier online lookup)
#   3) an online lookup on LRCLIB (free, needs internet), saved to lyrics_cache for next time
ONLINE_LYRICS = True
CACHE_LYRICS = True
LYRIC_OFFSET_SECONDS = 0.0          # lyrics too early? use a positive number. Too late? use a negative one.
LYRIC_OPACITY = 0.70                # lyrics show at the bottom, blended to 70% opacity
LYRIC_FONT_SIZE = 20                # lyric text size (it was 15)

# who sings what (used for the lookup; the file names above can be anything)
SONG_INFO = {
    SONG_MAIN: ("Boyz II Men", "On Bended Knee"),
    SONG_FINAL: ("Edwin McCain", "I'll Be"),
    SONG_YES: ("Ed Sheeran", "Photograph"),
}

# ---------- Settings ----------
W, H = 640, 540
DODGE_START = 9          # from the 9th "No" onward, the button runs away
LET_GO_AT = 10           # the 10th successful "No" ends it
CATCH_CHANCE = 0.10      # chance the cursor can actually catch the button

# ---------- Themes ----------
THEMES = {
    # the question screen: soft pink -> violet
    "ask": {
        "stops": ["#FFF1FE", "#EBD8FF", "#C9B2FF", "#9F86F5"],
        "bubbles": ["#F6E7FF", "#E9D6FF", "#DCC6FF", "#F9D9F6"],
        "card_fill": "#FCF8FF", "card_edge": "#DCC8FF", "shadow": "#A98CF0",
        "text": "#5B21B6", "accent": "#A855F7",
        "hearts": ["#FFFFFF", "#F5D0FE", "#E879F9", "#C084FC", "#8B5CF6", "#FBCFE8", "#7C3AED"],
    },
    # "Yes": sunny, happy, warm blush and gold
    "yes": {
        "stops": ["#FFF9DB", "#FFE3F0", "#F3CFFF", "#C7A9FF"],
        "bubbles": ["#FFF1B8", "#FFD6EC", "#F3D4FF", "#FFE9A8"],
        "card_fill": "#FFFDF5", "card_edge": "#F9C8E8", "shadow": "#D9A7F5",
        "text": "#7E22CE", "accent": "#EC4899",
        "hearts": ["#FFFFFF", "#FDE68A", "#F9A8D4", "#E879F9", "#C084FC", "#FCD34D", "#FB7185"],
    },
    # "No": dark, rainy, moody night purple
    "no": {
        "stops": ["#171230", "#241B4A", "#32265F", "#1E1740"],
        "bubbles": ["#2C2358", "#352A66", "#3F3275", "#2A2150"],
        "card_fill": "#2B2350", "card_edge": "#4C3F85", "shadow": "#120E26",
        "text": "#DDD0FF", "accent": "#A78BFA",
        "hearts": ["#6D5BA8", "#4C3F85", "#7C6BC4", "#5B4B96"],
    },
}
COLOR_KEYS = ("card_fill", "card_edge", "shadow", "text", "accent")

YES_FILL, YES_HOVER = "#8B5CF6", "#7C3AED"
NO_FILL, NO_HOVER, NO_EDGE = "#F5F3FF", "#EBE4FF", "#C4B5FD"
TEXT_DEEP = "#5B21B6"
RAIN_COLOR = "#A9BEEA"
FLOWER_COLORS = ["#F9A8D4", "#FDE68A", "#C084FC", "#FB7185", "#FFFFFF", "#A78BFA", "#FCA5A5"]

NO_LABELS = [
    "No", "Are you sure?", "Really?", "Think again...", "Pretty please?",
    "Don't do this", "Last chance?", "I'm shy now", "Catch me!",
]

PLEAS = [
    "Hmm... maybe you misclicked? 🥺",
    "Look at that big yes button, it's lonely 💜",
    "I made this just for you... 🌸",
    "Pretty please? With lavender on top? 🫶",
    "I'll bring snacks. And hugs. Lots of hugs. 🤗",
    "My heart is doing tiny sad flips... 🥹",
    "Okay, I'm getting nervous now... 🙈",
    "Fine, the No button is hiding. Try catching it! 🏃‍♀️💨",
]


# ---------- helpers ----------
def lerp_color(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def mix_theme(a, b, t):
    out = {}
    for key in ("stops", "bubbles"):
        out[key] = [lerp_color(x, y, t) for x, y in zip(a[key], b[key])]
    for key in COLOR_KEYS:
        out[key] = lerp_color(a[key], b[key], t)
    out["hearts"] = b["hearts"]
    return out


def round_points(x1, y1, x2, y2, r):
    """Points for a rounded rectangle (use with smooth=True)."""
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


LRC_TAG = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")


def parse_lrc_text(text):
    """Turns .lrc text into a sorted list of (seconds, line)."""
    items = []
    for line in text.splitlines():
        tags = LRC_TAG.findall(line)
        words = LRC_TAG.sub("", line).strip()
        for minutes, seconds in tags:
            items.append((int(minutes) * 60 + float(seconds), words))
    items.sort(key=lambda item: item[0])
    return items


def parse_lrc(path):
    try:
        with open(path, encoding="utf-8") as f:
            return parse_lrc_text(f.read())
    except OSError:
        return []


LYRIC_BANK = {}      # song file -> (lines, times), filled by a background thread


def fetch_synced_lyrics(artist, title):
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
        score = (exact, studio)
        if best is None or score > best[0]:
            best = (score, item["syncedLyrics"])
    return best[1] if best else None


def load_lyrics_for(song, artist, title):
    stem = os.path.splitext(song)[0]
    cache_dir = os.path.join(BASE_DIR, "lyrics_cache")
    for path in (os.path.join(BASE_DIR, stem + ".lrc"), os.path.join(cache_dir, stem + ".lrc")):
        lines = parse_lrc(path) if os.path.exists(path) else []
        if lines:
            LYRIC_BANK[song] = (lines, [t for t, _ in lines])
            return
    if not ONLINE_LYRICS:
        return
    try:
        raw = fetch_synced_lyrics(artist, title)
    except Exception as e:
        print(f"[lyrics] could not look up '{title}' online: {e}")
        return
    if not raw:
        print(f"[lyrics] no synced lyrics found online for '{title}'")
        return
    lines = parse_lrc_text(raw)
    LYRIC_BANK[song] = (lines, [t for t, _ in lines])
    if CACHE_LYRICS:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            with open(os.path.join(cache_dir, stem + ".lrc"), "w", encoding="utf-8") as f:
                f.write(raw)
        except OSError:
            pass


def prefetch_all_lyrics():
    for song, (artist, title) in SONG_INFO.items():
        load_lyrics_for(song, artist, title)


class RoundButton:
    """A soft, pill-shaped button drawn on the canvas."""

    def __init__(self, canvas, text, size, bold, fill, hover, fg, edge, command,
                 padx=26, pady=10):
        self.canvas = canvas
        self.text = text
        self.size = size
        self.bold = bold
        self.fill, self.hover, self.fg, self.edge = fill, hover, fg, edge
        self.command = command
        self.padx, self.pady = padx, pady
        self.tag = f"btn{id(self)}"
        self.visible = False
        self.x = self.y = 0
        self.w = self.h = 0
        self.bbox = (0, 0, 0, 0)
        self.poly = None

    def measure(self):
        font = tkfont.Font(family="Helvetica", size=self.size,
                           weight="bold" if self.bold else "normal")
        self.font = font
        self.w = font.measure(self.text) + self.padx * 2
        self.h = font.metrics("linespace") + self.pady * 2
        return self.w, self.h

    def draw(self, x, y):
        self.hide()
        self.measure()
        self.x, self.y = x, y
        x1, y1 = x - self.w / 2, y - self.h / 2
        x2, y2 = x + self.w / 2, y + self.h / 2
        self.bbox = (x1, y1, x2, y2)
        self.poly = self.canvas.create_polygon(
            round_points(x1, y1, x2, y2, self.h / 2), smooth=True,
            fill=self.fill, outline=self.edge, width=2, tags=self.tag)
        self.canvas.create_text(x, y, text=self.text, font=self.font,
                                fill=self.fg, tags=self.tag)
        self.canvas.tag_bind(self.tag, "<Button-1>", lambda e: self.command())
        self.canvas.tag_bind(self.tag, "<Enter>", self._enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self._leave)
        self.visible = True

    def _enter(self, _e):
        self.canvas.itemconfig(self.poly, fill=self.hover)
        self.canvas.config(cursor="hand2")

    def _leave(self, _e):
        self.canvas.itemconfig(self.poly, fill=self.fill)
        self.canvas.config(cursor="")

    def hide(self):
        self.canvas.delete(self.tag)
        self.canvas.config(cursor="")
        self.visible = False


class Flower:
    """A round-petaled flower that can bloom (grow 0 -> 1) and wilt (wilt 0 -> 1)."""

    def __init__(self, canvas, x, base_y, height, size, petals, color, delay, grown=False):
        self.canvas = canvas
        self.x, self.base_y = x, base_y
        self.height, self.size = height, size
        self.petals = petals
        self.color = color
        self.delay = delay
        self.grow = 1.0 if grown else 0.0
        self.wilt = 0.0
        self.side = random.choice([-1, 1])
        self.rot = random.random() * math.tau
        self.tag = f"flower{id(self)}"
        self.head = (x, base_y)

    def draw(self):
        c = self.canvas
        c.delete(self.tag)
        g = 1 - (1 - self.grow) ** 3          # ease-out so it blooms softly
        if g <= 0.01:
            return
        w = self.wilt
        h = self.height * g

        # the head swings to one side and sinks as the flower wilts
        hx = self.x + self.side * w * h * 0.55
        hy = self.base_y - h + w * h * 0.45
        mx = self.x + self.side * w * h * 0.08
        my = self.base_y - h * 0.5
        self.head = (hx, hy)

        stem = lerp_color("#5FBF73", "#6B6B4A", w)
        c.create_line(self.x, self.base_y, mx, my, hx, hy, smooth=True, width=3,
                      fill=stem, capstyle="round", tags=self.tag)
        sag = w * 8
        c.create_oval(mx - 15, my - 5 + sag, mx, my + 3 + sag, fill=stem, outline="", tags=self.tag)
        c.create_oval(mx, my - 9 + sag, mx + 15, my - 1 + sag, fill=stem, outline="", tags=self.tag)

        pr = self.size * g * (1 - 0.35 * w)
        visible = max(2, round(self.petals * (1 - 0.6 * w)))
        petal_color = lerp_color(self.color, "#7A6A8A", w * 0.85)
        for k in range(visible):
            a = math.tau * k / self.petals + self.rot
            d = pr * 1.15
            px = hx + math.cos(a) * d
            py = hy + math.sin(a) * d * (1 - 0.3 * w) + w * pr * 0.6
            c.create_oval(px - pr, py - pr, px + pr, py + pr,
                          fill=petal_color, outline="", tags=self.tag)
        cr = pr * 0.7
        c.create_oval(hx - cr, hy - cr, hx + cr, hy + cr,
                      fill=lerp_color("#FFD166", "#8A7A5A", w), outline="", tags=self.tag)
        c.tag_lower(self.tag, "card")


class Audio:
    """Plays the songs, fades the main one with each 'No', and keeps lyrics in sync."""

    def __init__(self, root):
        self.root = root
        self.ok = False
        self.vol = 1.0
        self.target = 1.0
        self.final = False        # True once the regular 'No' fade is no longer used
        self.offset = 0.0
        self.current = None
        # look the lyrics up in the background so the window never freezes
        threading.Thread(target=prefetch_all_lyrics, daemon=True).start()
        if pygame is None:
            print("[music] pygame not installed - running without music (pip install pygame)")
            return
        try:
            pygame.mixer.init()
            self.ok = True
        except Exception as e:
            print(f"[music] could not start audio: {e}")

    def current_lyrics(self):
        """(lines, times) for the song that is playing right now."""
        return LYRIC_BANK.get(self.current, ([], []))

    def _start(self, song, start, fade_ms):
        path = os.path.join(BASE_DIR, song)
        if not os.path.exists(path):
            print(f"[music] '{song}' not found next to the script")
            return False
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(1.0)
            self.vol = 1.0
            self.offset = start
            self.current = song
            pygame.mixer.music.play(start=start, fade_ms=fade_ms)
        except Exception as e:
            print(f"[music] could not play {song}: {e}")
            return False
        return True

    def start_main(self):
        if not self.ok:
            return
        if self._start(SONG_MAIN, MAIN_START_SECONDS, MAIN_FADE_IN_MS):
            self.fade_loop()

    def set_target(self, value):
        self.target = max(0.0, min(1.0, value))

    def fade_loop(self):
        if not self.ok or self.final:
            return
        if abs(self.vol - self.target) <= FADE_STEP:
            self.vol = self.target
        else:
            self.vol += FADE_STEP if self.target > self.vol else -FADE_STEP
        try:
            pygame.mixer.music.set_volume(self.vol)
        except Exception:
            return
        self.root.after(50, self.fade_loop)

    def switch_to(self, song, start, fade_ms):
        """Quickly fades out whatever is playing, then fades the new song in."""
        self.final = True
        if not self.ok:
            return
        self._fade_out_then(song, start, fade_ms)

    def _fade_out_then(self, song, start, fade_ms):
        self.vol = max(0.0, self.vol - 0.06)
        try:
            pygame.mixer.music.set_volume(self.vol)
        except Exception:
            pass
        if self.vol > 0:
            self.root.after(50, lambda: self._fade_out_then(song, start, fade_ms))
        else:
            self._start(song, start, fade_ms)

    def position(self):
        """Where we are in the current song, in seconds (None if nothing is playing)."""
        if not self.ok:
            return None
        try:
            ms = pygame.mixer.music.get_pos()
        except Exception:
            return None
        if ms < 0:
            return None
        return self.offset + ms / 1000.0


class App:
    def __init__(self, root, them, me):
        self.root = root
        self.them = them
        self.me = me
        self.no_count = 0
        self.dodging = False
        self.was_near = False
        self.safe = False
        self.mode = "ask"        # ask | yes | letgo
        self.last_no = None
        self.hearts = []         # floating hearts and falling petals
        self.drops = []          # raindrops
        self.flowers = []
        self.bands = []
        self.bubbles = []
        self.theme_name = "ask"
        self.theme_token = 0
        self.cur = THEMES["ask"]
        self.lyric_text = ""

        self.audio = Audio(root)
        self.audio.start_main()

        root.title("💜 A little question 💜")
        root.geometry(f"{W}x{H}")
        root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=W, height=H, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.draw_background()
        self.draw_card()

        self.title_id = self.canvas.create_text(
            W / 2, 66, text="✿ for you ✿", font=("Helvetica", 16, "italic"),
            fill=THEMES["ask"]["accent"], tags="text")
        self.msg_id = self.canvas.create_text(
            W / 2, 175, width=470, justify="center", fill=THEMES["ask"]["text"],
            font=("Helvetica", 24, "bold"), tags="text",
            text=f"Hey {them}, it's {me} 💜\n\nWill you stay by my side?")
        self.lyric_id = self.canvas.create_text(
            W / 2, H - 34, width=W - 60, justify="center", text="",
            font=("Helvetica", LYRIC_FONT_SIZE, "italic"), fill=THEMES["ask"]["text"], tags="text")

        self.yes_xy = (W * 0.30, 420)
        self.yes_btn = RoundButton(self.canvas, "Yes 💜", 18, True, YES_FILL,
                                   YES_HOVER, "white", YES_FILL, self.on_yes)
        self.yes_btn.draw(*self.yes_xy)

        self.no_btn = RoundButton(self.canvas, NO_LABELS[0], 13, False, NO_FILL,
                                  NO_HOVER, TEXT_DEEP, NO_EDGE, self.on_no,
                                  padx=22, pady=8)
        self.no_btn.draw(W * 0.72, 420)

        self.paint(self.cur)
        self.canvas.bind("<Motion>", self.on_motion)
        self.spawn_loop()
        self.animate_loop()
        self.flower_loop()
        self.rain_loop()
        self.lyric_loop()

    # ---------- look ----------
    def draw_background(self):
        bands = 120
        for i in range(bands):
            item = self.canvas.create_rectangle(
                0, i * H / bands, W, (i + 1) * H / bands + 1,
                fill="#FFFFFF", outline="", tags="bg")
            self.bands.append(item)
        for _ in range(16):
            r = random.randint(18, 60)
            x, y = random.randint(0, W), random.randint(0, H)
            idx = random.randrange(4)
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill="#FFFFFF", outline="", tags="bg")
            self.bubbles.append((item, idx))

    def draw_card(self):
        # soft shadow + rounded card behind the message
        self.shadow_id = self.canvas.create_polygon(
            round_points(48, 40, W - 48, 316, 42), smooth=True,
            fill="#A98CF0", outline="", tags="card")
        self.card = self.canvas.create_polygon(
            round_points(46, 32, W - 46, 308, 42), smooth=True,
            fill="#FCF8FF", outline="#DCC8FF", width=3, tags="card")

    def paint(self, th):
        """Colors everything from a theme dict."""
        stops = th["stops"]
        n = len(self.bands)
        for i, item in enumerate(self.bands):
            t = i / (n - 1) * (len(stops) - 1)
            k = min(int(t), len(stops) - 2)
            self.canvas.itemconfig(item, fill=lerp_color(stops[k], stops[k + 1], t - k))
        for item, idx in self.bubbles:
            self.canvas.itemconfig(item, fill=th["bubbles"][idx])
        self.canvas.itemconfig(self.shadow_id, fill=th["shadow"])
        self.canvas.itemconfig(self.card, fill=th["card_fill"], outline=th["card_edge"])
        self.canvas.itemconfig(self.title_id, fill=th["accent"])
        self.canvas.itemconfig(self.msg_id, fill=th["text"])
        # lyrics sit on the background at 70% opacity (text blended into the bottom color)
        self.canvas.itemconfig(
            self.lyric_id, fill=lerp_color(stops[-1], th["text"], LYRIC_OPACITY))

    def apply_theme(self, name, steps=40):
        """Smoothly cross-fades to another theme."""
        self.theme_name = name
        self.theme_token += 1
        token = self.theme_token
        start, end = self.cur, THEMES[name]

        def tick(i):
            if token != self.theme_token:
                return
            t = i / steps
            t = t * t * (3 - 2 * t)
            self.cur = mix_theme(start, end, t)
            self.paint(self.cur)
            if i < steps:
                self.root.after(40, lambda: tick(i + 1))

        tick(0)

    # ---------- floating hearts and falling petals ----------
    def spawn_heart(self, burst=False):
        x = random.randint(10, W - 10)
        y = random.randint(H // 2, H) if burst else H + 15
        size = random.randint(10, 28)
        item = self.canvas.create_text(
            x, y, text=random.choice(["♥", "♡", "✿", "✦", "❀", "❤"]),
            fill=random.choice(THEMES[self.theme_name]["hearts"]),
            font=("Helvetica", size))
        self.canvas.tag_lower(item, "card")
        self.hearts.append({
            "id": item, "x": x, "y": y, "t": random.random() * 6,
            "speed": random.uniform(1.0, 2.6) * (2 if burst else 1),
            "sway": random.uniform(0.5, 1.8),
        })

    def drop_petal(self, flower):
        hx, hy = flower.head
        item = self.canvas.create_text(
            hx, hy, text=random.choice(["✿", "❀"]),
            fill=lerp_color(flower.color, "#6B5B8A", 0.5),
            font=("Helvetica", random.randint(10, 16)))
        self.canvas.tag_lower(item, "card")
        self.hearts.append({
            "id": item, "x": hx, "y": hy, "t": random.random() * 6,
            "speed": -random.uniform(0.8, 1.6),     # negative = falls down
            "sway": random.uniform(0.3, 1.0),
        })

    def spawn_loop(self):
        if self.mode == "ask":
            self.spawn_heart()
            delay = 300
        elif self.mode == "yes":
            for _ in range(3):
                self.spawn_heart(burst=True)
            delay = 120
        else:
            delay = 1500
            if random.random() < 0.3:
                self.spawn_heart()
        self.root.after(delay, self.spawn_loop)

    def animate_loop(self):
        for h in self.hearts[:]:
            h["t"] += 0.08
            h["y"] -= h["speed"]
            h["x"] += math.sin(h["t"]) * h["sway"]
            self.canvas.coords(h["id"], h["x"], h["y"])
            if h["y"] < -30 or h["y"] > H + 30:
                self.canvas.delete(h["id"])
                self.hearts.remove(h)
        self.root.after(40, self.animate_loop)

    # ---------- flowers and rain ----------
    def plant_flowers(self, grown):
        n = 10
        for i in range(n):
            f = Flower(
                self.canvas, (i + 0.5) * W / n + random.randint(-16, 16), H + 4,
                random.randint(60, 118), random.randint(9, 14), random.randint(5, 7),
                random.choice(FLOWER_COLORS),
                delay=0 if grown else random.randint(0, 30), grown=grown)
            self.flowers.append(f)
            if grown:
                f.draw()

    def flower_loop(self):
        for f in self.flowers:
            if f.delay > 0:
                f.delay -= 1
                continue
            if self.mode == "yes" and f.grow < 1:
                f.grow = min(1.0, f.grow + 0.018)      # bloom
                f.draw()
            elif self.mode == "letgo" and f.wilt < 1:
                f.wilt = min(1.0, f.wilt + 0.006)      # wilt
                f.draw()
                if 0.1 < f.wilt < 0.95 and random.random() < 0.05:
                    self.drop_petal(f)
        self.root.after(40, self.flower_loop)

    def rain_loop(self):
        if self.mode == "letgo":
            for _ in range(4):
                x = random.randint(0, W + 60)
                length = random.randint(14, 26)
                item = self.canvas.create_line(x, -length, x - 4, 0,
                                               fill=RAIN_COLOR, width=1)
                self.canvas.tag_lower(item, "text")
                self.drops.append({"id": item, "x": x, "y": -length, "len": length,
                                   "v": random.uniform(14, 22)})
        for d in self.drops[:]:
            d["y"] += d["v"]
            d["x"] -= 2
            self.canvas.coords(d["id"], d["x"], d["y"], d["x"] - 4, d["y"] + d["len"])
            if d["y"] > H:
                self.canvas.delete(d["id"])
                self.drops.remove(d)
        self.root.after(40, self.rain_loop)

    # ---------- lyrics ----------
    def lyric_loop(self):
        pos = self.audio.position()
        lines, times = self.audio.current_lyrics()
        text = ""
        if pos is not None and lines:
            i = bisect.bisect_right(times, pos - LYRIC_OFFSET_SECONDS) - 1
            if i >= 0:
                text = lines[i][1]
        if text != self.lyric_text:
            self.lyric_text = text
            self.canvas.itemconfig(self.lyric_id, text=text)
        self.root.after(120, self.lyric_loop)

    # ---------- the "No" button ----------
    def random_no_pos(self, avoid=None):
        bw, bh = self.no_btn.measure()
        yx1, yy1, yx2, yy2 = self.yes_btn.bbox
        for _ in range(100):
            x = random.randint(int(bw / 2) + 15, int(W - bw / 2) - 15)
            y = random.randint(int(335 + bh / 2), int(H - 62 - bh / 2))   # keeps the lyric strip free
            # keep clear of the Yes button
            if (x + bw / 2 > yx1 - 30 and x - bw / 2 < yx2 + 30 and
                    y + bh / 2 > yy1 - 30 and y - bh / 2 < yy2 + 30):
                continue
            if avoid and math.hypot(x - avoid[0], y - avoid[1]) < 200:
                continue
            if self.last_no and math.hypot(x - self.last_no[0], y - self.last_no[1]) < 100:
                continue
            return x, y
        return int(W - bw / 2 - 20), int(H - 62 - bh / 2)

    def move_no(self, avoid=None):
        x, y = self.random_no_pos(avoid)
        self.last_no = (x, y)
        self.no_btn.draw(x, y)

    def on_motion(self, event):
        if not self.dodging or self.mode != "ask" or not self.no_btn.visible:
            return
        x1, y1, x2, y2 = self.no_btn.bbox
        m = 40
        near = (x1 - m <= event.x <= x2 + m) and (y1 - m <= event.y <= y2 + m)

        if near and not self.was_near:
            self.was_near = True
            self.safe = random.random() < CATCH_CHANCE   # 10% chance it stays put
            if not self.safe:
                self.move_no(avoid=(event.x, event.y))
                self.was_near = False
        elif not near:
            self.was_near = False
            self.safe = False

    def on_no(self):
        if self.mode != "ask":
            return
        self.no_count += 1

        if self.no_count >= LET_GO_AT:
            self.let_go()
            return

        # the Yes button gets bigger and cuter every time
        self.yes_btn.size = min(18 + self.no_count * 2, 38)
        self.yes_btn.padx = 26 + self.no_count * 2
        self.yes_btn.pady = 10 + self.no_count
        self.yes_btn.draw(*self.yes_xy)

        # music fades out gradually: full volume at 0 clicks, silent by the 9th
        self.audio.set_target(1.0 - self.no_count / (LET_GO_AT - 1))

        idx = min(self.no_count - 1, len(PLEAS) - 1)
        self.canvas.itemconfig(self.msg_id, text=PLEAS[idx], font=("Helvetica", 22, "bold"))
        self.no_btn.text = NO_LABELS[min(self.no_count, len(NO_LABELS) - 1)]

        if self.no_count >= DODGE_START:
            self.dodging = True
        self.move_no()

    # ---------- endings ----------
    def on_yes(self):
        self.mode = "yes"
        self.dodging = False
        self.audio.switch_to(SONG_YES, YES_START_SECONDS, YES_FADE_IN_MS)
        self.yes_btn.hide()
        self.no_btn.hide()
        self.apply_theme("yes")
        self.plant_flowers(grown=False)          # flowers bloom
        self.canvas.itemconfig(self.title_id, text="✿ ♥ ✿ ♥ ✿")
        self.canvas.itemconfig(
            self.msg_id, font=("Helvetica", 24, "bold"),
            text=f"Yay!!! 💜🎉\n\nThank you, {self.them}.\nI promise to make every day a little softer.\n\n— {self.me}")

    def let_go(self):
        self.mode = "letgo"
        self.dodging = False
        self.audio.switch_to(SONG_FINAL, FINAL_START_SECONDS, FINAL_FADE_IN_MS)
        self.yes_btn.hide()
        self.no_btn.hide()
        self.apply_theme("no")
        self.plant_flowers(grown=True)           # flowers that then wilt in the rain
        self.canvas.itemconfig(self.title_id, text="🕊️")
        self.canvas.itemconfig(
            self.msg_id, font=("Helvetica", 18),
            text=(f"It's okay, {self.them}.\n\n"
                  "Thank you for being honest with me, and for every moment we shared. "
                  "I won't hold on to something that isn't meant to stay.\n\n"
                  "I'm letting go with a full heart, "
                  "and I'll always wish you happiness. 💜\n\n"
                  f"— {self.me}"))
        close = RoundButton(self.canvas, "Close", 14, True, YES_FILL, YES_HOVER,
                            "white", YES_FILL, self.root.destroy, padx=30, pady=8)
        close.draw(W / 2, 430)


def main():
    root = tk.Tk()
    App(root, THEIR_NAME, MY_NAME)
    root.mainloop()


if __name__ == "__main__":
    main()