# 🎹 JJS Piano Bot

**Auto-play piano sheets in Jujutsu Shenanigans (Roblox)**
**NOTE: How good or bad the songs turns out entirely depends on the sheet provided, the pre-added 30 songs were used for testing and may or may not be upto the mark**

A Windows desktop app that plays piano emote songs automatically using DirectInput scan codes — the same signals Roblox reads from your keyboard, so it *actually works*.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

- **30+ built-in songs** — Megalovania, Giorno's Theme, Gurenge, Blue Bird, and more
- **Simple & Advanced piano modes** — supports both JJS piano configurations
- **Variable Tempo** — songs can speed up and slow down mid-playback with inline tempo tags
- **Custom sheet import** — paste or load `.txt` files with your own sheets
- **BPM slider + delay control** — fine-tune playback speed per song
- **F6 emergency stop** — instantly halt playback at any time
- **Dark themed GUI** — sleek, modern interface built with tkinter
- **Standalone .exe** — no Python installation needed for end users

---

## 🚀 Quick Start

### Option 1: Download the .exe (easiest)

1. Go to the [**Releases**](../../releases) page
2. Download `JJS_Piano_Bot.exe`
3. Run it — no installation needed!

### Option 2: Run from source

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/JJS-Piano-Bot.git
cd JJS-Piano-Bot

# Install the one dependency
pip install -r requirements.txt

# Run the GUI app
python jjs_piano_gui.py
```

---

## 🎮 How to Use

1. Open **Roblox** → **Jujutsu Shenanigans**
2. Equip the **Piano emote** (press `B` → Piano)
3. Set the piano to the correct mode:
   - **Advanced** for songs 1–21 (number keys + shift)
   - **Simple** for songs 22–30 (full letter keyboard)
4. **DO NOT** open the chat bar — leave the piano active
5. Open JJS Piano Bot → pick a song → click **▶ PLAY**
6. Switch to Roblox during the countdown
7. Press **F6** at any time to stop

---

## 🎵 Song List

| # | Song | BPM |
|---|------|-----|
| 1 | Megalovania | 160 |
| 2 | Giorno's Theme | 110 |
| 3 | Despacito | 130 |
| 4 | Specialz - JJK OP | 135 |
| 5 | An Enigmatic Encounter | 115 |
| 6 | Naruto - Blue Bird | 125 |
| 7 | Hunter x Hunter - Departure | 120 |
| 8 | Cruel Angel's Thesis | 130 |
| 9 | Fire Force OP | 140 |
| 10 | Your Lie in April | 115 |
| 11 | One Punch Man OP | 145 |
| 12 | Gurenge - Demon Slayer | 135 |
| 13 | Fallen Down - Undertale | 90 |
| 14 | Undertale OST | 100 |
| 15 | FNAF Theme | 115 |
| 16 | Ballin' | 120 |
| 17 | You Are My Sunshine | 110 |
| 18 | Treachery | 120 |
| 19 | Gojo Honored One (Numbers) | 100 |
| 20 | Hollow Purple | 120 |
| 21 | Malevolent Shrine | 130 |

| # | Song | BPM |
|---|------|-----|
| 22 | KaiKai Kitan - JJK OP | 140 |
| 23 | Super Mario Bros Theme | 145 |
| 24 | Naruto - Silhouette | 135 |
| 25 | Viva La Vida | 138 |
| 26 | Merry Go Round of Life | 108 |
| 27 | Gojo Honored One (Letters) | 100 |
| 28 | Minecraft Theme | 95 |
| 29 | Fur Elise | 100 |
| 30 | Black Clover OP | 140 |

---

## 🎛️ Variable Tempo (Speed Changes)

Songs can change speed mid-playback using **tempo tags** embedded in the sheet:

| Tag | Effect |
|-----|--------|
| `SLOW` | 30% slower |
| `FAST` | 30% faster |
| `SLOWER` | 50% slower |
| `FASTER` | 50% faster |
| `BPM80` | Set exact BPM to 80 |
| `BPM120` | Set exact BPM to 120 |
| `BPM160` | Set exact BPM to 160 |
| `RESET` | Return to original BPM |

### Example

```
BPM90 6 3 6 3 6 3 FAST 6 3 6 3 6 3 BPM160 2 1 3 RESET 1 2 5 R 5
```

This plays the first 6 notes slow, speeds up for the next 6, blasts through 3 notes at 160 BPM, then returns to the song's default speed.

### How to use in custom sheets

When pasting a custom sheet, just type the tempo tags inline with the notes. The bot skips over them during playback and adjusts speed immediately.

---

## 📋 Custom Sheets

You can add your own songs:

- **Paste Sheet** — Click "📋 Paste Sheet" in the app, name your song, paste the notes
- **Import File** — Click "📂 Import Sheet" and load a `.txt` file
- Custom sheets are saved to `custom_sheets.json` next to the app

### Sheet Notation

| Symbol | Meaning |
|--------|---------|
| `a` – `z`, `0` – `9` | Single key press |
| `A` – `Z` (uppercase) | Shift + key (black keys) |
| `[abc]` | Chord — press all keys together |
| `PAUSE` | Long pause (~0.45s) |
| `BPAUSE` | Brief pause (~0.20s) |
| Space | Short gap between notes |

---

## 🔧 Building the .exe

```bash
# Install build tools
pip install pyinstaller

# Build
pyinstaller --onefile --noconsole --name "JJS_Piano_Bot" jjs_piano_gui.py

# Output: dist/JJS_Piano_Bot.exe
```

Or just double-click `build_exe.bat`.

---

## ⚠️ Safety Notes

- **Move mouse to top-left corner** of screen to trigger failsafe
- **F6** stops playback instantly
- **Ctrl+C** in terminal to stop the CLI version
- This tool sends keyboard inputs via DirectInput — the same as a real keyboard
- **Not a cheat/exploit** — it just presses keys for you

---

## 📝 License

MIT License — free to use, modify, and share.

---

## 🤝 Contributing

Found a bug? Want to add a song? Open an issue or PR!

1. Fork the repo
2. Add your changes
3. Submit a pull request
