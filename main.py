import math
import random
import sys
from array import array
from dataclasses import dataclass

import pygame

BASE_W, BASE_H = 1280, 720
FPS = 60
SR = 44100

SAFE_ITEMS = ["Bread", "Cheese", "Sausage", "Lettuce", "Tomato", "Sauce"]
MYSTERY_ITEMS = ["Mystery leftovers", "Unknown jelly", "Old meat", "Sour milk", "Fuzzy surprise", "Wiggly thing"]

# Bottom → top layering for the final snack portrait (built only from player's fridge picks).
TASTE_STACK_ORDER = (
    "Bread",
    "Lettuce",
    "Tomato",
    "Cheese",
    "Sauce",
    "Sour milk",
    "Sausage",
    "Old meat",
    "Mystery leftovers",
    "Unknown jelly",
    "Fuzzy surprise",
    "Wiggly thing",
    "Top bread",
)

# Assembly: five fixed bun stack steps + two wildcard fill slots (no bread/cheese/sausage/sauce/top in wilds).
ASM_FIXED_FILL = frozenset({"Bread", "Cheese", "Sausage", "Sauce", "Top bread"})

ASSEMBLY_GUIDE_TEXT = """HOW TO STACK (bottom up)

1 — Bottom bread
2 — Cheese
3 — Sausage
4 — YOUR PICK
5 — YOUR PICK
6 — Sauce
7 — Top bread

“Your pick” accepts any drag tile that is NOT one of the locked base five (so toss in tomato, lettuce, or a weird fridge trophy)."""


HOW_PLAY_TEXT = """Welcome to your late-night snack quest.

FRIDGE • Tap a container, read the label, choose Keep or Discard. Each kept ingredient is saved for later. Once at least three are kept you can tap Next (they decide how your finale snack stacks).

MICROWAVE • Heat the pouch to exactly 2:00 real-time. Tap Start and Stop precisely on 2:00. Wrong timing keeps the microwave “disturbance” flashing and beeping in later steps.

CUTTING • Move the drifting cursor like a cartoon knife along the glowing line. Finish the path, tap Next.

COOKING • Heat climbs automatically toward 120%. Remove while the needle sits in the green band. Leaving it too hot burns the snack quality.

ASSEMBLY • Build the sandwich bottom→top following the glowing guide on the plate. Five steps are locked to the classic stack; TWO slots labeled “Your pick” accept Tomato, Lettuce, or other fridge-kept fillings (anything that is not Bread/Cheese/Sausage/Sauce/Top bun). Wrong fixed slots ding quality—wildcards forgive creativity.

FINAL FEAST • The plate renders an ingredient stack built from EVERYTHING you chose to Keep in the fridge (sorted neatly). Tap repeatedly to chew through the munch counter, then watch the ending reaction!"""

class State:
    MENU = "MENU"
    HOW = "HOW"
    FRIDGE = "FRIDGE"
    MICROWAVE = "MICROWAVE"
    CUTTING = "CUTTING"
    COOKING = "COOKING"
    ASSEMBLY = "ASSEMBLY"
    TASTE = "TASTE"
    WIN = "WIN"
    LOSE = "LOSE"


@dataclass
class Container:
    label: str
    hidden_item: str
    rect: pygame.Rect


class SFX:
    def __init__(self):
        self.ok = pygame.mixer.get_init() is not None
        self.sounds = {}
        if self.ok:
            self._build()

    def _tone(self, f, d, v=0.25, sq=False):
        n = int(SR * d)
        b = array("h")
        for i in range(n):
            t = i / SR
            w = 1 if sq and math.sin(2 * math.pi * f * t) >= 0 else (-1 if sq else math.sin(2 * math.pi * f * t))
            env = 1 - (i / max(1, n - 1)) * 0.4
            b.append(int(w * 32767 * v * env))
        return pygame.mixer.Sound(buffer=b.tobytes())

    def _noise(self, d, v=0.2):
        n = int(SR * d)
        b = array("h")
        for i in range(n):
            env = 1 - i / max(1, n - 1)
            b.append(int(random.uniform(-1, 1) * 32767 * v * env))
        return pygame.mixer.Sound(buffer=b.tobytes())

    def _build(self):
        self.sounds["btn"] = self._tone(760, 0.06, 0.2)
        self.sounds["ding"] = self._tone(920, 0.22, 0.3)
        self.sounds["beep"] = self._tone(1120, 0.15, 0.32, sq=True)
        self.sounds["eat"] = self._noise(0.06, 0.17)
        self.sounds["cut"] = self._noise(0.05, 0.17)

    def play(self, name):
        if self.ok and name in self.sounds:
            self.sounds[name].play()


class Button:
    def __init__(self, g, text, base=(176, 202, 243), hover=(196, 218, 252)):
        self.g = g
        self.text = text
        self.base = base
        self.hover = hover
        self.rect = pygame.Rect(0, 0, 1, 1)

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def hit(self, e):
        return e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos)

    def draw(self, surf):
        col = self.hover if self.rect.collidepoint(pygame.mouse.get_pos()) else self.base
        pygame.draw.rect(surf, col, self.rect, border_radius=max(8, int(self.g.scl * 14)))
        pygame.draw.rect(surf, (245, 245, 255), self.rect, 2, border_radius=max(8, int(self.g.scl * 14)))
        label_size = max(14, min(24, int(self.rect.h * 0.34)))
        t = self.g.font(label_size, True).render(self.text, True, (28, 30, 45))
        surf.blit(t, t.get_rect(center=self.rect.center))


class Meter:
    def __init__(self, c, v):
        self.c = c
        self.v = v

    def add(self, x):
        self.v = max(0, min(100, self.v + x))

    def draw(self, surf, r):
        pygame.draw.rect(surf, (28, 33, 46), r, border_radius=8)
        w = int((self.v / 100) * (r.w - 4))
        pygame.draw.rect(surf, self.c, (r.x + 2, r.y + 2, w, r.h - 4), border_radius=7)
        pygame.draw.rect(surf, (225, 228, 245), r, 2, border_radius=8)


class Game:
    def __init__(self):
        pygame.mixer.pre_init(SR, -16, 1, 512)
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("3AM Snack")
        self.clock = pygame.time.Clock()
        self.font_cache = {}
        self.sfx = SFX()

        self.state = State.MENU
        self.running = True
        self.scl = 1.0
        self.pad = 16

        self.nausea = Meter((128, 237, 142), 0)
        self.headache = Meter((251, 153, 178), 0)
        self.quality = Meter((241, 221, 117), 100)
        self.selected_ingredients = []

        self.flash_t = 0
        self.shake_t = 0
        self.control_penalty = 0
        self.cursor_v = pygame.Vector2(BASE_W // 2, BASE_H // 2)

        self.microwave_flashing_active = False
        self.microwave_flash_strength = 0
        self.microwave_beeping = False
        self.microwave_beep_cd = 0.0
        self.cutting_flash_cd = 2.6

        self.cook_heat = 0.0
        self.cook_a = 50.0
        self.cook_b = 70.0
        self.cook_done = False
        self.cook_msg = ""

        self.asm_slot_specs = []
        self.asm_items = []
        self.asm_drag = None
        self.asm_done = False
        self.asm_msg = ""
        self.asm_slots = []

        self.taste_bites = 0
        self.taste_need = 8
        self.taste_phase = "EAT"
        self.taste_msg = ""
        self.taste_outcome = ""
        self.taste_rect = pygame.Rect(0, 0, 1, 1)
        self.taste_timer = 0
        self.taste_bite_marks = []
        self.taste_crumbs = []
        self.taste_react_t = 0.0
        self.taste_stack = []

        self.end_title = ""
        self.end_msg = ""
        self.end_play = "Play Again"

        self.menu_btns = [Button(self, "Start Game"), Button(self, "How to Play", (177, 214, 191), (194, 229, 206)), Button(self, "Exit", (229, 172, 187), (244, 189, 202))]
        self.back_btn = Button(self, "Back", (177, 214, 191), (194, 229, 206))
        self.end_btns = [Button(self, "Play Again", (179, 220, 190), (194, 237, 204)), Button(self, "Main Menu"), Button(self, "Exit", (230, 172, 188), (244, 188, 202))]

        self.reset_progress()

    def font(self, size, bold=False):
        s = max(12, int(size * self.scl))
        k = (s, bold)
        if k not in self.font_cache:
            self.font_cache[k] = pygame.font.SysFont("consolas", s, bold=bold)
        return self.font_cache[k]

    def layout(self):
        sw, sh = self.screen.get_size()
        self.scl = min(sw / BASE_W, sh / BASE_H)
        self.pad = max(8, int(16 * self.scl))
        hud_h = max(92, min(136, int(108 * self.scl)))
        top_h = max(60, min(88, int(74 * self.scl)))
        actions_h = max(86, int(112 * self.scl))
        feedback_h = max(86, min(132, int(112 * self.scl)))
        hud = pygame.Rect(0, 0, sw, hud_h)
        top = pygame.Rect(self.pad, hud.bottom + self.pad, sw - self.pad * 2, top_h)
        actions = pygame.Rect(self.pad, sh - actions_h - self.pad, sw - self.pad * 2, actions_h)
        feedback = pygame.Rect(self.pad, actions.y - feedback_h - self.pad, sw - self.pad * 2, feedback_h)
        main = pygame.Rect(self.pad, top.bottom + self.pad, sw - self.pad * 2, feedback.y - (top.bottom + self.pad))
        return {"hud": hud, "top": top, "main": main, "actions": actions, "feedback": feedback, "pad": self.pad}

    def get_scaled_rect(self, x, y, w, h):
        sw, sh = self.screen.get_size()
        return pygame.Rect(int(x * sw / BASE_W), int(y * sh / BASE_H), int(w * sw / BASE_W), int(h * sh / BASE_H))

    def panel(self, surf, r, color=(26, 30, 48, 210)):
        p = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        p.fill(color)
        surf.blit(p, r.topleft)
        pygame.draw.rect(surf, (230, 234, 250), r, max(2, int(3 * self.scl)), border_radius=max(8, int(self.scl * 12)))

    def wrap(self, surf, text, r, fs=22, color=(236, 240, 255)):
        self.panel(surf, r, (16, 20, 32, 110))
        f = self.font(fs)
        words = text.replace("\n", " \n ").split(" ")
        lines, line = [], ""
        for w in words:
            if w == "\n":
                lines.append(line)
                line = ""
                continue
            c = f"{line} {w}".strip()
            if f.size(c)[0] > r.w - self.pad and line:
                lines.append(line)
                line = w
            else:
                line = c
        if line:
            lines.append(line)
        y = r.y + self.pad // 2
        for ln in lines:
            if y + f.get_height() > r.bottom - self.pad // 2:
                break
            surf.blit(f.render(ln, True, color), (r.x + self.pad // 2, y))
            y += f.get_height() + 2

    def wrap_fit(self, surf, text, r, fs=22, fs_min=10, color=(245, 248, 255), line_gap=None, panel_alpha=(18, 22, 42, 200)):
        lg = max(1, line_gap if line_gap is not None else max(1, int(3 * self.scl)))
        inner_h = max(1, r.h - max(14, self.pad))
        gx = max(12, min(22, int(14 * self.scl)))
        chosen_font = None
        lines_final = []

        words_in = text.replace("\n", " \n ").split(" ")
        for sz in range(int(fs), fs_min - 1, -1):
            f_try = self.font(sz)
            words = words_in
            lines, line = [], ""
            for w in words:
                if w == "\n":
                    lines.append(line)
                    line = ""
                    continue
                c_test = f"{line} {w}".strip()
                if f_try.size(c_test)[0] > r.w - gx * 2 and line:
                    lines.append(line)
                    line = w
                else:
                    line = c_test
            if line:
                lines.append(line)

            lh = len(lines) * (f_try.get_height() + lg) - lg if lines else f_try.get_height()
            if lh <= inner_h or sz <= fs_min:
                chosen_font = f_try
                lines_final = lines
                if lh <= inner_h:
                    break
        if chosen_font is None:
            chosen_font = self.font(fs_min)
            lines_final = [text[:140] + "…"]

        self.panel(surf, r, panel_alpha)
        y = r.y + gx // 2
        for ln in lines_final:
            if y + chosen_font.get_height() > r.bottom - gx // 2:
                break
            surf.blit(chosen_font.render(ln, True, color), (r.x + gx, y))
            y += chosen_font.get_height() + lg

    def short_panel_label(self, name, maxlen=11):
        if len(name) <= maxlen:
            return name
        return name[: maxlen - 1] + "…"

    def filler_pair_for_wild_slots(self):
        fill = []
        for x in self.selected_ingredients:
            if x not in ASM_FIXED_FILL and x not in fill:
                fill.append(x)
        for cand in ("Tomato", "Lettuce", "Tomato"):
            if len(fill) >= 2:
                break
            if cand not in fill:
                fill.append(cand)
        return fill[0], fill[1]

    def wildcard_ingredient_ok(self, n):
        if n in ASM_FIXED_FILL:
            return False
        return n in SAFE_ITEMS or n in MYSTERY_ITEMS

    def assembly_slot_label(self, i):
        spec = self.asm_slot_specs[i]
        if spec.get("wild"):
            return "Your pick"
        return self.short_panel_label(spec["need"], 11)

    def build_taste_stack(self, picks):
        if not picks:
            return ["Bread"]
        ranks = {n: i for i, n in enumerate(TASTE_STACK_ORDER)}
        return sorted(picks, key=lambda ing: ranks.get(ing, 999))

    def draw_menu_kitchen(self, surf):
        sw, sh = surf.get_size()
        t = pygame.time.get_ticks() * 0.001
        for y in range(sh):
            v = y / max(1, sh - 1)
            c = (int(8 + v * 12), int(10 + v * 10), int(18 + v * 22))
            pygame.draw.line(surf, c, (0, y), (sw, y))
        floor_y = int(sh * 0.78)
        pygame.draw.rect(surf, (16, 12, 24), (0, floor_y, sw, sh - floor_y))
        pygame.draw.rect(surf, (28, 20, 40), (int(sw * 0.06), floor_y - int(56 * self.scl), int(sw * 0.88), int(72 * self.scl)), border_radius=16)
        con = pygame.Rect(int(sw * 0.1), floor_y + int(6 * self.scl), sw - int(0.2 * sw), int(sh * 0.14))
        pygame.draw.rect(surf, (40, 30, 50), con, border_radius=12)

        glow = pygame.Surface((sw, sh), pygame.SRCALPHA)
        cx, top_y = sw // 2, int(sh * 0.02)
        cone_w = int(sw * 0.55)
        alpha = int(120 + math.sin(t * 2.4) * 35)
        pygame.draw.polygon(
            glow,
            (255, 245, 210, alpha),
            [
                (cx - cone_w // 2, top_y),
                (cx + cone_w // 2, top_y),
                (cx + int(90 * self.scl), int(sh * 0.78)),
                (cx - int(90 * self.scl), int(sh * 0.78)),
            ],
        )
        surf.blit(glow, (0, 0))

        fr_w = int(min(sw * 0.32, 360 * self.scl))
        fr_h = int(min(sh * 0.46, 420 * self.scl))
        fr = pygame.Rect(sw // 2 - fr_w // 2, int(sh * 0.26), fr_w, fr_h)
        pygame.draw.rect(surf, (44, 48, 68), fr, border_radius=22)
        pygame.draw.rect(surf, (188, 198, 232), fr, 3, border_radius=22)
        split = fr.y + int(fr.h * 0.48)
        pygame.draw.line(surf, (120, 132, 168), (fr.x + 18, split), (fr.right - 18, split), 2)
        glass = pygame.Rect(fr.x + int(18 * self.scl), fr.y + int(18 * self.scl), fr.w - int(36 * self.scl), int(fr.h * 0.38))
        inner = pygame.Surface((glass.w, glass.h), pygame.SRCALPHA)
        flick = int(85 + math.sin(t * 4.0) * 35)
        inner.fill((255, 252, 220, flick))
        surf.blit(inner, glass.topleft)
        pygame.draw.rect(surf, (230, 236, 255), glass, 2, border_radius=12)
        lower = pygame.Rect(fr.x + int(18 * self.scl), split + int(10 * self.scl), fr.w - int(36 * self.scl), fr.bottom - split - int(28 * self.scl))
        pygame.draw.rect(surf, (88, 96, 124), lower, border_radius=12)
        pygame.draw.rect(surf, (210, 220, 245), lower, 2, border_radius=12)
        for hx, hy in ((fr.right - int(22 * self.scl), fr.y + int(36 * self.scl)), (fr.right - int(22 * self.scl), split + int(30 * self.scl))):
            pygame.draw.circle(surf, (244, 246, 255), (hx, hy), int(6 * self.scl))
        feet = pygame.Rect(fr.centerx - int(40 * self.scl), fr.bottom - int(8 * self.scl), int(80 * self.scl), int(16 * self.scl))
        pygame.draw.ellipse(surf, (60, 66, 86), feet)

        fz = pygame.Surface((int(32 * self.scl), int(32 * self.scl)), pygame.SRCALPHA)
        fa = int(160 + math.sin(t * 5.2) * 70)
        pygame.draw.circle(
            fz,
            (255, 245, 200, fa),
            (int(16 * self.scl), int(16 * self.scl)),
            int(9 * self.scl),
        )
        fx = int(fr.centerx + math.sin(t) * 12 * self.scl - 16 * self.scl)
        fy = int(fr.y + fr.h * 0.3 - 16 * self.scl)
        surf.blit(fz, (fx, fy))

    def draw_bg(self, surf, glow=True):
        sw, sh = self.screen.get_size()
        t = pygame.time.get_ticks() * 0.001
        for y in range(sh):
            grad = y / max(1, sh - 1)
            c = (int(16 * (1 - grad) + 38 * grad), int(18 * (1 - grad) + 30 * grad), int(42 * (1 - grad) + 62 * grad))
            pygame.draw.line(surf, c, (0, y), (sw, y))
        floor_y = int(sh * 0.72)
        pygame.draw.rect(surf, (40, 30, 60), (0, floor_y, sw, int(sh * 0.28)))
        for x in range(0, sw, max(28, int(42 * self.scl))):
            pygame.draw.line(surf, (56, 45, 78), (x, floor_y), (x + int(20 * self.scl), sh), 1)
        tile_h = max(20, int(26 * self.scl))
        for yy in range(int(sh * 0.18), floor_y, tile_h):
            pygame.draw.line(surf, (36, 32, 58), (0, yy), (sw, yy), 1)
        for xx in range(0, sw, max(36, int(48 * self.scl))):
            pygame.draw.line(surf, (32, 28, 52), (xx, int(sh * 0.18)), (xx, floor_y), 1)
        steam_x = int(sw * 0.2 + math.sin(t * 1.3) * 18 * self.scl)
        steam_y = int(sh * 0.44 + math.cos(t * 2.4) * 10 * self.scl)
        steam = pygame.Surface((int(120 * self.scl), int(90 * self.scl)), pygame.SRCALPHA)
        pygame.draw.ellipse(steam, (210, 220, 255, 85), (0, 0, steam.get_width(), steam.get_height()))
        surf.blit(steam, (steam_x, steam_y))
        fridge = pygame.Rect(int(sw * 0.82), int(sh * 0.18), int(sw * 0.15), int(sh * 0.58))
        pygame.draw.rect(surf, (192, 206, 243), fridge, border_radius=18)
        pygame.draw.rect(surf, (245, 245, 255), fridge, 2, border_radius=18)
        handle = pygame.Rect(fridge.right - int(20 * self.scl), fridge.y + int(50 * self.scl), int(8 * self.scl), int(110 * self.scl))
        pygame.draw.rect(surf, (228, 232, 248), handle, border_radius=8)
        if glow:
            g = pygame.Surface((int(sw * 0.32), int(sh * 0.72)), pygame.SRCALPHA)
            pygame.draw.ellipse(g, (170, 226, 255, 130), (0, 0, g.get_width(), g.get_height()))
            surf.blit(g, (int(sw * 0.7), int(sh * 0.12)))

    def draw_fridge_cartoon(self, surf, r):
        body = r.inflate(-self.pad, -self.pad)
        pygame.draw.rect(surf, (178, 204, 236), body, border_radius=max(14, int(18 * self.scl)))
        pygame.draw.rect(surf, (236, 242, 255), body, 2, border_radius=max(14, int(18 * self.scl)))
        mid = body.y + int(body.h * 0.45)
        pygame.draw.line(surf, (154, 182, 218), (body.x + self.pad, mid), (body.right - self.pad, mid), max(2, int(3 * self.scl)))
        for i in range(3):
            yy = body.y + int(body.h * (0.2 + i * 0.22))
            pygame.draw.line(surf, (146, 172, 206), (body.x + int(20 * self.scl), yy), (body.right - int(20 * self.scl), yy), 2)
        h1 = pygame.Rect(body.right - int(20 * self.scl), body.y + int(44 * self.scl), int(8 * self.scl), int(96 * self.scl))
        h2 = pygame.Rect(body.right - int(20 * self.scl), body.y + int(body.h * 0.57), int(8 * self.scl), int(96 * self.scl))
        pygame.draw.rect(surf, (233, 236, 247), h1, border_radius=8)
        pygame.draw.rect(surf, (233, 236, 247), h2, border_radius=8)

    def draw_person(self, surf, area, mood, bite_ratio):
        t = pygame.time.get_ticks() * 0.001
        bob = math.sin(t * 4.2) * 4 * self.scl
        cx, cy = area.centerx, area.centery + int(bob)
        skin = (247, 206, 176)
        body = pygame.Rect(cx - int(82 * self.scl), cy + int(20 * self.scl), int(164 * self.scl), int(126 * self.scl))
        pygame.draw.rect(surf, (154, 176, 232), body, border_radius=20)
        head_r = int(48 * self.scl)
        pygame.draw.circle(surf, skin, (cx, cy - int(30 * self.scl)), head_r)
        eye_y = cy - int(40 * self.scl)
        eye_dx = int(16 * self.scl)
        pygame.draw.circle(surf, (42, 42, 58), (cx - eye_dx, eye_y), max(2, int(4 * self.scl)))
        pygame.draw.circle(surf, (42, 42, 58), (cx + eye_dx, eye_y), max(2, int(4 * self.scl)))
        if mood == "GOOD":
            pygame.draw.arc(surf, (62, 36, 50), (cx - int(22 * self.scl), cy - int(20 * self.scl), int(44 * self.scl), int(24 * self.scl)), 0.2, 2.9, 3)
            arm = [(body.x + int(18 * self.scl), body.y + int(42 * self.scl)), (body.x + int(56 * self.scl), body.y + int(26 * self.scl)), (body.x + int(90 * self.scl), body.y + int(46 * self.scl))]
            pygame.draw.lines(surf, skin, False, arm, max(4, int(6 * self.scl)))
        elif mood == "CONFUSED":
            pygame.draw.arc(surf, (62, 36, 50), (cx - int(16 * self.scl), cy - int(16 * self.scl), int(32 * self.scl), int(14 * self.scl)), 3.3, 6.0, 2)
            tilt = math.sin(t * 3.0) * 10
            qcol = (236, 229, 132)
            surf.blit(self.font(26, True).render("?", True, qcol), (cx + int(54 * self.scl), cy - int(95 * self.scl) + tilt))
            surf.blit(self.font(22, True).render("?", True, qcol), (cx + int(76 * self.scl), cy - int(68 * self.scl) - tilt * 0.4))
        else:
            pygame.draw.arc(surf, (70, 40, 50), (cx - int(18 * self.scl), cy - int(12 * self.scl), int(36 * self.scl), int(16 * self.scl)), 3.3, 6.1, 3)
            pygame.draw.circle(surf, (166, 214, 152), (cx, cy - int(30 * self.scl)), int(48 * self.scl), max(2, int(6 * self.scl)))
            pygame.draw.line(surf, skin, (body.centerx + int(28 * self.scl), body.y + int(18 * self.scl)), (body.centerx + int(2 * self.scl), body.y - int(26 * self.scl)), max(4, int(6 * self.scl)))
        if bite_ratio > 0.95:
            sparkle = (255, 246, 176)
            for i in range(3):
                px = cx - int(66 * self.scl) + i * int(64 * self.scl)
                py = body.bottom + int(10 * self.scl + math.sin(t * 4 + i) * 4 * self.scl)
                pygame.draw.circle(surf, sparkle, (px, py), max(2, int(5 * self.scl)))

    def draw_food(self, surf, name, c, s):
        x, y = c
        s = max(0.45, s)
        if name in ("Bread", "Top bread"):
            pygame.draw.ellipse(surf, (249, 224, 174), (x - 52 * s, y - 30 * s, 104 * s, 60 * s))
            pygame.draw.ellipse(surf, (198, 136, 89), (x - 52 * s, y - 30 * s, 104 * s, 60 * s), max(2, int(3 * s)))
        elif name == "Sausage":
            pygame.draw.ellipse(surf, (199, 103, 112), (x - 62 * s, y - 20 * s, 124 * s, 40 * s))
            pygame.draw.ellipse(surf, (136, 71, 84), (x - 62 * s, y - 20 * s, 124 * s, 40 * s), max(2, int(3 * s)))
        elif name == "Old meat":
            pygame.draw.ellipse(surf, (120, 98, 88), (x - 64 * s, y - 22 * s, 128 * s, 44 * s))
            pygame.draw.ellipse(surf, (82, 64, 58), (x - 64 * s, y - 22 * s, 128 * s, 44 * s), max(2, int(3 * s)))
            pygame.draw.ellipse(surf, (164, 140, 120), (x - 20 * s, y - 6 * s, 40 * s, 14 * s))
        elif name == "Cheese":
            pts = [(x - 58 * s, y + 24 * s), (x + 54 * s, y + 24 * s), (x + 18 * s, y - 26 * s), (x - 72 * s, y - 24 * s)]
            pygame.draw.polygon(surf, (251, 231, 118), pts)
            pygame.draw.polygon(surf, (206, 165, 72), pts, max(2, int(3 * s)))
        elif name == "Tomato":
            pygame.draw.circle(surf, (244, 118, 126), (int(x), int(y)), int(30 * s))
            pygame.draw.circle(surf, (196, 71, 90), (int(x), int(y)), int(30 * s), max(2, int(3 * s)))
        elif name == "Lettuce":
            pts = []
            for i in range(20):
                ang = i / 19 * math.pi * 2
                rr = (35 + math.sin(i * 1.1) * 9) * s
                pts.append((x + math.cos(ang) * rr, y + math.sin(ang) * rr))
            pygame.draw.polygon(surf, (127, 219, 138), pts)
            pygame.draw.polygon(surf, (84, 164, 96), pts, max(2, int(3 * s)))
        elif name == "Sauce":
            body = pygame.Rect(int(x - 24 * s), int(y - 46 * s), int(48 * s), int(90 * s))
            pygame.draw.rect(surf, (236, 187, 146), body, border_radius=max(6, int(14 * s)))
            pygame.draw.rect(surf, (184, 132, 94), body, max(2, int(3 * s)), border_radius=max(6, int(14 * s)))
        elif name == "Sour milk":
            body = pygame.Rect(int(x - 22 * s), int(y - 44 * s), int(44 * s), int(86 * s))
            pygame.draw.rect(surf, (220, 240, 232), body, border_radius=max(6, int(13 * s)))
            pygame.draw.rect(surf, (140, 180, 164), body, max(2, int(3 * s)), border_radius=max(6, int(13 * s)))
            pygame.draw.ellipse(surf, (176, 210, 198), (x - 10 * s, y - 28 * s, 20 * s, 14 * s))
        elif name == "Mystery":
            box = pygame.Rect(int(x - 38 * s), int(y - 28 * s), int(76 * s), int(56 * s))
            pygame.draw.rect(surf, (198, 186, 224), box, border_radius=max(8, int(12 * s)))
            pygame.draw.rect(surf, (120, 98, 150), box, max(2, int(3 * s)), border_radius=max(8, int(12 * s)))
            q = self.font(max(14, int(28 * s)), True).render("?", True, (255, 250, 200))
            surf.blit(q, q.get_rect(center=(int(x), int(y - 4 * s))))
        elif name == "Mystery leftovers":
            box = pygame.Rect(int(x - 44 * s), int(y - 26 * s), int(88 * s), int(52 * s))
            pygame.draw.rect(surf, (210, 190, 160), box, border_radius=10)
            pygame.draw.rect(surf, (130, 100, 80), box, 2, border_radius=10)
            pygame.draw.line(surf, (160, 120, 100), (box.left + 8, box.centery), (box.right - 8, box.centery), max(2, int(3 * s)))
            pygame.draw.circle(surf, (90, 70, 60), (int(x - 18 * s), int(y + 8 * s)), int(5 * s))
        elif name == "Unknown jelly":
            w, h = 52 * s, 40 * s
            pygame.draw.ellipse(surf, (186, 120, 210), (x - w / 2, y - h / 2, w, h))
            pygame.draw.ellipse(surf, (120, 70, 150), (x - w / 2, y - h / 2, w, h), max(2, int(3 * s)))
            pygame.draw.circle(surf, (230, 200, 250), (int(x - 12 * s), int(y - 6 * s)), int(6 * s))
        elif name == "Fuzzy surprise":
            pts = []
            for i in range(16):
                ang = i / 15 * math.pi * 2
                rr = (32 + math.sin(i * 1.4) * 10) * s
                pts.append((x + math.cos(ang) * rr, y + math.sin(ang) * rr))
            pygame.draw.polygon(surf, (142, 196, 130), pts)
            pygame.draw.polygon(surf, (78, 120, 72), pts, max(2, int(3 * s)))
            for dx, dy in [(-10, -6), (8, 4), (4, -10)]:
                pygame.draw.circle(surf, (34, 60, 30), (int(x + dx * s), int(y + dy * s)), int(3 * s))
        elif name == "Wiggly thing":
            for seg in range(5):
                sx = x + (seg - 2) * 14 * s
                sy = y + math.sin(seg * 1.2) * 10 * s
                pygame.draw.circle(surf, (255, 160, 190), (int(sx), int(sy)), int(11 * s))
            pygame.draw.circle(surf, (40, 40, 50), (int(x + 24 * s), int(y - 4 * s)), int(4 * s))
            pygame.draw.circle(surf, (255, 255, 255), (int(x + 25 * s), int(y - 5 * s)), int(2 * s))
        else:
            pts = []
            for i in range(14):
                ang = i / 14 * math.pi * 2
                rr = (28 + math.sin(i * 1.2) * 8) * s
                pts.append((x + math.cos(ang) * rr, y + math.sin(ang) * rr))
            pygame.draw.polygon(surf, (190, 160, 212), pts)
            pygame.draw.polygon(surf, (116, 90, 140), pts, max(2, int(3 * s)))

    def draw_microwave(self, surf, r, timer_txt):
        pygame.draw.rect(surf, (70, 82, 108), r, border_radius=16)
        pygame.draw.rect(surf, (230, 235, 255), r, 2, border_radius=16)
        door = pygame.Rect(r.x + self.pad // 2, r.y + self.pad // 2, int(r.w * 0.66), r.h - self.pad)
        pygame.draw.rect(surf, (24, 32, 44), door, border_radius=10)
        panel = pygame.Rect(door.right + self.pad // 2, door.y, r.right - (door.right + self.pad), door.h)
        pygame.draw.rect(surf, (51, 58, 78), panel, border_radius=8)
        disp = pygame.Rect(panel.x + self.pad // 3, panel.y + self.pad // 3, panel.w - self.pad // 2, int(panel.h * 0.22))
        pygame.draw.rect(surf, (18, 28, 37), disp, border_radius=6)
        t = self.font(28, True).render(timer_txt, True, (147, 255, 182))
        surf.blit(t, t.get_rect(center=disp.center))

    def draw_packet(self, surf, r):
        pygame.draw.rect(surf, (197, 211, 244), r, border_radius=14)
        pygame.draw.rect(surf, (245, 245, 255), r, 2, border_radius=14)
        pygame.draw.rect(surf, (180, 194, 236), (r.x + self.pad, r.y + self.pad, r.w - self.pad * 2, int(36 * self.scl)), border_radius=8)
        surf.blit(self.font(22, True).render("Frozen Meal", True, (44, 50, 69)), (r.x + self.pad * 2, r.y + self.pad + int(4 * self.scl)))

    def draw_knife_cartoon(self, surf, p):
        x, y = p
        pygame.draw.polygon(
            surf,
            (230, 234, 246),
            [
                (x - 30 * self.scl, y - 9 * self.scl),
                (x + 34 * self.scl, y),
                (x - 30 * self.scl, y + 9 * self.scl),
            ],
        )
        pygame.draw.rect(
            surf,
            (174, 132, 112),
            (x - 43 * self.scl, y - 8 * self.scl, 14 * self.scl, 16 * self.scl),
            border_radius=5,
        )

    def draw_hud(self, surf, task, hint):
        l = self.layout()
        h = l["hud"]
        pygame.draw.rect(surf, (13, 18, 31), h)
        g = self.pad
        meter_top = max(6, g // 2)
        lf = self.font(12)
        mh = max(36, min(54, int(h.h * 0.38) - lf.get_height()))
        avail = h.w - g * 4 - int(h.w * 0.3)
        mw = max(100, avail // 3)
        if mw * 3 + g * 6 > h.w:
            mw = max(92, (h.w - g * 7) // 3)
        r1 = pygame.Rect(g, meter_top, mw, mh)
        r2 = pygame.Rect(r1.right + g, meter_top, mw, mh)
        r3 = pygame.Rect(r2.right + g, meter_top, mw, mh)
        self.nausea.draw(surf, r1)
        self.headache.draw(surf, r2)
        self.quality.draw(surf, r3)
        ly = min(r3.bottom + max(2, g // 5), h.bottom - lf.get_height() - 10)
        surf.blit(lf.render("Nausea", True, (222, 239, 225)), (r1.x, ly))
        surf.blit(lf.render("Headache", True, (243, 221, 227)), (r2.x, ly))
        surf.blit(lf.render("Quality", True, (242, 236, 197)), (r3.x, ly))
        text_top = ly + lf.get_height() + max(4, g // 3)
        text_left = r3.right + g
        text_w = max(120, h.right - text_left - g)
        text_bot = h.bottom - g // 2
        text_top = min(text_top, text_bot - 36)
        has_hint = bool(hint and str(hint).strip())
        if has_hint:
            task_h = max(26, int((text_bot - text_top) * 0.48))
            task_rect = pygame.Rect(text_left, text_top, text_w, task_h - 6)
            self.wrap_fit(surf, task, task_rect, fs=14, fs_min=10, color=(240, 244, 255))
            hr = pygame.Rect(text_left, text_top + task_h, text_w, max(26, text_bot - (text_top + task_h)))
            self.wrap_fit(surf, str(hint), hr, fs=13, fs_min=10, color=(214, 220, 246))
        else:
            task_rect = pygame.Rect(text_left, text_top, text_w, max(44, text_bot - text_top))
            self.wrap_fit(surf, task, task_rect, fs=15, fs_min=10)

    def reset_progress(self):
        labels = [f"Container {i+1}" for i in range(10)]
        pool = SAFE_ITEMS + MYSTERY_ITEMS
        random.shuffle(pool)
        self.fridge_items = [Container(labels[i], pool[i], pygame.Rect(0, 0, 1, 1)) for i in range(10)]
        self.fridge_selected = None
        self.fridge_msg = "Inspect a container, then choose Keep or Discard."
        self.fridge_reveal_item = None
        self.fridge_reveal_timer = 0.0

        self.mw_time = 0.0
        self.mw_run = False
        self.mw_done = False
        self.mw_msg = "Press Start and stop exactly at 2:00."

        self.cut_progress = 0
        self.cut_drag = False
        self.cut_msg = "Drag knife over the glowing guide."
        self.taste_bite_marks = []
        self.taste_crumbs = []
        self.taste_react_t = 0.0

        self.cook_heat = 0.0
        self.cook_done = False
        self.cook_msg = ""
        self.asm_items = []
        self.asm_drag = None
        self.asm_done = False
        self.asm_msg = ""
        self.asm_slots = []
        self.asm_slot_specs = []
        self.taste_stack = []

    def setup_cooking(self):
        self.cook_heat = 0.0
        self.cook_a = random.uniform(50, 62)
        self.cook_b = self.cook_a + random.uniform(16, 20)
        self.cook_done = False
        self.cook_msg = "Press Remove when the heat marker is in the green zone."

    def finish_cooking(self):
        if self.cook_done:
            return
        self.cook_done = True
        if self.cook_heat < self.cook_a:
            self.cook_msg = "Undercooked."
            self.quality.add(-10)
            self.nausea.add(8)
        elif self.cook_a <= self.cook_heat <= self.cook_b:
            self.cook_msg = "Cooked perfectly."
            self.quality.add(8)
        else:
            self.cook_msg = "Burnt."
            self.quality.add(-14)
            self.headache.add(12)

    def setup_assembly(self):
        self.asm_slot_specs = [
            {"need": "Bread", "wild": False},
            {"need": "Cheese", "wild": False},
            {"need": "Sausage", "wild": False},
            {"need": None, "wild": True},
            {"need": None, "wild": True},
            {"need": "Sauce", "wild": False},
            {"need": "Top bread", "wild": False},
        ]
        f1, f2 = self.filler_pair_for_wild_slots()
        tray = ["Bread", "Cheese", "Sausage", f1, f2, "Sauce", "Top bread"]
        random.shuffle(tray)
        self.asm_items = [{"n": n, "r": pygame.Rect(0, 0, 1, 1), "home": None, "placed": False} for n in tray]
        self.asm_drag = None
        self.asm_done = False
        self.asm_msg = "Match the glowing slots. Two middle slots = your choice ingredient."

    def asm_drop(self, it):
        n_slots = len(self.asm_slot_specs)
        idx = sum(1 for x in self.asm_items if x["placed"])
        if idx >= n_slots:
            it["r"] = it["home"].copy()
            return
        target = self.asm_slots[idx]
        spec = self.asm_slot_specs[idx]
        if not target.colliderect(it["r"].inflate(int(-22 * self.scl), int(-8 * self.scl))):
            self.quality.add(-3)
            self.nausea.add(1)
            it["r"] = it["home"].copy()
            self.asm_msg = "Line it up with the glowing slot."
            return
        ok = self.wildcard_ingredient_ok(it["n"]) if spec["wild"] else it["n"] == spec["need"]
        if ok:
            it["placed"] = True
            it["r"] = target.copy()
            self.quality.add(3)
            self.asm_msg = f"Nice! {it['n']} locked in."
            if sum(1 for x in self.asm_items if x["placed"]) == n_slots:
                self.asm_done = True
                self.asm_msg = "Snack assembled. Taste it!"
        else:
            self.quality.add(-6)
            self.nausea.add(3)
            it["r"] = it["home"].copy()
            if spec["wild"]:
                self.asm_msg = "Wildcard needs a non-base ingredient (tomato, lettuce, funky fridge stuff…)."
            else:
                self.asm_msg = f"This slot wants {spec['need']} — check the guide."

    def layout_assembly(self, l):
        m = l["main"]
        if not self.asm_slot_specs:
            self.asm_slots = []
            return
        guide_w = min(max(int(m.w * 0.28), int(236 * self.scl)), int(m.w * 0.4))
        gx0 = m.x + l["pad"]
        work_inner_w = max(252, m.w - guide_w - l["pad"] * 3)
        work = pygame.Rect(gx0 + guide_w, m.y + l["pad"], work_inner_w, m.h - l["pad"] * 2)
        self._asm_guide_area = pygame.Rect(gx0 + l["pad"] // 2, m.y + l["pad"], guide_w - l["pad"], m.h - l["pad"] * 2)
        pw = min(int(work.w * 0.42), int(380 * self.scl))
        self._asm_plate = pygame.Rect(work.centerx - pw // 2, work.y + int(work.h * 0.04), pw, int(work.h * 0.76))
        step = max(int(self._asm_plate.h * 0.085), int(52 * self.scl))
        y_top = self._asm_plate.y + int(self._asm_plate.h * 0.05)
        self.asm_slots = [
            pygame.Rect(
                self._asm_plate.centerx - int(self._asm_plate.w * 0.33),
                y_top + i * step,
                int(self._asm_plate.w * 0.66),
                step - max(7, int(9 * self.scl)),
            )
            for i in range(len(self.asm_slot_specs))
        ]

        nc = len(self.asm_items)
        rows = max(4, math.ceil(nc / 2))
        left_w = max(108, min(180, self._asm_plate.x - work.x - l["pad"] * 2))
        left = pygame.Rect(work.x + l["pad"], work.y + l["pad"], left_w, work.h - l["pad"] * 2)
        right = pygame.Rect(self._asm_plate.right + l["pad"], left.y, work.right - self._asm_plate.right - l["pad"] * 2, left.h)

        spots = []
        rh = max(58, left.h // rows)
        for r_idx in range(rows):
            yr = left.y + r_idx * rh
            spots.append(pygame.Rect(left.x + l["pad"] // 2, yr + l["pad"] // 2, left.w - l["pad"], rh - l["pad"]))
            xr = pygame.Rect(right.x + l["pad"] // 2, yr + l["pad"] // 2, right.w - l["pad"], rh - l["pad"])
            if len(spots) < nc:
                spots.append(xr)
        for i, it in enumerate(self.asm_items):
            if it["home"] is None and i < len(spots):
                it["r"] = spots[i].copy()
                it["home"] = spots[i].copy()

        a = l["actions"]
        self._asm_next = pygame.Rect(a.right - int(a.w * 0.32), a.y + l["pad"], int(a.w * 0.28), a.h - l["pad"] * 2)

    def start_taste(self):
        self.taste_bites = 0
        self.taste_phase = "EAT"
        self.taste_msg = ""
        self.taste_outcome = ""
        self.taste_bite_marks = []
        self.taste_crumbs = []
        self.taste_react_t = 0.0
        self.taste_stack = self.build_taste_stack(self.selected_ingredients)

    def full_reset(self):
        self.nausea.v = 0
        self.headache.v = 0
        self.quality.v = 100
        self.selected_ingredients = []
        self.flash_t = self.shake_t = self.control_penalty = 0
        self.microwave_flashing_active = False
        self.microwave_beeping = False
        self.microwave_flash_strength = 0
        self.microwave_beep_cd = 0.0
        self.cutting_flash_cd = 2.6
        self.reset_progress()
        self.state = State.FRIDGE

    def update_global(self, dt):
        self.flash_t = max(0, self.flash_t - dt)
        self.shake_t = max(0, self.shake_t - dt)
        self.control_penalty = max(0, self.control_penalty - dt)
        self.fridge_reveal_timer = max(0, self.fridge_reveal_timer - dt)
        mystery_count = sum(1 for x in self.selected_ingredients if x in MYSTERY_ITEMS)
        if self.state in [State.MICROWAVE, State.CUTTING, State.COOKING, State.ASSEMBLY, State.TASTE]:
            self.nausea.add(mystery_count * dt * 0.42)
        if self.microwave_beeping and self.state in [State.CUTTING, State.COOKING, State.ASSEMBLY, State.TASTE]:
            self.microwave_beep_cd -= dt
            if self.microwave_beep_cd <= 0:
                self.sfx.play("beep")
                self.microwave_beep_cd = 0.5
        if self.nausea.v >= 100 and self.state not in [State.MENU, State.HOW, State.WIN, State.LOSE]:
            self.state = State.LOSE
            self.end_title = "You Couldn't Keep It Down"
            self.end_msg = "Yuck... I can't keep this down."
            self.end_play = "Try Again"

    def cursor(self, extra_drift=0.0):
        mx, my = pygame.mouse.get_pos()
        t = pygame.time.get_ticks() * 0.004
        sway = 2 + self.headache.v * 0.08 + extra_drift * 6
        target = pygame.Vector2(mx + math.sin(t * 1.3) * sway, my + math.cos(t * 1.7) * sway)
        lag = 0.22 + min(0.5, self.headache.v / 180) + (0.16 if self.control_penalty > 0 else 0)
        self.cursor_v += (target - self.cursor_v) * lag
        return self.cursor_v.x, self.cursor_v.y

    def handle_events(self):
        l = self.layout()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
                return
            if e.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((max(920, e.w), max(620, e.h)), pygame.RESIZABLE)
            if self.state == State.MENU:
                self.menu_layout(self.menu_btns, int(self.screen.get_height() * 0.046))
                if self.menu_btns[0].hit(e):
                    self.full_reset()
                elif self.menu_btns[1].hit(e):
                    self.state = State.HOW
                elif self.menu_btns[2].hit(e):
                    self.running = False
            elif self.state == State.HOW:
                self.back_btn.set_rect((self.pad, self.screen.get_height() - int(70 * self.scl), int(180 * self.scl), int(54 * self.scl)))
                if self.back_btn.hit(e):
                    self.state = State.MENU
            elif self.state == State.FRIDGE:
                self.handle_fridge_event(e, l)
            elif self.state == State.MICROWAVE:
                self.handle_microwave_event(e, l)
            elif self.state == State.CUTTING:
                self.handle_cutting_event(e, l)
            elif self.state == State.COOKING:
                self.handle_cooking_event(e, l)
            elif self.state == State.ASSEMBLY:
                self.handle_assembly_event(e, l)
            elif self.state == State.TASTE:
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.taste_phase == "EAT" and self.taste_rect.collidepoint(e.pos):
                    self.taste_bites += 1
                    self.sfx.play("eat")
                    self.taste_bite_marks.append((e.pos[0], e.pos[1], random.randint(int(12 * self.scl), int(20 * self.scl))))
                    for _ in range(6):
                        self.taste_crumbs.append(
                            {
                                "x": float(e.pos[0]),
                                "y": float(e.pos[1]),
                                "vx": random.uniform(-85, 85) * self.scl,
                                "vy": random.uniform(-120, -45) * self.scl,
                                "t": random.uniform(0.4, 0.9),
                            }
                        )
                    if self.taste_bites >= self.taste_need:
                        self.taste_outcome, self.taste_msg = self.decide_outcome()
                        self.taste_phase = "REACTION"
                        self.taste_timer = 2.2
                        self.taste_react_t = 2.2
            elif self.state in [State.WIN, State.LOSE]:
                self.menu_layout(self.end_btns)
                self.end_btns[0].text = self.end_play
                if self.end_btns[0].hit(e):
                    self.full_reset()
                elif self.end_btns[1].hit(e):
                    self.state = State.MENU
                elif self.end_btns[2].hit(e):
                    self.running = False

    def handle_fridge_event(self, e, l):
        m = l["main"]
        fridge = pygame.Rect(m.x, m.y, int(m.w * 0.66), m.h)
        side = pygame.Rect(fridge.right + l["pad"], m.y, m.right - (fridge.right + l["pad"]), m.h)
        grid = fridge.inflate(-l["pad"] * 2, -l["pad"] * 2)
        cw = (grid.w - l["pad"] * 4) // 5
        ch = (grid.h - l["pad"]) // 2
        for i, c in enumerate(self.fridge_items):
            c.rect = pygame.Rect(grid.x + (i % 5) * (cw + l["pad"]), grid.y + (i // 5) * (ch + l["pad"]), cw, ch)
        a = l["actions"]
        bw = (a.w - l["pad"] * 4) // 3
        self._keep = pygame.Rect(a.x + l["pad"], a.y + l["pad"], bw, a.h - l["pad"] * 2)
        self._discard = pygame.Rect(self._keep.right + l["pad"], a.y + l["pad"], bw, a.h - l["pad"] * 2)
        self._next = pygame.Rect(self._discard.right + l["pad"], a.y + l["pad"], bw, a.h - l["pad"] * 2)
        self._fridge_area, self._side_area = fridge, side
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.fridge_selected and self._keep.collidepoint(e.pos):
                item = self.fridge_selected.hidden_item
                self.selected_ingredients.append(item)
                self.fridge_msg = f"You kept {self.fridge_selected.label}. It was: {item}"
                self.fridge_reveal_item = item
                self.fridge_reveal_timer = 2.0
                self.fridge_items.remove(self.fridge_selected)
                self.fridge_selected = None
                self.sfx.play("btn")
            elif self.fridge_selected and self._discard.collidepoint(e.pos):
                item = self.fridge_selected.hidden_item
                self.fridge_msg = f"You discarded {self.fridge_selected.label}. It was: {item}"
                self.fridge_reveal_item = item
                self.fridge_reveal_timer = 2.0
                self.fridge_items.remove(self.fridge_selected)
                self.fridge_selected = None
                self.sfx.play("btn")
            elif len(self.selected_ingredients) >= 3 and self._next.collidepoint(e.pos):
                self.state = State.MICROWAVE
                self.sfx.play("btn")
            elif not self.fridge_selected:
                for c in self.fridge_items:
                    if c.rect.collidepoint(e.pos):
                        self.fridge_selected = c
                        self.fridge_msg = f"Opened {c.label}. Choose Keep or Discard."
                        self.sfx.play("btn")
                        break

    def handle_microwave_event(self, e, l):
        m = l["main"]
        mw = pygame.Rect(m.x, m.y + l["pad"], int(m.w * 0.62), m.h - l["pad"] * 2)
        pkt = pygame.Rect(mw.right + l["pad"], mw.y, m.right - (mw.right + l["pad"]), mw.h)
        a = l["actions"]
        bw = (a.w - l["pad"] * 4) // 3
        self._mw_b0 = pygame.Rect(a.x + l["pad"], a.y + l["pad"], bw, a.h - l["pad"] * 2)
        self._mw_b1 = pygame.Rect(self._mw_b0.right + l["pad"], a.y + l["pad"], bw, a.h - l["pad"] * 2)
        self._mw_b2 = pygame.Rect(self._mw_b1.right + l["pad"], a.y + l["pad"], bw, a.h - l["pad"] * 2)
        self._mw_area, self._pkt_area = mw, pkt
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if not self.mw_done and self._mw_b0.collidepoint(e.pos):
                self.mw_run = True
            elif not self.mw_done and self._mw_b1.collidepoint(e.pos):
                self.mw_done = True
                self.mw_run = False
                sec = int(self.mw_time)
                if sec == 120:
                    self.microwave_flashing_active = False
                    self.microwave_flash_strength = 0
                    self.microwave_beeping = False
                    self.mw_msg = "Perfect timing."
                    self.sfx.play("ding")
                elif sec < 120:
                    self.microwave_flashing_active = True
                    self.microwave_flash_strength = 1
                    self.microwave_beeping = True
                    self.microwave_beep_cd = 0
                    self.mw_msg = "Stopped early. Food is cold."
                else:
                    self.microwave_flashing_active = True
                    self.microwave_flash_strength = 2
                    self.microwave_beeping = True
                    self.microwave_beep_cd = 0
                    self.mw_msg = "Stopped late. Disturbance is stronger."
            elif self.mw_done and self._mw_b2.collidepoint(e.pos):
                self.sfx.play("btn")
                self.state = State.CUTTING

    def handle_cutting_event(self, e, l):
        m = l["main"]
        self._board = pygame.Rect(m.centerx - int(m.w * 0.42), m.centery - int(m.h * 0.29), int(m.w * 0.84), int(m.h * 0.58))
        self._path = [(self._board.left + int(self._board.w * 0.08) + j * int(self._board.w / 40), self._board.centery + math.sin(j * 0.35) * int(self._board.h * 0.2)) for j in range(36)]
        a = l["actions"]
        self._cut_next = pygame.Rect(a.right - int(a.w * 0.28), a.y + l["pad"], int(a.w * 0.24), a.h - l["pad"] * 2)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.cut_drag = True
            if self.cut_progress >= len(self._path) and self._cut_next.collidepoint(e.pos):
                self.setup_cooking()
                self.state = State.COOKING
                self.sfx.play("btn")
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.cut_drag = False

    def handle_cooking_event(self, e, l):
        m = l["main"]
        self._cook_pan = pygame.Rect(m.centerx - int(m.w * 0.28), m.y + int(m.h * 0.08), int(m.w * 0.56), int(m.h * 0.46))
        self._cook_bar = pygame.Rect(m.centerx - int(m.w * 0.36), self._cook_pan.bottom + int(m.h * 0.06), int(m.w * 0.72), int(m.h * 0.14))
        a = l["actions"]
        bw = int(a.w * 0.26)
        self._cook_remove = pygame.Rect(a.centerx - bw - l["pad"] // 2, a.y + l["pad"], bw, a.h - l["pad"] * 2)
        self._cook_next = pygame.Rect(a.centerx + l["pad"] // 2, a.y + l["pad"], bw, a.h - l["pad"] * 2)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self._cook_remove.collidepoint(e.pos) and not self.cook_done:
                self.sfx.play("btn")
                self.finish_cooking()
            elif self._cook_next.collidepoint(e.pos) and self.cook_done:
                self.sfx.play("btn")
                self.setup_assembly()
                self.state = State.ASSEMBLY

    def handle_assembly_event(self, e, l):
        self.layout_assembly(l)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self._asm_next.collidepoint(e.pos) and self.asm_done:
                self.sfx.play("btn")
                self.start_taste()
                self.state = State.TASTE
                return
            if not self.asm_done:
                for it in reversed(self.asm_items):
                    if not it["placed"] and it["r"].collidepoint(e.pos):
                        self.asm_drag = it
                        break
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self.asm_drag:
                self.asm_drop(self.asm_drag)
            self.asm_drag = None

    def decide_outcome(self):
        mystery_count = sum(1 for x in self.selected_ingredients if x in MYSTERY_ITEMS)
        eq = self.quality.v - mystery_count * 9
        if self.nausea.v >= 100 or eq < 40:
            return "LOSE", "Yuck... I can't keep this down."
        if eq >= 75:
            return "GOOD", "Ooo, you made something yummy!"
        return "CONFUSED", "What… was this?"

    def menu_layout(self, btns, bottom_margin_px=None):
        sw, sh = self.screen.get_size()
        bw = int(min(sw * 0.36, 340 * self.scl))
        bh = max(44, min(64, int(sh * 0.076)))
        gap = max(10, int(bh * 0.2))
        bm = bottom_margin_px if bottom_margin_px is not None else max(56, int(sh * 0.08))
        span = len(btns) * bh + max(0, len(btns) - 1) * gap
        y0 = max(int(sh * 0.34), sh - bm - span)
        x = sw // 2 - bw // 2
        for i, b in enumerate(btns):
            b.set_rect((x, y0 + i * (bh + gap), bw, bh))

    def update(self, dt):
        self.update_global(dt)
        if self.state == State.MICROWAVE and self.mw_run:
            self.mw_time += dt * 20
        if self.state == State.CUTTING:
            if self.microwave_flashing_active:
                self.cutting_flash_cd -= dt
                if self.cutting_flash_cd <= 0:
                    self.flash_t = max(self.flash_t, 0.12 if self.microwave_flash_strength == 1 else 0.2)
                    self.shake_t = max(self.shake_t, 0.14 if self.microwave_flash_strength == 1 else 0.25)
                    self.headache.add(0.7 if self.microwave_flash_strength == 1 else 1.2)
                    self.control_penalty = max(self.control_penalty, 0.12 if self.microwave_flash_strength == 1 else 0.22)
                    self.cutting_flash_cd = random.uniform(2.7, 4.2) if self.microwave_flash_strength == 1 else random.uniform(1.6, 3.0)
            if hasattr(self, "_path") and self.cut_drag and self.cut_progress < len(self._path):
                p = self.cursor(extra_drift=0.6 if self.flash_t > 0 and self.microwave_flashing_active else 0.0)
                t = self._path[self.cut_progress]
                if math.dist(p, t) < 26 * self.scl:
                    self.cut_progress += 1
                    if random.random() < 0.08:
                        self.sfx.play("cut")
        if self.state == State.COOKING and not self.cook_done:
            self.cook_heat += dt * 28
            if self.cook_heat > 120:
                self.cook_heat = 120
                self.finish_cooking()
        if self.state == State.ASSEMBLY and self.asm_drag:
            cx, cy = self.cursor()
            wob = math.sin(pygame.time.get_ticks() * 0.01) * (1 + self.headache.v / 28)
            self.asm_drag["r"].center = (int(cx + wob), int(cy + wob * 0.3))
        if self.state == State.TASTE and self.taste_phase == "REACTION":
            self.taste_timer -= dt
            self.taste_react_t = max(0.0, self.taste_react_t - dt)
            if self.taste_timer <= 0:
                if self.taste_outcome == "LOSE":
                    self.state = State.LOSE
                    self.end_title = "You Couldn't Keep It Down"
                    self.end_msg = "Yuck... I can't keep this down."
                    self.end_play = "Try Again"
                elif self.taste_outcome == "GOOD":
                    self.state = State.WIN
                    self.end_title = "Snack Complete!"
                    self.end_msg = "Ooo, you made something yummy!"
                    self.end_play = "Play Again"
                else:
                    self.state = State.WIN
                    self.end_title = "Snack Complete...?"
                    self.end_msg = "What… was this?"
                    self.end_play = "Play Again"
        if self.state == State.TASTE:
            alive = []
            for c in self.taste_crumbs:
                c["x"] += c["vx"] * dt
                c["y"] += c["vy"] * dt
                c["vy"] += 260 * self.scl * dt
                c["t"] -= dt
                if c["t"] > 0:
                    alive.append(c)
            self.taste_crumbs = alive

    def draw(self):
        l = self.layout()
        if self.state == State.MENU:
            sh = self.screen.get_height()
            sw = self.screen.get_width()
            self.draw_menu_kitchen(self.screen)
            subtitle = self.font(20).render("A sleepy cartoon kitchen quest", True, (216, 226, 248))
            self.screen.blit(subtitle, subtitle.get_rect(center=(sw // 2, int(sh * 0.11))))
            title = self.font(58, True).render("3AM Snack", True, (247, 246, 255))
            self.screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.16))))
            self.menu_layout(self.menu_btns, int(sh * 0.046))
            for b in self.menu_btns:
                b.draw(self.screen)
        elif self.state == State.HOW:
            sw, sh = self.screen.get_width(), self.screen.get_height()
            self.draw_menu_kitchen(self.screen)
            bh = max(52, int(58 * self.scl))
            self.back_btn.set_rect((self.pad, sh - bh - self.pad, int(min(260, sw * 0.22)), bh))
            self.back_btn.draw(self.screen)
            head = self.font(32, True).render("How to play", True, (250, 248, 255))
            self.screen.blit(head, head.get_rect(center=(sw // 2, int(sh * 0.065))))
            help_r = pygame.Rect(self.pad + 14, self.pad + int(sh * 0.12), sw - self.pad * 2 - 28, sh - (self.pad + int(sh * 0.12)) - bh - self.pad * 3)
            self.wrap_fit(self.screen, HOW_PLAY_TEXT, help_r, fs=17, fs_min=9)
        elif self.state == State.FRIDGE:
            self.draw_bg(self.screen, True)
            self.draw_hud(self.screen, "Fridge: choose ingredients", "")
            self.wrap_fit(self.screen, "Fridge — tap tubs, Keep/Discard, Next at 3 kept items.", l["top"], 18, fs_min=11)
            self.handle_fridge_event(pygame.event.Event(pygame.NOEVENT), l)
            self.panel(self.screen, self._fridge_area)
            self.panel(self.screen, self._side_area)
            self.draw_fridge_cartoon(self.screen, self._fridge_area)
            for c in self.fridge_items:
                pygame.draw.rect(self.screen, (194, 218, 246), c.rect, border_radius=14)
                pygame.draw.rect(self.screen, (244, 245, 255), c.rect, 2, border_radius=14)
                self.screen.blit(self.font(12).render(self.short_panel_label(c.label, 13), True, (46, 52, 70)), (c.rect.x + self.pad // 4, c.rect.bottom - int(17 * self.scl)))
            rr = self._side_area.inflate(-self.pad, -self.pad)
            text_h = int(rr.h * 0.55)
            text_rr = pygame.Rect(rr.x, rr.y + int(6 * self.scl), rr.w, text_h)
            food_y = rr.bottom - int(rr.h * 0.2)
            if self.fridge_selected:
                self.wrap_fit(self.screen, f"{self.fridge_selected.label}\nMystery tub — Keep or Discard?", text_rr, 16, fs_min=10)
                self.draw_food(self.screen, "Mystery", (rr.centerx, food_y), self.scl * 0.95)
            elif self.fridge_reveal_item and self.fridge_reveal_timer > 0:
                self.wrap_fit(self.screen, f"Revealed:\n{self.fridge_reveal_item}", text_rr, 16, fs_min=10)
                self.draw_food(self.screen, self.fridge_reveal_item, (rr.centerx, food_y), self.scl * 0.95)
            b0, b1, b2 = Button(self, "Keep", (158, 222, 178), (176, 240, 197)), Button(self, "Discard", (238, 168, 182), (247, 188, 201)), Button(self, "Next")
            b0.set_rect(self._keep); b1.set_rect(self._discard); b2.set_rect(self._next)
            b0.draw(self.screen); b1.draw(self.screen); b2.draw(self.screen)
            self.wrap_fit(self.screen, self.fridge_msg, l["feedback"], 17, fs_min=10)
        elif self.state == State.MICROWAVE:
            self.draw_bg(self.screen, False)
            self.draw_hud(self.screen, "Microwave timing", f"{int(self.mw_time)//60}:{int(self.mw_time)%60:02d}")
            self.wrap_fit(self.screen, "Microwave — perfect 2:00 stop keeps the spooky beeping away.", l["top"], 17, fs_min=10)
            self.handle_microwave_event(pygame.event.Event(pygame.NOEVENT), l)
            self.panel(self.screen, self._mw_area)
            self.panel(self.screen, self._pkt_area)
            self.draw_microwave(self.screen, self._mw_area.inflate(-self.pad, -self.pad), f"{int(self.mw_time)//60}:{int(self.mw_time)%60:02d}")
            self.draw_packet(self.screen, self._pkt_area.inflate(-self.pad, -self.pad))
            self.wrap_fit(self.screen, "MICROWAVE 2:00", self._pkt_area.inflate(int(self.pad * 0.5), -self.pad), 17, fs_min=11, color=(42, 48, 68))
            for r, t in [(self._mw_b0, "Start"), (self._mw_b1, "Stop"), (self._mw_b2, "Next")]:
                b = Button(self, t); b.set_rect(r); b.draw(self.screen)
            if self.microwave_beeping:
                beep_txt = self.font(16, True).render("Beep…", True, (255, 220, 225))
                self.screen.blit(beep_txt, (self._pkt_area.x + self.pad, self._pkt_area.y + self.pad))
            self.wrap_fit(self.screen, self.mw_msg, l["feedback"], 16, fs_min=10)
        elif self.state == State.CUTTING:
            self.draw_bg(self.screen, False)
            self.draw_hud(self.screen, "Cut sausage", "")
            self.wrap_fit(self.screen, "Cutting — trace the green line with the drifting knife cursor.", l["top"], 17, fs_min=10)
            self.handle_cutting_event(pygame.event.Event(pygame.NOEVENT), l)
            pygame.draw.rect(self.screen, (208, 188, 160), self._board, border_radius=20)
            pygame.draw.rect(self.screen, (240, 228, 205), self._board, 2, border_radius=20)
            self.draw_food(self.screen, "Sausage", self._board.center, self.scl * 1.8)
            pygame.draw.lines(self.screen, (126, 255, 162), False, self._path, max(3, int(5 * self.scl)))
            for i in range(self.cut_progress):
                if i < len(self._path) - 1:
                    pygame.draw.line(self.screen, (255, 244, 132), self._path[i], self._path[i + 1], max(3, int(5 * self.scl)))
            self.draw_knife_cartoon(self.screen, self.cursor(extra_drift=0.6 if self.flash_t > 0 and self.microwave_flashing_active else 0.0))
            bn = Button(self, "Next"); bn.set_rect(self._cut_next); bn.draw(self.screen)
            self.wrap_fit(self.screen, self.cut_msg + (" Disturbance active." if self.microwave_flashing_active else ""), l["feedback"], 16, fs_min=10)
        elif self.state == State.COOKING:
            self.draw_bg(self.screen, False)
            self.draw_hud(self.screen, "Pan heat", f"Heat {int(self.cook_heat)}%")
            self.wrap_fit(self.screen, "Cooking — Remove while the heat marker sits in the green band.", l["top"], 17, fs_min=10)
            self.handle_cooking_event(pygame.event.Event(pygame.NOEVENT), l)
            pygame.draw.ellipse(self.screen, (74, 80, 98), self._cook_pan)
            pygame.draw.ellipse(self.screen, (212, 216, 235), self._cook_pan, max(2, int(3 * self.scl)))
            ih = self._cook_pan.inflate(int(-20 * self.scl), int(-14 * self.scl))
            pygame.draw.ellipse(self.screen, (52, 58, 72), ih)
            self.draw_food(self.screen, "Sausage", self._cook_pan.center, self.scl * 1.6)
            pygame.draw.rect(self.screen, (26, 34, 44), self._cook_bar, border_radius=10)
            s0 = int(self._cook_bar.left + (self.cook_a / 120) * self._cook_bar.w)
            s1 = int(self._cook_bar.left + (self.cook_b / 120) * self._cook_bar.w)
            pygame.draw.rect(self.screen, (108, 219, 122), (s0, self._cook_bar.y + 3, max(4, s1 - s0), self._cook_bar.h - 6), border_radius=8)
            cur = int(self._cook_bar.left + (self.cook_heat / 120) * self._cook_bar.w)
            pygame.draw.rect(self.screen, (250, 240, 172), (self._cook_bar.x + 2, self._cook_bar.y + 2, max(2, cur - self._cook_bar.x), self._cook_bar.h - 4), border_radius=8)
            pygame.draw.rect(self.screen, (226, 230, 250), self._cook_bar, 2, border_radius=10)
            br = Button(self, "Remove", (175, 220, 182), (193, 238, 199))
            br.set_rect(self._cook_remove)
            br.draw(self.screen)
            bn = Button(self, "Next"); bn.set_rect(self._cook_next); bn.draw(self.screen)
            self.wrap_fit(self.screen, self.cook_msg, l["feedback"], 16, fs_min=10)
        elif self.state == State.ASSEMBLY:
            self.draw_bg(self.screen, False)
            self.draw_hud(self.screen, "Assemble sandwich", "Glow = next slot. Two middle picks are freestyle.")
            self.wrap_fit(self.screen, "Seven layers: guided base bun stack + TWO “your pick” slots.", l["top"], 14, fs_min=9)
            self.layout_assembly(l)
            self.handle_assembly_event(pygame.event.Event(pygame.NOEVENT), l)
            if self.asm_slot_specs:
                self.wrap_fit(self.screen, ASSEMBLY_GUIDE_TEXT, self._asm_guide_area, 12, fs_min=9)
            pygame.draw.ellipse(self.screen, (236, 238, 246), self._asm_plate)
            pygame.draw.ellipse(self.screen, (245, 248, 255), self._asm_plate, 2)
            placed_n = sum(1 for x in self.asm_items if x["placed"])
            for i, slot in enumerate(self.asm_slots):
                hilite = i == placed_n and not self.asm_done
                bg = (142, 230, 174) if hilite else (186, 198, 224)
                edge = (74, 130, 98) if hilite else (110, 118, 140)
                pygame.draw.rect(self.screen, bg, slot, border_radius=12)
                pygame.draw.rect(self.screen, edge, slot, max(2, int(3 * self.scl)), border_radius=12)
                lx = slot.x + max(8, int(10 * self.scl))
                ly = slot.y + max(7, int(9 * self.scl))
                lab = self.assembly_slot_label(i)
                shade = self.font(10, True).render(lab, True, (18, 20, 30))
                lite = self.font(10, True).render(lab, True, (252, 252, 254))
                self.screen.blit(shade, (lx + 1, ly + 1))
                self.screen.blit(lite, (lx, ly))
            for it in self.asm_items:
                pygame.draw.rect(self.screen, (174, 226, 179) if it["placed"] else (246, 204, 184), it["r"], border_radius=14)
                pygame.draw.rect(self.screen, (245, 245, 255), it["r"], 2, border_radius=14)
                self.draw_food(self.screen, it["n"], it["r"].center, self.scl * 0.72)
            bt = Button(self, "Taste Snack", (179, 220, 190), (194, 237, 204))
            bt.set_rect(self._asm_next)
            bt.draw(self.screen)
            self.wrap_fit(self.screen, self.asm_msg, l["feedback"], 16, fs_min=10)
        elif self.state == State.TASTE:
            self.draw_bg(self.screen, True)
            self.draw_hud(self.screen, "Tap snack to eat", f"Bites {self.taste_bites}/{self.taste_need}")
            stack_show = self.taste_stack or self.build_taste_stack(self.selected_ingredients)
            if len(stack_show) <= 4:
                picks = ", ".join(stack_show)
            else:
                picks = ", ".join(stack_show[:4]) + f" (+{len(stack_show) - 4} more)"
            self.wrap_fit(self.screen, "Taste plate = your fridge keeps: " + picks + ".", l["top"], 15, fs_min=9)
            m = l["main"]
            char_area = pygame.Rect(m.x + int(m.w * 0.03), m.y + int(m.h * 0.06), int(m.w * 0.34), int(m.h * 0.78))
            plate = pygame.Rect(m.centerx - int(m.w * 0.02), m.y + int(m.h * 0.14), int(m.w * 0.34), int(m.h * 0.5))
            pygame.draw.ellipse(self.screen, (236, 238, 246), plate)
            pygame.draw.ellipse(self.screen, (245, 248, 255), plate, 2)
            layers = self.taste_stack or self.build_taste_stack(self.selected_ingredients)
            n = max(1, len(layers))
            ratio = min(1.0, self.taste_bites / max(1, self.taste_need))
            remaining = max(0.0, 1.0 - ratio)
            spacing = max(10, min(30, int(110 * self.scl / n)))
            sf = max(0.34, min(0.78, 2.05 / math.sqrt(n)))
            cy0 = plate.centery + int(8 * self.scl)
            half = (n - 1) * spacing / 2.0
            visible = int(math.ceil(n * remaining))
            if visible > 0:
                start = n - visible
                visible_layers = layers[start:]
                vn = len(visible_layers)
                vhalf = (vn - 1) * spacing / 2.0
                for idx, nm in enumerate(visible_layers):
                    cy = cy0 - vhalf + idx * spacing
                    scale = self.scl * sf
                    if idx == vn - 1 and ratio > 0:
                        # Top layer gradually shrinks while bites increase.
                        scale *= max(0.38, 1.0 - (ratio * 0.42))
                    self.draw_food(self.screen, nm, (plate.centerx, int(cy)), scale)
            else:
                empty = self.font(14, True).render("All gone!", True, (120, 128, 160))
                self.screen.blit(empty, empty.get_rect(center=(plate.centerx, plate.centery)))
            stack_h = max(int(plate.h * 0.2), int((n - 1) * spacing + 56 * self.scl * sf))
            self.taste_rect = pygame.Rect(
                int(plate.centerx - plate.w * 0.32),
                int(cy0 - half - 18 * self.scl),
                int(plate.w * 0.64),
                int(stack_h + 36 * self.scl),
            )
            for bx, by, br in self.taste_bite_marks:
                pygame.draw.circle(self.screen, (236, 238, 246), (int(bx), int(by)), br)
            for c in self.taste_crumbs:
                pygame.draw.circle(self.screen, (247, 226, 168), (int(c["x"]), int(c["y"])), max(2, int(4 * self.scl)))
            mood = "GOOD"
            if self.taste_phase == "REACTION":
                mood = self.taste_outcome
            elif self.nausea.v >= 90 or self.quality.v < 40:
                mood = "LOSE"
            elif self.quality.v < 75:
                mood = "CONFUSED"
            self.draw_person(self.screen, char_area, mood, ratio)
            eat_text = f"Tap snack to take bites ({self.taste_bites}/{self.taste_need})"
            if self.taste_phase == "REACTION":
                eat_text = self.taste_msg
            self.wrap_fit(self.screen, eat_text, l["feedback"], 16, fs_min=10)
        else:
            self.draw_bg(self.screen, True)
            self.wrap_fit(self.screen, f"{self.end_title}\n\n{self.end_msg}", self.get_scaled_rect(140, 96, BASE_W - 280, BASE_H - 200), 26, fs_min=12)
            self.menu_layout(self.end_btns)
            self.end_btns[0].text = self.end_play
            for b in self.end_btns:
                b.draw(self.screen)

        if self.flash_t > 0:
            f = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            f.fill((255, 255, 255, int(150 * min(1, self.flash_t / 0.2))))
            self.screen.blit(f, (0, 0))
        if self.shake_t > 0:
            c = self.screen.copy()
            self.screen.blit(c, (random.randint(-4, 4), random.randint(-4, 4)))

    def loop(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().loop()
