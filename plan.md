# 3AM Snack — Development plan

## Vision

Late-night cartoon kitchen adventure: procedural UI art, reactive layout, friction mini-games (fridge → microwave → cutting → cooking → assembly → eating), persistent microwave “punishment”, and branching taste endings.

---

## Milestones

| Milestone | Goal | Status |
|-----------|------|--------|
| **M1 — Core loop** | Pygame scaffold, states (menu → fridge … → win/lose), HUD meters | ✅ |
| **M2 — Mini-games** | Microwave timer, sausage cutting path, pan heat bar, sandwich assembly slots | ✅ |
| **M3 — Fridge & outcomes** | Hidden containers, keep/discard, mystery items, GOOD / CONFUSED / LOSE endings | ✅ |
| **M4 — Polish & UX** | Responsive layout (`layout`, `wrap_fit`), sound (`SFX`), menu kitchen scene, HOW TO PLAY | ✅ |
| **M5 — Assembly & taste** | 7-slot guide + 2 wildcard fills; taste stack from fridge picks; bite-by-bite finale | ✅ |
| **M6 — Docs & release** | `README`, `requirements`, changelog-style refinements log, repo on GitHub | 🔄 |

---

## AI tools (how they were used)

| Tool | Use |
|------|-----|
| **Cursor (Composer / Agent)** | Iteration on `main.py`: state machine extensions, duplicate-file cleanup (single canonical game), HUD/layout helpers, procedural drawing, HOW/MENU copy, assembly & taste behaviour |
| **Cursor inline chat** | Smaller tweaks: overlap fixes, ellipsis copy, user-facing wording |

*No standalone code generators outside Cursor for this snapshot; gameplay lives in `main.py`.*

---

## Task list

### Completed (reference)

- [x] Single entrypoint (`main.py`), one `Game` class, trimmed duplicate pasted copies
- [x] Layout: hud / top / main / actions / feedback; `wrap_fit`, `get_scaled_rect`
- [x] Fridge grid + side panel + `draw_fridge_cartoon`; microwave + cutting + cooking + assembly
- [x] Assembly: blueprint guide panel; 5 fixed steps + 2 “Your pick” wildcards
- [x] Taste: stack from `selected_ingredients` + bites/crumbs + character moods
- [x] Start screen: dark kitchen + lit fridge; expanded HOW TO PLAY

### Backlog / nice-to-follow

- [ ] Save high scores or run statistics (optional)
- [ ] Optional config file (`config.ini`) for volume / fullscreen
- [ ] Split very large `main.py` into modules (`states/`, `ui/`, `assets/`) if the project grows
- [ ] Add `LICENSE` (e.g. MIT) once authors agree
- [ ] CI smoke test: `python -m py_compile main.py`

---

## Technical constraints

- **Python** 3.10+ recommended (project tested mindset: 3.13 + pygame-compatible wheels).
- **Renderer** pygame (or pygame-ce drop-in).

---

## Last updated

2026-05-10 (Europe/Berlin timezone per session context.)
