# 3AM Snack

**Repository:** [github.com/TiyahSingh/3AM-Snack](https://github.com/TiyahSingh/3AM-Snack)

A playful **cartoon kitchen** snack quest built with **Pygame**: raid the fridge, wrangle the microwave, cut sausage, pan-cook heat, assemble a guided sandwich with two **“your pick”** slots, then finish the snack bite-by-bite with character reactions (**good / confused / lose**).

## Features (short)

- **Fridge mystery tubs** — keep or discard hidden ingredients; picks drive the **final taste stack**.
- **Microwave** — stop timing matters; disturbances can haunt later steps with flashes / beeping.
- **Cutting → cooking → assembly** — full chain into a **seven-layer sandwich guide** (+ two freestyle layers).
- **Final eating scene** — tap bites until the munch counter clears; moods match outcome bands.

## Installation

Uses a virtual environment (`venv`) is recommended.

```bash
cd 3AM_Snack
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Runtime

```bash
python main.py
```

Resize the window as you like (`pygame.RESIZABLE`).

### pygame vs pygame-ce

This project imports `pygame`. **pygame-ce** is a maintained drop-in fork and often installs as `pip install pygame-ce` while still exposing the `pygame` module once installed — use whichever suits your Python version. Standard `pip install pygame` is fine when wheels exist for your platform.

## Project layout

| Path | Purpose |
|------|---------|
| `main.py` | Full game implementation |
| `requirements.txt` | Python dependencies |
| `plan.md` | Milestones & task list |
| `refinements-changes.md` | Design / scope changelog |
| `readme.md` | This file |

## Credits

- **Design & gameplay** — your project iteration (see git history).
- **AI-assisted authoring** — development and refactoring were iterated with **Cursor** (Composer / Agent) acting as coding assistant alongside you.

## AI tools disclosure

Assistant usage included: architecture discussion, refactoring a previously duplicated mega-file into a single maintained `main.py`, layout/text tuning, procedural drawing snippets, HOW TO PLAY content, sandwich assembly rules documentation, and this README/plan refinement log. Generated text and code remain subject to normal review and licensing of your codebase.

---

Enjoy your 3 AM sandwich.
