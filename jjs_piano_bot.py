"""
JJS PIANO BOT  -  Jujutsu Shenanigans Auto-Play Script
Uses pydirectinput (scan codes) so Roblox actually receives keys

HOW TO USE:
  1. Run AS ADMINISTRATOR if keys still don't register
  2. Open Roblox -> Jujutsu Shenanigans
  3. Equip the Piano emote (press B -> Piano)
  4. Set the piano to the correct mode (Simple or Advanced) -- see song list
  5. DO NOT open the chat bar -- the piano emote captures keys directly
  6. Pick your song, set your countdown, then CLICK ROBLOX to focus it.
     The script will auto-focus Roblox right before playback begins.

WHY THIS WORKS:
  Regular Python key-injection (pyautogui, ctypes SendInput) fails in Roblox
  because Roblox detects the LLMHF_INJECTED flag and ignores those events.
  pydirectinput sends DirectInput-compatible scan codes that look identical
  to real hardware key presses -- the same method Roblox reads from.

SAFETY:
  - Ctrl+C in this terminal at any time to stop
  - Move mouse to top-left corner to trigger failsafe

NOTATION LEGEND:
  - Letters/digits in sequence -> press one by one
  - UPPERCASE letter           -> Shift held (black key / sharp)
  - [abc]                      -> chord: all keys pressed together
  - PAUSE                      -> long pause (~0.45 s)
  - BPAUSE                     -> brief pause (~0.20 s)
"""

import time
import sys
import os
import ctypes
import threading

# ---------------------------------------------------------------------------
# pydirectinput -- sends real DirectInput scan codes Roblox accepts
# ---------------------------------------------------------------------------
try:
    import pydirectinput
except ImportError:
    print("ERROR: pydirectinput not installed.")
    print("Run:  python -m pip install pydirectinput")
    sys.exit(1)

pydirectinput.PAUSE = 0.0
pydirectinput.FAILSAFE = True   # move mouse to top-left to abort

# ---------------------------------------------------------------------------
# WINDOW HELPERS
# ---------------------------------------------------------------------------
user32 = ctypes.windll.user32

def find_roblox_hwnd():
    """Return the Roblox window handle, or 0 if not found."""
    return user32.FindWindowW(None, "Roblox")

def focus_roblox(hwnd):
    """Bring the Roblox window to the foreground."""
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)


# ---------------------------------------------------------------------------
# F6 STOP SWITCH
# A daemon thread polls Windows GetAsyncKeyState every 50 ms.
# When F6 is detected, it sets _stop_flag so play_sheet exits cleanly.
# ---------------------------------------------------------------------------

VK_F6     = 0x75
_stop_flag = threading.Event()

def _hotkey_watcher():
    was_down = False
    while True:
        down = bool(user32.GetAsyncKeyState(VK_F6) & 0x8000)
        if down and not was_down:
            _stop_flag.set()
        was_down = down
        time.sleep(0.05)

_watcher_thread = threading.Thread(target=_hotkey_watcher, daemon=True)
_watcher_thread.start()

# ---------------------------------------------------------------------------
# KEY PRESS PRIMITIVES
# ---------------------------------------------------------------------------

def _pdi_key(ch):
    return ch.lower()

def key_down(ch):
    try:
        pydirectinput.keyDown(_pdi_key(ch))
    except Exception:
        pass

def key_up(ch):
    try:
        pydirectinput.keyUp(_pdi_key(ch))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

SPACE_PAUSE    = 0.07
DASH_PAUSE     = 0.10
PAUSE_DURATION = 0.45
BPAUSE_DURATION = 0.20

# ---------------------------------------------------------------------------
# MODE / SHIFT LOGIC
#
# ADVANCED piano (1-octave):
#   White keys: 1 2 3 4 5 6 7 8 9 0
#   Black keys: Q E R T Y U P  (Shift held)
#
# SIMPLE piano (full keyboard):
#   White keys: 1-0, q w e r t y u i o p a s d f g h j k l z x c v b n m
#   Black keys: uppercase letters that appear in sheets
#   NOTE: R and U are white keys on simple, so songs using R/U as black
#         keys must be set to "advanced" mode.
# ---------------------------------------------------------------------------

ADV_BLACK = set('QERTYUP')

def needs_shift(ch, mode):
    if mode == "advanced":
        return ch.upper() in ADV_BLACK
    else:
        return ch.isupper() and ch.isalpha()

# ---------------------------------------------------------------------------
# KEY ENGINE
# ---------------------------------------------------------------------------

def press_single(ch, mode, note_delay, chord_delay):
    if ch in ('-', ' '):
        return
    if not (ch.isalpha() or ch.isdigit()):
        return

    use_shift = needs_shift(ch, mode)
    if use_shift:
        key_down('shift')
        time.sleep(chord_delay)
    key_down(ch)
    time.sleep(chord_delay)
    key_up(ch)
    if use_shift:
        time.sleep(chord_delay)
        key_up('shift')
    time.sleep(note_delay)


def press_chord(chars, mode, chord_delay, note_delay):
    keys = []
    use_shift = False
    for ch in chars:
        if ch in ('-', ' '):
            continue
        if not (ch.isalpha() or ch.isdigit()):
            continue
        keys.append(ch)
        if needs_shift(ch, mode):
            use_shift = True
    if not keys:
        return
    if use_shift:
        key_down('shift')
        time.sleep(chord_delay)
    for ch in keys:
        key_down(ch)
        time.sleep(chord_delay)
    time.sleep(chord_delay)
    for ch in reversed(keys):
        key_up(ch)
        time.sleep(chord_delay)
    if use_shift:
        key_up('shift')
    time.sleep(note_delay)


_CONTROL_WORDS = {"PAUSE", "BPAUSE", "SLOW", "FAST", "SLOWER", "FASTER", "RESET"}

def _is_bpm_token(word):
    """Check if word is a BPM### token like BPM80, BPM160."""
    return (len(word) >= 4 and word[:3] == 'BPM' and word[3:].isdigit())

def tokenise(sheet):
    tokens = []
    i = 0
    while i < len(sheet):
        ch = sheet[i]
        if ch == '[':
            j = sheet.find(']', i + 1)
            if j == -1:
                j = len(sheet) - 1
            tokens.append(sheet[i:j + 1])
            i = j + 1
        elif ch == ' ':
            if tokens and tokens[-1] != ' ':
                tokens.append(' ')
            i += 1
        else:
            j = i
            while j < len(sheet) and sheet[j] not in (' ', '[', ']'):
                j += 1
            word = sheet[i:j]
            if word in _CONTROL_WORDS or _is_bpm_token(word):
                tokens.append(word)
            else:
                for c in word:
                    tokens.append(c)
            i = j
    return tokens


# ---------------------------------------------------------------------------
# TEMPO MULTIPLIERS
#
# SLOW / FAST     = gentle 30% shift
# SLOWER / FASTER = aggressive 50% shift
# BPM###          = jump to exact BPM  (e.g. BPM80, BPM160)
# RESET           = return to original BPM
# ---------------------------------------------------------------------------

TEMPO_MULT = {
    "SLOW":   0.70,
    "FAST":   1.30,
    "SLOWER": 0.50,
    "FASTER": 1.50,
}

def _bpm_to_delay(bpm):
    """Convert a BPM value to note delay in seconds."""
    return 60.0 / (bpm * 1.85)

def play_sheet(sheet, mode, note_delay, chord_delay, base_bpm=120):
    _stop_flag.clear()          # reset before each song
    tokens = tokenise(sheet)

    # Live tempo state
    orig_delay = note_delay
    orig_chord = chord_delay
    orig_bpm   = base_bpm
    cur_bpm    = base_bpm

    for tok in tokens:
        if _stop_flag.is_set():  # F6 was pressed
            raise KeyboardInterrupt

        # ── Tempo control tokens ────────────────────────────────
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

        # ── Normal playback tokens ──────────────────────────────
        if tok == ' ':
            time.sleep(SPACE_PAUSE)
        elif tok == 'PAUSE':
            time.sleep(PAUSE_DURATION)
        elif tok == 'BPAUSE':
            time.sleep(BPAUSE_DURATION)
        elif tok == '-':
            time.sleep(DASH_PAUSE)
        elif tok.startswith('[') and tok.endswith(']'):
            press_chord(tok[1:-1], mode, chord_delay, note_delay)
        elif len(tok) == 1:
            press_single(tok, mode, note_delay, chord_delay)

# ---------------------------------------------------------------------------
# SONG LIBRARY
#
# ADVANCED songs: use piano in ADVANCED mode
#   - White keys: number keys 1-0
#   - Black keys: Q E R T Y U P (hold Shift)
#
# SIMPLE songs: use piano in SIMPLE mode
#   - Uses the full letter keyboard across multiple octaves
# ---------------------------------------------------------------------------

SONGS = {

    # == ADVANCED MODE SONGS =================================================

    "1. Megalovania": {
        "mode": "advanced",
        "bpm_hint": 160,
        "sheet": "2 2 9 6 T 5 4 2 4 5 "
                 "1 1 9 6 T 5 4 2 4 5 "
                 "2 2 9 6 T 5 4 2 4 5 "
                 "1 1 9 6 T 5 4 2 1 "
                 "4 4 4 4 2 2 "
                 "4 4 4 5 T 5 4 2 4 5 "
                 "4 4 4 5 T 6 8 6 9 9 9 6 9 8 "
                 "6 6 6 6 6 5 5 "
                 "6 6 6 6 5 6 9 6 5 "
                 "9 6 5 4 8 5 4 3 1 2 3 4 8 "
                 "4 2 4 5 T 5 4 2 T 5 4 5 "
                 "T 6 8 6 T 5 4 2 3 4 5 T 8 U T T 5 4 5"
    },

    "2. Giorno's Theme": {
        "mode": "advanced",
        "bpm_hint": 110,
        "sheet": "2 R 2 2 3 4 3 2 Q 2 3 2 R 2 4 7 "
                 "2 Q 6 5 "
                 "2 R 2 2 3 4 3 2 Q 2 3 2 R 2 4 7 7 U 1 5 7 9 5 R Q 4 9 Y 7"
    },

    "3. Despacito": {
        "mode": "advanced",
        "bpm_hint": 130,
        "sheet": "9 U 7 9 U 7 6 5 9 U 7 6 R 9 U 9 0 U "
                 "9 U 7 R 7 U 9 0 9 U 7 6 5 9 9 "
                 "9 6 9 6 9 6 9 0 U 7 R 7 U 9 0 9 U 7 6 5 9 0 "
                 "9 6 9 6 9 6 9 0 U 9 U 7 "
                 "R 7 7 U 9 U 9 U 9 9 U 7 5 7 7 U 9 U 9 U 9 0 6 "
                 "6 6 6 6 9 U 9 U 9 0 0 U 9 U 7 "
                 "R 7 7 U 9 U 9 U 9 9 U 7 5 7 7 U 9 U 9 U 9 0 6 "
                 "6 6 6 6 9 U 9 U 9 0 0 U "
                 "9 U 7 R R R R R 7 7 7 7 7 6 7 5 "
                 "5 5 5 5 7 7 7 7 7 7 U 9 6 6 6 6 "
                 "9 9 9 9 9 0 0 U"
    },

    "4. Specialz - JJK OP": {
        "mode": "advanced",
        "bpm_hint": 135,
        "sheet": "2 2 7 "
                 "6 7 9 7 6 7 7 "
                 "5 6 7 9 7 6 7 7 "
                 "2 2 5 5 2 2 5 6 5 9 8 7 6 5 5 "
                 "5 6 7 6 "
                 "6 6 7 9 7 "
                 "2 2 7 "
                 "6 7 9 7 6 7 7 "
                 "5 5 6 7 9 7 6 7 5 "
                 "5 5 6 7 7 0 P "
                 "9 7 6 5 5 "
                 "5 6 7 6 "
                 "6 6 7"
    },

    "5. An Enigmatic Encounter": {
        "mode": "advanced",
        "bpm_hint": 115,
        "sheet": "8 7 8 6 7 8 6 5 3 2 1 2 "
                 "8 7 8 "
                 "6 7 8 9 8 7 6 T "
                 "8 7 8 "
                 "6 7 8 6 5 3 2 1 2 "
                 "8 7 8 "
                 "6 7 8 9 8 7 6 T "
                 "8 7 8 "
                 "6 7 8 6 5 3 2 1 2 "
                 "8 7 8 "
                 "6 7 8 9 8 7 6 T"
    },

    "6. Naruto - Blue Bird": {
        "mode": "advanced",
        "bpm_hint": 125,
        "sheet": "Q R T 6 T R "
                 "Q R T 6 7 6 7 U "
                 "Q R T 6 T R "
                 "R U 7 R U 7 3 3 R R "
                 "BPAUSE "
                 "6 T T 6 6 T 3 R 3 R 4 Q R T 6 Q 6 T R 3 R 1 2 Q "
                 "Q Q Q 2 3 R 3 3 3 R T 6 T "
                 "Q R T 6 Q 6 T R 3 R 1 2 Q Q Q Q 2 6 T R 3 R R "
                 "BPAUSE "
                 "Q R T 6 6 T 6 T T T 6 7 7 6 T R "
                 "R 6 7 U R 6 7 U U 0 9 U"
    },

    "7. Hunter x Hunter - Departure": {
        "mode": "advanced",
        "bpm_hint": 120,
        "sheet": "4 E 2 E 4 4 4 2 4 "
                 "4 E 2 4 R R R 2 R "
                 "R E 2 R 5 5 5 2 5 "
                 "4 5 T Y Y"
    },

    "8. Cruel Angel's Thesis - Evangelion": {
        "mode": "advanced",
        "bpm_hint": 130,
        "sheet": "1 E 4 E 4 2 4 2 4 2 Y T E 5 4 E 5 "
                 "E 5 Y 8 T 4 E 2 2 1 2 "
                 "2 E E 1 E 4 E 4 2 4 2 4 2 Y 2 T E 5 4 E 5 "
                 "E 5 Y T 8 4 E Y Y 5 Y 4 Y 5 8 "
                 "1 E 4 E 4 2 4 2 4 2 Y 2 T E 5 4 E 5 "
                 "E 5 Y T 8 4 E 2 Y 2 Y 2 5 2 Y 4 Y 5 8"
    },

    "9. Fire Force OP": {
        "mode": "advanced",
        "bpm_hint": 140,
        "sheet": "Q 3 Q 3 Q U 3 T 7 R 3 "
                 "3 0 E 6 P Q U E T 7 "
                 "Q U 3 T 7 R 1 E R 3 3 3 T 7 "
                 "T Q 3 T Q E 3 3 E R 3 1 3 1 "
                 "3 R T 3 Q 3 6 "
                 "T R 3 E R 6 T R 3 3"
    },

    "10. Your Lie in April": {
        "mode": "advanced",
        "bpm_hint": 115,
        "sheet": "T R 4 R T "
                 "6 T 6 7 3 3 7 6 T 6 "
                 "6 T 6 7 6 7 U "
                 "6 T 6 7 3 7 6 T 6 "
                 "U U U 7 6 T R "
                 "6 T 6 7 3 7 6 T 6 "
                 "3 6 T 6 7 0 9 U "
                 "U U U 7 6 7 U 9 U "
                 "3 U U U 7 6 T R"
    },

    "11. One Punch Man OP": {
        "mode": "advanced",
        "bpm_hint": 145,
        "sheet": "4 4 4 4 4 5 4 3 4 5 "
                 "5 R 2 3 3 2 3 R 5 6 R 3 "
                 "2 R 2 2 2 Q 1 Q 3 2 "
                 "5 R 2 3 3 2 2 6 6 6 6 6 5 R 3 R 2 "
                 "[36] [36] [36] [36] "
                 "5 R 2 3 3 2 3 R 5 6 R 3 "
                 "2 R 2 2 2 Q 1 Q 3 2 "
                 "5 R 2 3 3 2 6 6 6 6 6 5 R 3 R 2 "
                 "6 6 6 6 6 7"
    },

    "12. Gurenge - Demon Slayer": {
        "mode": "advanced",
        "bpm_hint": 135,
        "sheet": "Q 6 Q 5 Q Y Q 6 2 5 2 4 2 3 2 4 "
                 "Q 6 Q 5 Q Y Q 6 1 4 8 4 Y 4 6 4 T "
                 "Q 6 Q 5 Q Y Q 6 2 5 2 4 2 3 2 4"
    },

    "13. Fallen Down - Undertale": {
        "mode": "advanced",
        "bpm_hint": 90,
        "sheet": "6 3 6 3 6 3 6 3 6 3 6 3 "
                 "2 1 3 "
                 "1 2 5 R 5 6 R 2 "
                 "6 2 6 2 6 2 6 Q 6 Q Y "
                 "6 4 6 4 5 6 5 4 3"
    },

    "14. Undertale OST": {
        "mode": "advanced",
        "bpm_hint": 100,
        "sheet": "Y 5 4 E 2 E 4 "
                 "9 U 8 Y "
                 "1 "
                 "Y 5 4 E 4 5 2 "
                 "4 "
                 "4 E 2 E"
    },

    "15. FNAF Theme": {
        "mode": "advanced",
        "bpm_hint": 115,
        "sheet": "9 0 9 7 7 7 6 7 8 7 8 6 9 7 5 3 6 E"
    },

    "16. Ballin'": {
        "mode": "advanced",
        "bpm_hint": 120,
        "sheet": "6 7 6 7 8 7 6 5 7 "
                 "9 9 9 9 7 "
                 "9 9 9 9 9 9 9 9 0 "
                 "9 9 9 9 7 0 7 6 5 5 "
                 "9 9 9 9 7 0 7 6 5 5 "
                 "7 7 7 7 7 6 5 5 6 6 5 6 7 8 8 7 6 5 6 6 5 9 7 "
                 "8 8 7 6 5 6 6 5 9 7 "
                 "9 9 0 "
                 "7 7 6 6 6 5 9 7 "
                 "7 7 7 8 7 6 5 6 6 6 5 6 3"
    },

    "17. You Are My Sunshine": {
        "mode": "advanced",
        "bpm_hint": 110,
        "sheet": "1 1 2 3 3 3 2 3 1 1 1 2 3 4 6 6 5 4 3 "
                 "1 2 3 4 6 6 5 4 3 1 1 2 3 4 2 2 3 1"
    },

    "18. Treachery": {
        "mode": "advanced",
        "bpm_hint": 120,
        "sheet": "6 7 8 7 6 7 8 9 8 7 8 "
                 "6 7 8 7 6 7 8 9 8 7 8 "
                 "6 7 8 7 6 7 8 9 8 7 6 8 0"
    },

    "19. Gojo Honored One (Numbers)": {
        "mode": "advanced",
        "bpm_hint": 100,
        "sheet": "4 6 7 8 7 6 4 6 7 8 7 6 "
                 "3 5 7 8 7 5 "
                 "3 5 7 9 7 5 "
                 "2 4 6 8 6 4 2 4 6 8 6 4 "
                 "1 3 6 7 6 3 "
                 "1 3 6 7 6 3"
    },

    "20. Hollow Purple": {
        "mode": "advanced",
        "bpm_hint": 120,
        "sheet": "u r t r u r Q w "
                 "r u r t r e w o "
                 "I u Y p 3 5 7 [uf3] "
                 "5 [ra7] 3 5 7 [ts3] 5 [ra7] "
                 "3 5 7 [uf3] 5 [ra7] 3 5 "
                 "7 [QI3] [wo5] [ra7] 3 5 7 [uf3] "
                 "5 [ra7] 3 5 7 [ts3] 5 [ra7] "
                 "3 5 7 [ep3] 5 [wo7] 3 5 "
                 "7 I o a 3 u [r3] r "
                 "[t3] r 3 r 3 u [r3] o "
                 "[I3] u Y 3 Y I 3 u "
                 "PAUSE "
                 "3 [uf] [ra3] [ra] [ts3] [ra] 3 [ra] "
                 "3 [uf] [ra3] [oh] [IG3] [uf] [YD] 3 "
                 "[YD] [IG] 3 o [I3] u Y 3 "
                 "t r 3 0 0 0 0 r "
                 "r r r t t r 3 3 "
                 "3 3 8 8 7 7 5 5"
    },

    "21. Malevolent Shrine": {
        "mode": "advanced",
        "bpm_hint": 130,
        "sheet": "3 5 8 7 "
                 "6 [79] 8 6 [t7] 3 "
                 "5 [25] 4 3 4 y [e7] "
                 "3 [t0] 8 7 9 [q6u] [q6u]"
    },

    # == SIMPLE MODE SONGS ===================================================

    "22. KaiKai Kitan - JJK OP": {
        "mode": "simple",
        "bpm_hint": 140,
        "sheet": "P h s g d P p P S s P P s P P P g d P s P s d s P "
                 "P h s g d P p P S s P P s P P P g d P s P s S s P "
                 "J t y y t y t y y t y t y E E o o i y t E "
                 "t y t y t y t y t y t y y y w w o o i y t "
                 "t y t y t y y t y t t y t y E o o i y t E "
                 "t y t y t y t y t y t y t y w o i o p P "
                 "g d P P P P P P J j g d P P s P P g d s P g d s P P P s P "
                 "s d d d d J j P P P J j J P P P J j J P P P P h "
                 "g g d d D g d s P P g g P P P g g P P P p P s "
                 "s d d J j P P P J j J P P P J j J P P P P h"
    },

    "23. Super Mario Bros Theme": {
        "mode": "simple",
        "bpm_hint": 145,
        "sheet": "f f f s f h o "
                 "s o u p a P p o "
                 "f h j g h f s d a "
                 "s o u p a P p o "
                 "f h j g h f s d a "
                 "h G g D f O p s p s d "
                 "h G g D f l l l "
                 "h G g D f O p s p s d "
                 "[DO] [id] [us] "
                 "s s s s d f s p o "
                 "s s s s d f "
                 "s s s s d f s p o f f f s f h o "
                 "f s o o p g g p a j j j h g f s p o"
    },

    "24. Naruto - Silhouette": {
        "mode": "simple",
        "bpm_hint": 135,
        "sheet": "G d f G d G G f d f j j f S f d "
                 "k j d k j d d S d f d "
                 "G d f G d d G f d f j j f S f d "
                 "k j d k j d d S d f d "
                 "BPAUSE "
                 "a G G d d G G d d k G d "
                 "a S d d S d f f f G f d f d "
                 "p d G G f d f f p S f h G f G f d "
                 "k j d k j d d S d f G d "
                 "p d G G f d f f p S f h G G G f d "
                 "k j d k j d d S j f G d"
    },

    "25. Viva La Vida": {
        "mode": "simple",
        "bpm_hint": 138,
        "sheet": "P s s s S P P O P P O s Y i "
                 "s s s s s s s S P P O P P O P s O o i "
                 "P s s s S P P O P P O s O o i "
                 "s s s s s S P O O s P O O s P O O D "
                 "g g g g S D D S D D S s "
                 "s s s s s s s S P O s P O O s P O O "
                 "D g g g D g D "
                 "P s S D D D s D s i o O "
                 "g g g D g D "
                 "P s S D s D D s D s i o O"
    },

    "26. Merry Go Round of Life": {
        "mode": "simple",
        "bpm_hint": 108,
        "sheet": "[36] 7 8 [29] "
                 "9 [83] "
                 "7 6 [71] "
                 "[71] 8 9 [03] "
                 "0 [04] 0 9 8 [91] "
                 "[61] 8 9 [03] "
                 "[92] 8 7 y 7 [83] "
                 "[72] 6 5 r 5 [51] 4 3 [31] 4 5 [63]"
    },

    "27. Gojo Honored One (Letters)": {
        "mode": "simple",
        "bpm_hint": 100,
        "sheet": "i p a s a p "
                 "i p a s a p "
                 "i p a s a p "
                 "i p a s a p "
                 "u o a s a o "
                 "u o a d a o "
                 "u o a d a o "
                 "u o a f a o "
                 "y p s h s p "
                 "y p s h s p "
                 "y p s h s p "
                 "y p s h s p "
                 "t o f k f o "
                 "t o f k f o "
                 "t o f k f o "
                 "t o f l f o"
    },

    "28. Minecraft Theme (Letters)": {
        "mode": "simple",
        "bpm_hint": 95,
        "sheet": "r p a i y u t i p u "
                 "r d a p i y u t p i u "
                 "r p a d g f s d s p "
                 "r a p i y u t i p u "
                 "r p a i y u t i p u "
                 "r p a d d f s g i p u "
                 "i a p o u y t y u r "
                 "d a p o u f s d f a"
    },

    "29. Fur Elise": {
        "mode": "simple",
        "bpm_hint": 100,
        "sheet": "f d f d f a d s p e "
                 "t u p a 0 u o a s e "
                 "u f d f d f a d s p e "
                 "t u p a 0 u s a p e "
                 "a s d f t o g f d r "
                 "i f d s e u d s a "
                 "f d f d f a d s p e "
                 "t u p a 0 u o a s e "
                 "u f d f d f a d s p e "
                 "t u p a 0 u s a p e u"
    },

    "30. Black Clover OP": {
        "mode": "simple",
        "bpm_hint": 140,
        "sheet": "o o o d d s a p "
                 "f f a s s a p a "
                 "f f "
                 "f a a s a p a u "
                 "a p o i g h f z z l k j h k k j h k k j z k k z g h "
                 "h h h j j h g f h g f f g h g h j h g f d h g g x z l k "
                 "z z l k x z l k "
                 "g j c x z l k k k j g f g g x z l k "
                 "g j c x z l k z l l l l k k "
                 "h g f g f f g h g h j h g f d h g g l l l k k"
    },

}

# ---------------------------------------------------------------------------
# UI HELPERS
# ---------------------------------------------------------------------------

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def clr(code, text):
    return "\033[" + code + "m" + text + "\033[0m"

def print_banner():
    print(clr("96", "+=================================================================+"))
    print(clr("96", "|       JJS PIANO BOT  --  Jujutsu Shenanigans Piano             |"))
    print(clr("96", "|   pydirectinput scan codes  |  actually works in Roblox!       |"))
    print(clr("96", "+=================================================================+"))
    print()

def print_instructions():
    print(clr("93", "SETUP:"))
    print("  1. Open Roblox -> Jujutsu Shenanigans")
    print("  2. Equip Piano emote  (B -> Piano)")
    print("  3. Set piano mode to ADVANCED for songs 1-21, SIMPLE for 22-30")
    print("  4. " + clr("91", "DO NOT open the chat bar") + " -- leave the piano active")
    print("  5. Pick a song, set countdown, then CLICK ROBLOX before it hits 0")
    print("  " + clr("93", "STOP:") + "  Press " + clr("91", "F6") + " at any time to abort playback instantly")
    print()

def print_song_list():
    adv  = [(k, v) for k, v in SONGS.items() if v["mode"] == "advanced"]
    simp = [(k, v) for k, v in SONGS.items() if v["mode"] == "simple"]

    print(clr("95", "== ADVANCED MODE SONGS (set piano to ADVANCED) =="))
    for name, data in adv:
        print("  " + clr("97", name) + "  " + clr("90", "(BPM ~" + str(data["bpm_hint"]) + ")"))
    print()
    print(clr("92", "== SIMPLE MODE SONGS (set piano to SIMPLE) =="))
    for name, data in simp:
        print("  " + clr("97", name) + "  " + clr("90", "(BPM ~" + str(data["bpm_hint"]) + ")"))
    print()

def get_auto_delay(bpm):
    return 60 / (bpm * 1.85)

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    clear()
    print_banner()
    print_instructions()
    print_song_list()

    hwnd = find_roblox_hwnd()
    if not hwnd:
        print(clr("91", "WARNING: Roblox window not found! Open Roblox first, then re-run."))
        input("Press Enter to exit...")
        return
    print(clr("92", "Roblox window found (hwnd=" + str(hwnd) + ")"))
    print()

    song_names = list(SONGS.keys())

    while True:
        try:
            choice = input(clr("96", "Enter song number or name: ")).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n" + clr("91", "Exiting.")); return

        picked = None
        for name in song_names:
            num = name.split('.')[0].strip()
            if choice == num or choice.lower() in name.lower():
                picked = name
                break

        if picked is None:
            print(clr("91", "  Song not found -- try again."))
            continue
        break

    song       = SONGS[picked]
    mode       = song["mode"]
    bpm_hint   = song["bpm_hint"]
    auto_delay = get_auto_delay(bpm_hint)

    print()
    print(clr("93", "Selected: ") + clr("97", picked))
    print(clr("93", "Mode:     ") + ("Simple" if mode == "simple" else "Advanced"))
    print(clr("93", "BPM hint: ") + str(bpm_hint) + "  ->  auto delay " + str(round(auto_delay, 3)) + "s/note")
    print()

    speed_in   = input(clr("96", "Note delay (s) [Enter = " + str(round(auto_delay, 3)) + "]: ")).strip()
    note_delay = float(speed_in) if speed_in else auto_delay
    chord_delay = max(0.01, note_delay * 0.12)

    countdown_in = input(clr("96", "Countdown before playing [default 5s]: ")).strip()
    try:
        countdown = int(countdown_in) if countdown_in else 5
    except ValueError:
        countdown = 5

    print()
    print(clr("91", "Switch to Roblox NOW -- piano emote must be open!"))
    print(clr("90", "(Ctrl+C here at any time to stop)"))
    print()

    for i in range(countdown, 0, -1):
        print("  " + clr("93", str(i) + "...") + "  ", end='\r')
        time.sleep(1)

    try:
        focus_roblox(hwnd)
    except Exception:
        pass

    print(clr("92", "PLAYING: " + picked))
    print(clr("90", "  Press F6 or move mouse to corner to abort"))

    try:
        play_sheet(song["sheet"], mode, note_delay, chord_delay,
                   base_bpm=bpm_hint)
        print("\n" + clr("92", "Done! Song finished."))
    except KeyboardInterrupt:
        print("\n" + clr("91", "Stopped."))

    print()
    try:
        again = input(clr("96", "Play another song? (y/n): ")).strip().lower()
    except (KeyboardInterrupt, EOFError):
        again = 'n'
    if again == 'y':
        main()
    else:
        print(clr("96", "Bye!"))

if __name__ == "__main__":
    main()
