# Refinements & changes — running log

Maintained alongside Cursor-assisted development to record **scope shifts** and **design decisions**. Newest entries at the bottom.

---

## 2026-05-10 — Consolidation & stability

- **Problem:** Multiple full copies of the game appended in `main.py` caused wrong `Game` class / missing methods (`get_scaled_rect`, incomplete `draw` branches) → crashes after sausage cutting (`COOKING` / `ASSEMBLY` missing initially).
- **Decision:** Canonical **single** implementation; trim duplicate trailing blocks; retain one `Game().loop()` entrypoint.

---

## HUD & readability

- **Decision:** Responsive `layout()`, `wrap_fit()`, separated HUD task vs hint, stronger panel alpha and contrast to reduce overlapping text on small windows.
- **Shift:** Top band copy shortened; feedback region height increased where needed.

---

## Fridge & microwave behaviour

- **Decision:** Keep/discard flow; neutral labels before reveal; **`selected_ingredients`** feed final taste stacking order via `build_taste_stack` / `TASTE_STACK_ORDER`.
- **Decision:** Microwave early/late stop → **`microwave_flashing_active`** + beep loop persists into cutting / later phases (perfect 2:00 clears punishment).

---

## Art direction

- **Decision:** Cartoon procedural drawing (foods, microwave, fridge, menu dark-kitchen vignette).
- **Shift:** Start screen became **little fridge under cone light** in a dark kitchen; HOW TO PLAY expanded to explain **all** phases.

---

## Assembly sandwich

- **Decision:** **Seven vertical slots**: fixed base ladder (Bread → Cheese → Sausage → Sauce → Top bread shape) **with two middle wildcards (“Your pick”)** for non-base ingredients (`wildcard_ingredient_ok`, excludes `ASM_FIXED_FILL`).
- **Decision:** Left **guide panel** (`ASSEMBLY_GUIDE_TEXT`) + tray fill priority from fridge-kept fillers then Tomato/Lettuce defaults.

---

## Final taste scene

- **Decision:** Bite mechanic: crumbs + plate-coloured bite masking; stacked layers shrink by bite progress until **plate empty (“All gone!”)**; character mood preview before outcome transition (**GOOD / CONFUSED / LOSE** messaging).

---

## Documentation & tooling

- **Decision:** Ship `readme.md`, `plan.md`, `requirements.txt`, this log; initialise git and push when remote available.
- **Done:** Local `git` repo with `.gitignore`; public remote **https://github.com/TiyahSingh/3AM-Snack** (`main` pushed via GitHub CLI).
