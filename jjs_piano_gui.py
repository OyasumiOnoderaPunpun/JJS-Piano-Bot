"""
JJS Piano Bot — GUI Edition
Jujutsu Shenanigans Auto-Play with pydirectinput scan codes.
Standalone tkinter app — bundle with PyInstaller for .exe.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import ctypes
import os
import sys
import json
import queue

# ── pydirectinput ────────────────────────────────────────────────────────────
try:
    import pydirectinput
except ImportError:
    try:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Missing dependency",
            "pydirectinput not installed.\nRun:  pip install pydirectinput")
        sys.exit(1)
    except Exception:
        print("ERROR: pip install pydirectinput"); sys.exit(1)

pydirectinput.PAUSE = 0.0
pydirectinput.FAILSAFE = True

# ── Windows helpers ──────────────────────────────────────────────────────────
user32 = ctypes.windll.user32

def find_roblox_hwnd():
    return user32.FindWindowW(None, "Roblox")

def focus_roblox(hwnd):
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)

# ── App data directory (next to .exe or script) ─────────────────────────────
def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CUSTOM_SHEETS_FILE = os.path.join(get_app_dir(), "custom_sheets.json")

# ── Piano engine ─────────────────────────────────────────────────────────────
ADV_BLACK = set('QERTYUP')

def _pdi_key(ch):
    return ch.lower()

def key_down(ch):
    try: pydirectinput.keyDown(_pdi_key(ch))
    except Exception: pass

def key_up(ch):
    try: pydirectinput.keyUp(_pdi_key(ch))
    except Exception: pass

def needs_shift(ch, mode):
    if mode == "advanced":
        return ch.upper() in ADV_BLACK
    return ch.isupper() and ch.isalpha()

def press_single(ch, mode, note_delay, chord_delay):
    if ch in ('-',' ') or not (ch.isalpha() or ch.isdigit()):
        return
    shift = needs_shift(ch, mode)
    if shift:
        key_down('shift'); time.sleep(chord_delay)
    key_down(ch); time.sleep(chord_delay); key_up(ch)
    if shift:
        time.sleep(chord_delay); key_up('shift')
    time.sleep(note_delay)

def press_chord(chars, mode, chord_delay, note_delay):
    keys, shift = [], False
    for ch in chars:
        if ch in ('-',' ') or not (ch.isalpha() or ch.isdigit()):
            continue
        keys.append(ch)
        if needs_shift(ch, mode): shift = True
    if not keys: return
    if shift:
        key_down('shift'); time.sleep(chord_delay)
    for ch in keys:
        key_down(ch); time.sleep(chord_delay)
    time.sleep(chord_delay)
    for ch in reversed(keys):
        key_up(ch); time.sleep(chord_delay)
    if shift: key_up('shift')
    time.sleep(note_delay)

_CONTROL = {"PAUSE", "BPAUSE", "SLOW", "FAST", "SLOWER", "FASTER", "RESET"}

def _is_bpm_token(word):
    """Check if word is a BPM### token like BPM80, BPM160."""
    return (len(word) >= 4 and word[:3] == 'BPM' and word[3:].isdigit())

def tokenise(sheet):
    tokens, i = [], 0
    while i < len(sheet):
        ch = sheet[i]
        if ch == '[':
            j = sheet.find(']', i+1)
            if j == -1: j = len(sheet)-1
            tokens.append(sheet[i:j+1]); i = j+1
        elif ch == ' ':
            if tokens and tokens[-1] != ' ': tokens.append(' ')
            i += 1
        else:
            j = i
            while j < len(sheet) and sheet[j] not in (' ','[',']'): j += 1
            w = sheet[i:j]
            if w in _CONTROL or _is_bpm_token(w):
                tokens.append(w)
            else:
                for c in w: tokens.append(c)
            i = j
    return tokens

SPACE_PAUSE = 0.07; DASH_PAUSE = 0.10
PAUSE_DUR = 0.45;   BPAUSE_DUR = 0.20

# ── Tempo multipliers ────────────────────────────────────────────────────
# SLOW / FAST   = gentle 30% shift
# SLOWER / FASTER = aggressive 50% shift
# BPM###       = jump to exact BPM
# RESET        = return to original BPM
TEMPO_MULT = {
    "SLOW":   0.70,   # 30% slower (BPM drops → delay increases)
    "FAST":   1.30,   # 30% faster
    "SLOWER": 0.50,   # 50% slower
    "FASTER": 1.50,   # 50% faster
}

def _bpm_to_delay(bpm):
    """Convert a BPM value to note delay in seconds."""
    return 60.0 / (bpm * 1.85)

def play_sheet(sheet, mode, note_delay, chord_delay, stop_flag,
               progress_cb=None, base_bpm=120):
    """Play a sheet with dynamic tempo support.

    Tempo tokens embedded in the sheet change speed on the fly:
      SLOW / FAST       — shift current BPM by ±30%
      SLOWER / FASTER   — shift current BPM by ±50%
      BPM###            — jump to exact BPM  (e.g. BPM80, BPM160)
      RESET             — return to the original BPM

    stop_flag  = threading.Event
    progress_cb(current, total)
    base_bpm   = the song's starting BPM (used by RESET)
    """
    stop_flag.clear()
    tokens = tokenise(sheet)
    total = len(tokens)

    # Live tempo state
    orig_delay = note_delay
    orig_chord = chord_delay
    orig_bpm   = base_bpm
    cur_bpm    = base_bpm

    for idx, tok in enumerate(tokens):
        if stop_flag.is_set(): return False
        if progress_cb and idx % 3 == 0:
            progress_cb(idx, total)

        # ── Tempo control tokens ─────────────────────────────────
        if tok in TEMPO_MULT:
            cur_bpm = max(20, min(400, cur_bpm * TEMPO_MULT[tok]))
            note_delay = _bpm_to_delay(cur_bpm)
            chord_delay = max(0.01, note_delay * 0.12)
            continue

        if tok == 'RESET':
            cur_bpm    = orig_bpm
            note_delay = orig_delay
            chord_delay = orig_chord
            continue

        if _is_bpm_token(tok):
            cur_bpm = max(20, min(400, int(tok[3:])))
            note_delay = _bpm_to_delay(cur_bpm)
            chord_delay = max(0.01, note_delay * 0.12)
            continue

        # ── Normal playback tokens ───────────────────────────────
        if tok == ' ':       time.sleep(SPACE_PAUSE)
        elif tok == 'PAUSE': time.sleep(PAUSE_DUR)
        elif tok == 'BPAUSE':time.sleep(BPAUSE_DUR)
        elif tok == '-':     time.sleep(DASH_PAUSE)
        elif tok.startswith('[') and tok.endswith(']'):
            press_chord(tok[1:-1], mode, chord_delay, note_delay)
        elif len(tok) == 1:
            press_single(tok, mode, note_delay, chord_delay)
    if progress_cb: progress_cb(total, total)
    return True

# ── Song library ─────────────────────────────────────────────────────────────
SONGS = [
    {"name":"Megalovania","mode":"advanced","bpm":160,
     "sheet":"2 2 9 6 T 5 4 2 4 5 1 1 9 6 T 5 4 2 4 5 2 2 9 6 T 5 4 2 4 5 1 1 9 6 T 5 4 2 1 4 4 4 4 2 2 4 4 4 5 T 5 4 2 4 5 4 4 4 5 T 6 8 6 9 9 9 6 9 8 6 6 6 6 6 5 5 6 6 6 6 5 6 9 6 5 9 6 5 4 8 5 4 3 1 2 3 4 8 4 2 4 5 T 5 4 2 T 5 4 5 T 6 8 6 T 5 4 2 3 4 5 T 8 U T T 5 4 5"},
    {"name":"Giorno's Theme","mode":"advanced","bpm":110,
     "sheet":"2 R 2 2 3 4 3 2 Q 2 3 2 R 2 4 7 2 Q 6 5 2 R 2 2 3 4 3 2 Q 2 3 2 R 2 4 7 7 U 1 5 7 9 5 R Q 4 9 Y 7"},
    {"name":"Despacito","mode":"advanced","bpm":130,
     "sheet":"9 U 7 9 U 7 6 5 9 U 7 6 R 9 U 9 0 U 9 U 7 R 7 U 9 0 9 U 7 6 5 9 9 9 6 9 6 9 6 9 0 U 7 R 7 U 9 0 9 U 7 6 5 9 0 9 6 9 6 9 6 9 0 U 9 U 7 R 7 7 U 9 U 9 U 9 9 U 7 5 7 7 U 9 U 9 U 9 0 6 6 6 6 6 9 U 9 U 9 0 0 U 9 U 7 R 7 7 U 9 U 9 U 9 9 U 7 5 7 7 U 9 U 9 U 9 0 6 6 6 6 6 9 U 9 U 9 0 0 U 9 U 7 R R R R R 7 7 7 7 7 6 7 5 5 5 5 5 7 7 7 7 7 7 U 9 6 6 6 6 9 9 9 9 9 0 0 U"},
    {"name":"Specialz - JJK OP","mode":"advanced","bpm":135,
     "sheet":"2 2 7 6 7 9 7 6 7 7 5 6 7 9 7 6 7 7 2 2 5 5 2 2 5 6 5 9 8 7 6 5 5 5 6 7 6 6 6 7 9 7 2 2 7 6 7 9 7 6 7 7 5 5 6 7 9 7 6 7 5 5 5 6 7 7 0 P 9 7 6 5 5 5 6 7 6 6 6 7"},
    {"name":"An Enigmatic Encounter","mode":"advanced","bpm":115,
     "sheet":"8 7 8 6 7 8 6 5 3 2 1 2 8 7 8 6 7 8 9 8 7 6 T 8 7 8 6 7 8 6 5 3 2 1 2 8 7 8 6 7 8 9 8 7 6 T 8 7 8 6 7 8 6 5 3 2 1 2 8 7 8 6 7 8 9 8 7 6 T"},
    {"name":"Naruto - Blue Bird","mode":"advanced","bpm":125,
     "sheet":"Q R T 6 T R Q R T 6 7 6 7 U Q R T 6 T R R U 7 R U 7 3 3 R R BPAUSE 6 T T 6 6 T 3 R 3 R 4 Q R T 6 Q 6 T R 3 R 1 2 Q Q Q Q 2 3 R 3 3 3 R T 6 T Q R T 6 Q 6 T R 3 R 1 2 Q Q Q Q 2 6 T R 3 R R BPAUSE Q R T 6 6 T 6 T T T 6 7 7 6 T R R 6 7 U R 6 7 U U 0 9 U"},
    {"name":"Hunter x Hunter - Departure","mode":"advanced","bpm":120,
     "sheet":"4 E 2 E 4 4 4 2 4 4 E 2 4 R R R 2 R R E 2 R 5 5 5 2 5 4 5 T Y Y"},
    {"name":"Cruel Angel's Thesis","mode":"advanced","bpm":130,
     "sheet":"1 E 4 E 4 2 4 2 4 2 Y T E 5 4 E 5 E 5 Y 8 T 4 E 2 2 1 2 2 E E 1 E 4 E 4 2 4 2 4 2 Y 2 T E 5 4 E 5 E 5 Y T 8 4 E Y Y 5 Y 4 Y 5 8 1 E 4 E 4 2 4 2 4 2 Y 2 T E 5 4 E 5 E 5 Y T 8 4 E 2 Y 2 Y 2 5 2 Y 4 Y 5 8"},
    {"name":"Fire Force OP","mode":"advanced","bpm":140,
     "sheet":"Q 3 Q 3 Q U 3 T 7 R 3 3 0 E 6 P Q U E T 7 Q U 3 T 7 R 1 E R 3 3 3 T 7 T Q 3 T Q E 3 3 E R 3 1 3 1 3 R T 3 Q 3 6 T R 3 E R 6 T R 3 3"},
    {"name":"Your Lie in April","mode":"advanced","bpm":115,
     "sheet":"T R 4 R T 6 T 6 7 3 3 7 6 T 6 6 T 6 7 6 7 U 6 T 6 7 3 7 6 T 6 U U U 7 6 T R 6 T 6 7 3 7 6 T 6 3 6 T 6 7 0 9 U U U U 7 6 7 U 9 U 3 U U U 7 6 T R"},
    {"name":"One Punch Man OP","mode":"advanced","bpm":145,
     "sheet":"4 4 4 4 4 5 4 3 4 5 5 R 2 3 3 2 3 R 5 6 R 3 2 R 2 2 2 Q 1 Q 3 2 5 R 2 3 3 2 2 6 6 6 6 6 5 R 3 R 2 [36] [36] [36] [36] 5 R 2 3 3 2 3 R 5 6 R 3 2 R 2 2 2 Q 1 Q 3 2 5 R 2 3 3 2 6 6 6 6 6 5 R 3 R 2 6 6 6 6 6 7"},
    {"name":"Gurenge - Demon Slayer","mode":"advanced","bpm":135,
     "sheet":"Q 6 Q 5 Q Y Q 6 2 5 2 4 2 3 2 4 Q 6 Q 5 Q Y Q 6 1 4 8 4 Y 4 6 4 T Q 6 Q 5 Q Y Q 6 2 5 2 4 2 3 2 4"},
    {"name":"Fallen Down - Undertale","mode":"advanced","bpm":90,
     "sheet":"6 3 6 3 6 3 6 3 6 3 6 3 2 1 3 1 2 5 R 5 6 R 2 6 2 6 2 6 2 6 Q 6 Q Y 6 4 6 4 5 6 5 4 3"},
    {"name":"Undertale OST","mode":"advanced","bpm":100,
     "sheet":"Y 5 4 E 2 E 4 9 U 8 Y 1 Y 5 4 E 4 5 2 4 4 E 2 E"},
    {"name":"FNAF Theme","mode":"advanced","bpm":115,
     "sheet":"9 0 9 7 7 7 6 7 8 7 8 6 9 7 5 3 6 E"},
    {"name":"Ballin'","mode":"advanced","bpm":120,
     "sheet":"6 7 6 7 8 7 6 5 7 9 9 9 9 7 9 9 9 9 9 9 9 9 0 9 9 9 9 7 0 7 6 5 5 9 9 9 9 7 0 7 6 5 5 7 7 7 7 7 6 5 5 6 6 5 6 7 8 8 7 6 5 6 6 5 9 7 8 8 7 6 5 6 6 5 9 7 9 9 0 7 7 6 6 6 5 9 7 7 7 7 8 7 6 5 6 6 6 5 6 3"},
    {"name":"You Are My Sunshine","mode":"advanced","bpm":110,
     "sheet":"1 1 2 3 3 3 2 3 1 1 1 2 3 4 6 6 5 4 3 1 2 3 4 6 6 5 4 3 1 1 2 3 4 2 2 3 1"},
    {"name":"Treachery","mode":"advanced","bpm":120,
     "sheet":"6 7 8 7 6 7 8 9 8 7 8 6 7 8 7 6 7 8 9 8 7 8 6 7 8 7 6 7 8 9 8 7 6 8 0"},
    {"name":"Gojo Honored One (Numbers)","mode":"advanced","bpm":100,
     "sheet":"4 6 7 8 7 6 4 6 7 8 7 6 3 5 7 8 7 5 3 5 7 9 7 5 2 4 6 8 6 4 2 4 6 8 6 4 1 3 6 7 6 3 1 3 6 7 6 3"},
    {"name":"Hollow Purple","mode":"advanced","bpm":120,
     "sheet":"u r t r u r Q w r u r t r e w o I u Y p 3 5 7 [uf3] 5 [ra7] 3 5 7 [ts3] 5 [ra7] 3 5 7 [uf3] 5 [ra7] 3 5 7 [QI3] [wo5] [ra7] 3 5 7 [uf3] 5 [ra7] 3 5 7 [ts3] 5 [ra7] 3 5 7 [ep3] 5 [wo7] 3 5 7 I o a 3 u [r3] r [t3] r 3 r 3 u [r3] o [I3] u Y 3 Y I 3 u PAUSE 3 [uf] [ra3] [ra] [ts3] [ra] 3 [ra] 3 [uf] [ra3] [oh] [IG3] [uf] [YD] 3 [YD] [IG] 3 o [I3] u Y 3 t r 3 0 0 0 0 r r r r t t r 3 3 3 3 8 8 7 7 5 5"},
    {"name":"Malevolent Shrine","mode":"advanced","bpm":130,
     "sheet":"3 5 8 7 6 [79] 8 6 [t7] 3 5 [25] 4 3 4 y [e7] 3 [t0] 8 7 9 [q6u] [q6u]"},
    {"name":"KaiKai Kitan - JJK OP","mode":"simple","bpm":140,
     "sheet":"P h s g d P p P S s P P s P P P g d P s P s d s P P h s g d P p P S s P P s P P P g d P s P s S s P J t y y t y t y y t y t y E E o o i y t E t y t y t y t y t y t y y y w w o o i y t t y t y t y y t y t t y t y E o o i y t E t y t y t y t y t y t y t y w o i o p P g d P P P P P P J j g d P P s P P g d s P g d s P P P s P s d d d d J j P P P J j J P P P J j J P P P P h g g d d D g d s P P g g P P P g g P P P p P s s d d J j P P P J j J P P P J j J P P P P h"},
    {"name":"Super Mario Bros Theme","mode":"simple","bpm":145,
     "sheet":"f f f s f h o s o u p a P p o f h j g h f s d a s o u p a P p o f h j g h f s d a h G g D f O p s p s d h G g D f l l l h G g D f O p s p s d [DO] [id] [us] s s s s d f s p o s s s s d f s s s s d f s p o f f f s f h o f s o o p g g p a j j j h g f s p o"},
    {"name":"Naruto - Silhouette","mode":"simple","bpm":135,
     "sheet":"G d f G d G G f d f j j f S f d k j d k j d d S d f d G d f G d d G f d f j j f S f d k j d k j d d S d f d BPAUSE a G G d d G G d d k G d a S d d S d f f f G f d f d p d G G f d f f p S f h G f G f d k j d k j d d S d f G d p d G G f d f f p S f h G G G f d k j d k j d d S j f G d"},
    {"name":"Viva La Vida","mode":"simple","bpm":138,
     "sheet":"P s s s S P P O P P O s Y i s s s s s s s S P P O P P O P s O o i P s s s S P P O P P O s O o i s s s s s S P O O s P O O s P O O D g g g g S D D S D D S s s s s s s s s S P O s P O O s P O O D g g g D g D P s S D D D s D s i o O g g g D g D P s S D s D D s D s i o O"},
    {"name":"Merry Go Round of Life","mode":"simple","bpm":108,
     "sheet":"[36] 7 8 [29] 9 [83] 7 6 [71] [71] 8 9 [03] 0 [04] 0 9 8 [91] [61] 8 9 [03] [92] 8 7 y 7 [83] [72] 6 5 r 5 [51] 4 3 [31] 4 5 [63]"},
    {"name":"Gojo Honored One (Letters)","mode":"simple","bpm":100,
     "sheet":"i p a s a p i p a s a p i p a s a p i p a s a p u o a s a o u o a d a o u o a d a o u o a f a o y p s h s p y p s h s p y p s h s p y p s h s p t o f k f o t o f k f o t o f k f o t o f l f o"},
    {"name":"Minecraft Theme (Letters)","mode":"simple","bpm":95,
     "sheet":"r p a i y u t i p u r d a p i y u t p i u r p a d g f s d s p r a p i y u t i p u r p a i y u t i p u r p a d d f s g i p u i a p o u y t y u r d a p o u f s d f a"},
    {"name":"Fur Elise","mode":"simple","bpm":100,
     "sheet":"f d f d f a d s p e t u p a 0 u o a s e u f d f d f a d s p e t u p a 0 u s a p e a s d f t o g f d r i f d s e u d s a f d f d f a d s p e t u p a 0 u o a s e u f d f d f a d s p e t u p a 0 u s a p e u"},
    {"name":"Black Clover OP","mode":"simple","bpm":140,
     "sheet":"o o o d d s a p f f a s s a p a f f f a a s a p a u a p o i g h f z z l k j h k k j h k k j z k k z g h h h h j j h g f h g f f g h g h j h g f d h g g x z l k z z l k x z l k g j c x z l k k k j g f g g x z l k g j c x z l k z l l l l k k h g f g f f g h g h j h g f d h g g l l l k k"},
]

# ── Custom sheets persistence ────────────────────────────────────────────────
def load_custom_sheets():
    try:
        with open(CUSTOM_SHEETS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_custom_sheets(sheets):
    try:
        with open(CUSTOM_SHEETS_FILE, 'w') as f:
            json.dump(sheets, f, indent=2)
    except Exception:
        pass

# ── Theme colors ─────────────────────────────────────────────────────────────
C = {
    "bg":       "#0f0f1a",
    "panel":    "#1a1a2e",
    "card":     "#16213e",
    "accent":   "#e94560",
    "accent2":  "#533483",
    "green":    "#4ecca3",
    "text":     "#eaeaea",
    "dim":      "#7a7a8c",
    "entry":    "#0d1117",
    "border":   "#30304a",
    "adv":      "#e94560",
    "sim":      "#4ecca3",
    "hover":    "#1f2b47",
}
FONT       = ("Segoe UI", 10)
FONT_B     = ("Segoe UI", 10, "bold")
FONT_H     = ("Segoe UI", 16, "bold")
FONT_SM    = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 9)

# ═════════════════════════════════════════════════════════════════════════════
# GUI APPLICATION
# ═════════════════════════════════════════════════════════════════════════════

class PianoBotApp:

    def __init__(self, root):
        self.root = root
        self.root.title("JJS Piano Bot")
        self.root.geometry("960x680")
        self.root.minsize(800, 580)
        self.root.configure(bg=C["bg"])

        # Try to set icon-less title bar dark (Windows 10/11)
        try:
            self.root.update()
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            hwnd_self = ctypes.windll.user32.GetParent(self.root.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd_self, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
        except Exception:
            pass

        # State
        self._stop   = threading.Event()
        self._pq     = queue.Queue()
        self._playing = False
        self._updating = False          # prevent slider ↔ entry loop
        self._all_songs = list(SONGS)   # built-in
        self._customs = load_custom_sheets()
        self._current_song = None

        # Build
        self._build_styles()
        self._build_ui()
        self._refresh_list()
        self._start_f6()
        self._poll()

    # ── ttk styles ───────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style()
        s.theme_use("clam")

        s.configure(".", background=C["bg"], foreground=C["text"],
                    fieldbackground=C["entry"], borderwidth=0,
                    font=FONT)

        s.configure("TFrame", background=C["bg"])
        s.configure("Card.TFrame", background=C["card"])
        s.configure("Panel.TFrame", background=C["panel"])

        s.configure("TLabel", background=C["bg"], foreground=C["text"], font=FONT)
        s.configure("Card.TLabel", background=C["card"])
        s.configure("Panel.TLabel", background=C["panel"])
        s.configure("Dim.TLabel", foreground=C["dim"], font=FONT_SM)
        s.configure("Header.TLabel", font=FONT_H, foreground=C["accent"])
        s.configure("Adv.TLabel", foreground=C["adv"], font=FONT_B)
        s.configure("Sim.TLabel", foreground=C["green"], font=FONT_B)
        s.configure("Status.TLabel", foreground=C["dim"], font=FONT_SM,
                    background=C["panel"])

        s.configure("Play.TButton", font=FONT_B, foreground="#fff",
                    background=C["green"], padding=(16,8))
        s.map("Play.TButton",
              background=[("active",C["green"]),("disabled",C["dim"])])

        s.configure("Stop.TButton", font=FONT_B, foreground="#fff",
                    background=C["accent"], padding=(16,8))
        s.map("Stop.TButton",
              background=[("active",C["accent"]),("disabled",C["dim"])])

        s.configure("Imp.TButton", font=FONT_SM, foreground=C["text"],
                    background=C["card"], padding=(10,6))
        s.map("Imp.TButton", background=[("active",C["hover"])])

        s.configure("Horizontal.TScale", background=C["card"],
                    troughcolor=C["entry"], sliderthickness=18)
        s.configure("green.Horizontal.TProgressbar",
                    troughcolor=C["entry"], background=C["green"], thickness=12)

    # ── UI layout ────────────────────────────────────────────────────────
    def _build_ui(self):
        # ─── Header ──────────────────────────────────────────────────
        hdr = ttk.Frame(self.root)
        hdr.pack(fill="x", padx=16, pady=(12,4))
        ttk.Label(hdr, text="🎹 JJS Piano Bot", style="Header.TLabel").pack(side="left")
        ttk.Label(hdr, text="Jujutsu Shenanigans Auto-Piano  |  F6 = Stop",
                  style="Dim.TLabel").pack(side="left", padx=12)

        # ─── Main container ─────────────────────────────────────────
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=16, pady=(4,8))
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        # ─── LEFT: song list ────────────────────────────────────────
        left = ttk.Frame(main, style="Card.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0,8))

        # Search
        sf = ttk.Frame(left, style="Card.TFrame")
        sf.pack(fill="x", padx=8, pady=(8,4))
        ttk.Label(sf, text="🔍", style="Card.TLabel").pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh_list())
        se = tk.Entry(sf, textvariable=self._search_var,
                      bg=C["entry"], fg=C["text"], insertbackground=C["text"],
                      font=FONT, relief="flat", bd=0)
        se.pack(side="left", fill="x", expand=True, padx=(6,0), ipady=4)

        # Listbox
        lf = ttk.Frame(left, style="Card.TFrame")
        lf.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self._lb = tk.Listbox(lf, bg=C["entry"], fg=C["text"],
                              selectbackground=C["accent"], selectforeground="#fff",
                              font=FONT, relief="flat", bd=0, highlightthickness=0,
                              activestyle="none")
        sb = tk.Scrollbar(lf, command=self._lb.yview, bg=C["card"],
                          troughcolor=C["entry"])
        self._lb.configure(yscrollcommand=sb.set)
        self._lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._lb.bind("<<ListboxSelect>>", self._on_select)

        # Import buttons
        bf = ttk.Frame(left, style="Card.TFrame")
        bf.pack(fill="x", padx=8, pady=(0,8))
        ttk.Button(bf, text="📂 Import Sheet", style="Imp.TButton",
                   command=self._import_file).pack(side="left", padx=(0,4))
        ttk.Button(bf, text="📋 Paste Sheet", style="Imp.TButton",
                   command=self._paste_sheet).pack(side="left", padx=(0,4))
        ttk.Button(bf, text="🗑 Delete Custom", style="Imp.TButton",
                   command=self._delete_custom).pack(side="right")

        # ─── RIGHT: controls ────────────────────────────────────────
        right = ttk.Frame(main, style="Card.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)
        row = 0

        def label(r, txt, **kw):
            ttk.Label(right, text=txt, style="Card.TLabel", **kw).grid(
                row=r, column=0, sticky="w", padx=(12,4), pady=4)

        def pad_row():
            nonlocal row; row += 1
            ttk.Frame(right, height=6, style="Card.TFrame").grid(
                row=row, column=0, columnspan=2)

        # Mode
        label(row, "Mode")
        self._mode_var = tk.StringVar(value="advanced")
        mf = ttk.Frame(right, style="Card.TFrame")
        mf.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        self._adv_rb = tk.Radiobutton(mf, text="Advanced", variable=self._mode_var,
            value="advanced", bg=C["card"], fg=C["adv"], selectcolor=C["entry"],
            activebackground=C["card"], activeforeground=C["adv"], font=FONT_B,
            indicatoron=1, bd=0, highlightthickness=0)
        self._adv_rb.pack(side="left", padx=(0,8))
        self._sim_rb = tk.Radiobutton(mf, text="Simple", variable=self._mode_var,
            value="simple", bg=C["card"], fg=C["green"], selectcolor=C["entry"],
            activebackground=C["card"], activeforeground=C["green"], font=FONT_B,
            indicatoron=1, bd=0, highlightthickness=0)
        self._sim_rb.pack(side="left")
        row += 1; pad_row()

        # BPM slider
        label(row, "BPM")
        sf2 = ttk.Frame(right, style="Card.TFrame")
        sf2.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        self._bpm_var = tk.IntVar(value=120)
        self._bpm_scale = ttk.Scale(sf2, from_=40, to=300,
            variable=self._bpm_var, orient="horizontal",
            command=self._on_bpm_slide)
        self._bpm_scale.pack(side="left", fill="x", expand=True)
        self._bpm_lbl = ttk.Label(sf2, text="120", width=4,
                                  style="Card.TLabel", font=FONT_B)
        self._bpm_lbl.pack(side="left", padx=(4,8))
        row += 1; pad_row()

        # Delay entry
        label(row, "Delay (s)")
        df = ttk.Frame(right, style="Card.TFrame")
        df.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        self._delay_var = tk.StringVar(value="0.270")
        de = tk.Entry(df, textvariable=self._delay_var, width=8,
                      bg=C["entry"], fg=C["text"], insertbackground=C["text"],
                      font=FONT_MONO, relief="flat", bd=0)
        de.pack(side="left", ipady=3)
        de.bind("<Return>", self._on_delay_edit)
        de.bind("<FocusOut>", self._on_delay_edit)
        ttk.Label(df, text="s/note", style="Card.TLabel").pack(side="left", padx=4)
        row += 1; pad_row()

        # Countdown
        label(row, "Countdown")
        cf = ttk.Frame(right, style="Card.TFrame")
        cf.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        self._cd_var = tk.IntVar(value=5)
        cd_spin = tk.Spinbox(cf, from_=1, to=30, width=4,
            textvariable=self._cd_var,
            bg=C["entry"], fg=C["text"], font=FONT, relief="flat", bd=0,
            buttonbackground=C["card"], insertbackground=C["text"])
        cd_spin.pack(side="left", ipady=2)
        ttk.Label(cf, text="seconds", style="Card.TLabel").pack(side="left", padx=4)
        row += 1; pad_row(); pad_row()

        # Play / Stop buttons
        btf = ttk.Frame(right, style="Card.TFrame")
        btf.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")
        self._play_btn = ttk.Button(btf, text="▶  PLAY", style="Play.TButton",
                                    command=self._play)
        self._play_btn.pack(side="left", fill="x", expand=True, padx=(0,4))
        self._stop_btn = ttk.Button(btf, text="■  STOP (F6)", style="Stop.TButton",
                                    command=self._stop_playback, state="disabled")
        self._stop_btn.pack(side="left", fill="x", expand=True, padx=(4,0))
        row += 1; pad_row()

        # Status
        self._status_var = tk.StringVar(value="Ready — pick a song")
        ttk.Label(right, textvariable=self._status_var,
                  style="Status.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(4,2))
        row += 1

        # Progress bar
        self._prog = ttk.Progressbar(right, style="green.Horizontal.TProgressbar",
                                     mode="determinate", maximum=100)
        self._prog.grid(row=row, column=0, columnspan=2,
                        sticky="ew", padx=12, pady=(2,8))
        row += 1; pad_row()

        # ─── Bottom: sheet preview ───────────────────────────────────
        pv = ttk.Frame(self.root, style="Panel.TFrame")
        pv.pack(fill="x", padx=16, pady=(0,12))
        ttk.Label(pv, text="Sheet Preview", style="Panel.TLabel",
                  font=FONT_B).pack(anchor="w", padx=8, pady=(6,2))
        self._preview = tk.Text(pv, height=3, bg=C["entry"], fg=C["dim"],
                                font=FONT_MONO, relief="flat", bd=0, wrap="word",
                                state="disabled", insertbackground=C["text"])
        self._preview.pack(fill="x", padx=8, pady=(0,8))

    # ── List helpers ─────────────────────────────────────────────────────
    def _all_items(self):
        """Return combined list: built-in + custom."""
        items = []
        for i, s in enumerate(self._all_songs):
            tag = "ADV" if s["mode"] == "advanced" else "SIM"
            items.append({"idx": i, "custom": False,
                          "display": f"{i+1}. {s['name']}  [{tag}]",
                          **s})
        for i, s in enumerate(self._customs):
            tag = "ADV" if s.get("mode","advanced") == "advanced" else "SIM"
            items.append({"idx": i, "custom": True,
                          "display": f"★ {s['name']}  [{tag}]",
                          **s})
        return items

    def _refresh_list(self):
        q = self._search_var.get().lower()
        self._items = [it for it in self._all_items()
                       if q in it["display"].lower()]
        self._lb.delete(0, "end")
        for it in self._items:
            self._lb.insert("end", it["display"])

    def _on_select(self, _evt=None):
        sel = self._lb.curselection()
        if not sel: return
        it = self._items[sel[0]]
        self._current_song = it
        self._mode_var.set(it["mode"])
        bpm = it.get("bpm", 120)
        self._updating = True
        self._bpm_var.set(bpm)
        self._bpm_lbl.config(text=str(bpm))
        self._delay_var.set(f"{60/(bpm*1.85):.3f}")
        self._updating = False
        # Preview
        self._preview.config(state="normal")
        self._preview.delete("1.0", "end")
        self._preview.insert("1.0", it["sheet"][:500] + ("…" if len(it["sheet"])>500 else ""))
        self._preview.config(state="disabled")
        self._status_var.set(f"Selected: {it['name']}")

    # ── BPM ↔ Delay sync ────────────────────────────────────────────────
    def _on_bpm_slide(self, val):
        if self._updating: return
        bpm = int(float(val))
        self._bpm_lbl.config(text=str(bpm))
        self._updating = True
        self._delay_var.set(f"{60/(bpm*1.85):.3f}")
        self._updating = False

    def _on_delay_edit(self, _evt=None):
        if self._updating: return
        try:
            d = float(self._delay_var.get())
            if d <= 0: return
            bpm = int(60 / (d * 1.85))
            bpm = max(40, min(300, bpm))
            self._updating = True
            self._bpm_var.set(bpm)
            self._bpm_lbl.config(text=str(bpm))
            self._updating = False
        except ValueError:
            pass

    # ── Import / Paste ───────────────────────────────────────────────────
    def _import_file(self):
        fp = filedialog.askopenfilename(
            title="Import sheet",
            filetypes=[("Text files","*.txt"),("All","*.*")])
        if not fp: return
        try:
            with open(fp, 'r') as f: sheet = f.read().strip()
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        name = os.path.splitext(os.path.basename(fp))[0]
        self._add_custom(name, sheet)

    def _paste_sheet(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Paste Sheet")
        dlg.geometry("500x320")
        dlg.configure(bg=C["bg"])
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Song name:").pack(anchor="w", padx=12, pady=(12,2))
        name_var = tk.StringVar(value="My Song")
        tk.Entry(dlg, textvariable=name_var, bg=C["entry"], fg=C["text"],
                 font=FONT, relief="flat", insertbackground=C["text"]).pack(
            fill="x", padx=12, ipady=3)

        ttk.Label(dlg, text="Sheet (raw keys):").pack(anchor="w", padx=12, pady=(8,2))
        txt = tk.Text(dlg, height=8, bg=C["entry"], fg=C["text"],
                      font=FONT_MONO, relief="flat", wrap="word",
                      insertbackground=C["text"])
        txt.pack(fill="both", expand=True, padx=12, pady=(0,4))

        # Tempo tag help
        help_text = ("Tempo tags:  SLOW · FAST · SLOWER · FASTER · "
                     "RESET · BPM80 BPM120 BPM160 …")
        ttk.Label(dlg, text=help_text, style="Dim.TLabel").pack(
            anchor="w", padx=12, pady=(0,8))

        def confirm():
            s = txt.get("1.0","end").strip()
            n = name_var.get().strip() or "Untitled"
            if not s:
                messagebox.showwarning("Empty", "Paste a sheet first"); return
            self._add_custom(n, s)
            dlg.destroy()

        ttk.Button(dlg, text="✓ Add", style="Play.TButton",
                   command=confirm).pack(pady=(0,12))

    def _add_custom(self, name, sheet):
        entry = {"name": name, "mode": self._mode_var.get(),
                 "bpm": self._bpm_var.get(), "sheet": sheet}
        self._customs.append(entry)
        save_custom_sheets(self._customs)
        self._refresh_list()
        self._status_var.set(f"Added custom sheet: {name}")

    def _delete_custom(self):
        sel = self._lb.curselection()
        if not sel: return
        it = self._items[sel[0]]
        if not it.get("custom"):
            messagebox.showinfo("Info", "Can only delete custom sheets"); return
        if messagebox.askyesno("Delete", f"Delete '{it['name']}'?"):
            self._customs.pop(it["idx"])
            save_custom_sheets(self._customs)
            self._current_song = None
            self._refresh_list()

    # ── Playback ─────────────────────────────────────────────────────────
    def _play(self):
        if self._playing: return
        if not self._current_song:
            self._status_var.set("No song selected!")
            return
        hwnd = find_roblox_hwnd()
        if not hwnd:
            messagebox.showwarning("Roblox not found",
                "Could not find the Roblox window.\n"
                "Open Roblox and equip the piano first.")
            return

        self._playing = True
        self._play_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._prog["value"] = 0

        song  = self._current_song
        mode  = self._mode_var.get()
        try:
            delay = float(self._delay_var.get())
        except ValueError:
            delay = 0.2
        chord = max(0.01, delay * 0.12)
        cd    = self._cd_var.get()

        def run():
            # Countdown
            for i in range(cd, 0, -1):
                if self._stop.is_set():
                    self._finish("Stopped"); return
                self._status_var.set(f"Starting in {i}…  Switch to Roblox!")
                time.sleep(1)

            try: focus_roblox(hwnd)
            except Exception: pass

            self._status_var.set(f"Playing: {song['name']}")
            ok = play_sheet(song["sheet"], mode, delay, chord,
                            self._stop, self._progress_cb,
                            base_bpm=self._bpm_var.get())
            self._finish("Done!" if ok else "Stopped (F6)")

        t = threading.Thread(target=run, daemon=True)
        t.start()

    def _stop_playback(self):
        self._stop.set()

    def _progress_cb(self, cur, total):
        self._pq.put((cur, total))

    def _finish(self, msg):
        self._playing = False
        self._stop.clear()
        self.root.after(0, lambda: self._play_btn.config(state="normal"))
        self.root.after(0, lambda: self._stop_btn.config(state="disabled"))
        self.root.after(0, lambda: self._status_var.set(msg))
        self.root.after(0, lambda: self._prog.configure(value=100 if "Done" in msg else 0))

    def _poll(self):
        try:
            while True:
                cur, total = self._pq.get_nowait()
                pct = int(cur / max(total,1) * 100)
                self._prog["value"] = pct
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    # ── F6 watcher ───────────────────────────────────────────────────────
    def _start_f6(self):
        VK_F6 = 0x75
        def watch():
            was = False
            while True:
                down = bool(user32.GetAsyncKeyState(VK_F6) & 0x8000)
                if down and not was:
                    self._stop.set()
                was = down
                time.sleep(0.05)
        t = threading.Thread(target=watch, daemon=True)
        t.start()


# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app = PianoBotApp(root)
    root.mainloop()
