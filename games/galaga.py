# galaga_lite_v8.py - Galaga-lite with:
# 1) Challenge Stage every 3rd level (no enemy bullets, scripted swoops, bonus for perfect clear)
# 2) Boss "capture-lite" beam that costs a life but grants temporary double-shot on your next life
#
# Mapping matches your working SH1106 games:
# - I2C(0) on GP21/GP20
# - SH1106 rotate=90 (portrait 64x128)
# - Buttons PULL_UP active LOW: UP=GP19, DOWN=GP18, RIGHT=GP16, LEFT=GP17
#
# Controls:
# - LEFT/RIGHT: move ship (hold ok)
# - UP: fire (tap only)
# - DOWN: bomb (tap only; clears bullets + enemy bullets + cancels divers) / menus: quit
#
# Optional splash: galaga.pbm (128x64 P4)

from machine import Pin, I2C
import sh1106
import framebuf
import time
import random
import sys

time.sleep(0.3)
i2c = I2C(0, scl=Pin(21), sda=Pin(20))
oled = sh1106.SH1106_I2C(128, 64, i2c, rotate=90)  # 64x128 portrait

btn_up    = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down  = Pin(18, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_left  = Pin(17, Pin.IN, Pin.PULL_UP)

W, H = 64, 128

def clamp(v, lo, hi):
    if v < lo: return lo
    if v > hi: return hi
    return v

def aabb(ax, ay, aw, ah, bx, by, bw, bh):
    return (ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by)

def wait_for_all_released():
    while (not btn_up.value()) or (not btn_down.value()) or (not btn_left.value()) or (not btn_right.value()):
        time.sleep_ms(10)
    time.sleep_ms(60)

# ----------------------------
# Text screens
# ----------------------------
def show_centered_portrait(lines):
    oled.fill(0)
    line_h = 10
    total_h = len(lines) * line_h - 2
    y = (H - total_h) // 2
    if y < 0: y = 0
    for i, t in enumerate(lines):
        t = str(t)
        if len(t) > 8:
            t = t[:8]
        x = (W - len(t) * 8) // 2
        if x < 0: x = 0
        oled.text(t, x, y + i * line_h, 1)
    oled.show()

def show_centered_sideways(lines):
    fb = framebuf.FrameBuffer(bytearray(128 * 64 // 8), 128, 64, framebuf.MONO_HLSB)
    fb.fill(0)

    line_h = 10
    total_h = len(lines) * line_h - 2
    y = (64 - total_h) // 2
    if y < 0: y = 0

    for i, t in enumerate(lines):
        t = str(t)
        if len(t) > 16:
            t = t[:16]
        x = (128 - len(t) * 8) // 2
        if x < 0: x = 0
        fb.text(t, x, y + i * line_h, 1)

    rotated = bytearray(64 * 128 // 8)
    fb_rot = framebuf.FrameBuffer(rotated, 64, 128, framebuf.MONO_HLSB)
    fb_rot.fill(0)

    for xx in range(128):
        for yy in range(64):
            if fb.pixel(xx, yy):
                fb_rot.pixel(63 - yy, xx, 1)

    oled.fill(0)
    oled.blit(fb_rot, 0, 0)
    oled.show()

# ----------------------------
# Optional PBM splash (128x64 P4) -> rotate into portrait
# ----------------------------
def blit_pbm(filename):
    with open(filename, "rb") as f:
        if f.readline().strip() != b"P4":
            raise ValueError("Not P4")
        line = f.readline()
        while line.startswith(b"#"):
            line = f.readline()
        w, h = [int(x) for x in line.split()]
        data = bytearray(f.read())

    fb = framebuf.FrameBuffer(data, w, h, framebuf.MONO_HLSB)

    rotated = bytearray(64 * 128 // 8)
    fb_rot = framebuf.FrameBuffer(rotated, 64, 128, framebuf.MONO_HLSB)
    fb_rot.fill(0)

    for xx in range(w):
        for yy in range(h):
            if fb.pixel(xx, yy):
                fb_rot.pixel(63 - yy, xx, 1)

    oled.fill(0)
    oled.blit(fb_rot, 0, 0)
    oled.show()

def show_splash():
    try:
        blit_pbm("galaga.pbm")
    except Exception:
        show_centered_portrait(["GALAGA", "LITE", "", "UP=GO", "DN=QT"])

# ----------------------------
# Sprites (9x7 enemies, bug-like)
# ----------------------------
SHIP_W, SHIP_H = 9, 7
EN_W, EN_H = 9, 7
PB_W, PB_H = 1, 4  # player bullet
EB_W, EB_H = 1, 3  # enemy bullet

def draw_ship(x, y):
    oled.fill_rect(x + 3, y, 3, 2, 1)
    oled.fill_rect(x + 1, y + 2, 7, 3, 1)
    oled.fill_rect(x, y + 5, 9, 2, 1)
    oled.pixel(x + 2, y + 6, 0)
    oled.pixel(x + 6, y + 6, 0)

def _draw_sprite_9x7(x, y, rows):
    for ry in range(7):
        bits = rows[ry]
        for rx in range(9):
            if bits & (1 << (8 - rx)):
                oled.pixel(x + rx, y + ry, 1)

BEE_A = [
    0b001111100,
    0b011000110,
    0b111101111,
    0b011111110,
    0b001011100,
    0b010111010,
    0b100000001,
]
BEE_B = [
    0b001111100,
    0b110000011,
    0b111101111,
    0b011111110,
    0b010111010,
    0b001011100,
    0b100000001,
]
BOSS_A = [
    0b011111110,
    0b111000111,
    0b111111111,
    0b011111110,
    0b110111011,
    0b110000011,
    0b010000010,
]
BOSS_B = [
    0b011111110,
    0b111000111,
    0b111111111,
    0b011111110,
    0b110000011,
    0b110111011,
    0b010000010,
]

def draw_enemy(x, y, etype, anim_phase):
    if etype == 1:
        rows = BOSS_B if anim_phase else BOSS_A
    else:
        rows = BEE_B if anim_phase else BEE_A
    _draw_sprite_9x7(x, y, rows)

def draw_player_bullet(x, y):
    oled.vline(x, y, PB_H, 1)

def draw_enemy_bullet(x, y):
    oled.vline(x, y, EB_H, 1)

def draw_beam(x_center, y_top, y_bottom):
    # thin "tractor beam" look
    oled.vline(x_center, y_top, max(1, y_bottom - y_top), 1)
    oled.vline(x_center - 1, y_top + 3, max(1, y_bottom - y_top - 6), 1)

# ----------------------------
# Formation layout
# ----------------------------
PLAY_TOP = 12
SHIP_Y = H - SHIP_H - 3

FORMATION_COLS = 6
FORMATION_ROWS = 3
SP_X = 2
SP_Y = 8

FORM_W = FORMATION_COLS * EN_W + (FORMATION_COLS - 1) * SP_X
FORM_H = FORMATION_ROWS * EN_H + (FORMATION_ROWS - 1) * SP_Y

def make_wave(level):
    enemies = []
    for r in range(FORMATION_ROWS):
        for c in range(FORMATION_COLS):
            etype = 0
            hp = 1
            if level >= 3 and r == 0 and (c % 2 == 0):
                etype = 1
                hp = 2
            enemies.append({
                "r": r, "c": c,
                "alive": True,
                "type": etype,
                "hp": hp,
                "state": "form",    # form | dive | return | beam
                "x": 0, "y": 0,
                "vx": 0, "vy": 0,
                "home_x": 0, "home_y": 0,
                "phase": random.randint(0, 255),
                "next_shot": time.ticks_ms() + random.randint(400, 1200),
                "beam_t": 0,        # beam timer
                "script": 0,        # used by challenge stage patterns
            })
    return enemies

def compute_home(form_x, form_y, e):
    x = form_x + e["c"] * (EN_W + SP_X)
    y = form_y + e["r"] * (EN_H + SP_Y)
    return x, y

# ----------------------------
# Edge-detect input
# ----------------------------
class EdgeButtons:
    def __init__(self):
        self.u = 1; self.d = 1; self.l = 1; self.r = 1

    def update(self):
        nu = btn_up.value()
        nd = btn_down.value()
        nl = btn_left.value()
        nr = btn_right.value()

        pu = (self.u == 1 and nu == 0)
        pd = (self.d == 1 and nd == 0)
        pl = (self.l == 1 and nl == 0)
        pr = (self.r == 1 and nr == 0)

        self.u, self.d, self.l, self.r = nu, nd, nl, nr
        return pu, pd, pl, pr

# ----------------------------
# Behaviors
# ----------------------------
def max_divers(level):
    if level <= 2: return 1
    if level <= 5: return 2
    return 3

def dive_interval_ms(level):
    return max(750, 1700 - level * 120)

def form_step_ms(level):
    return max(70, 130 - level * 5)

def pick_diver(enemies):
    cands = [e for e in enemies if e["alive"] and e["state"] == "form"]
    if not cands:
        return None
    cands.sort(key=lambda z: z["r"])
    pool = cands[:min(10, len(cands))]
    return random.choice(pool)

def start_dive(e, ship_x):
    e["state"] = "dive"
    target_x = ship_x + SHIP_W // 2
    dx = target_x - (e["home_x"] + EN_W // 2)
    vx = clamp(dx // 10, -3, 3)
    if vx == 0 and dx != 0:
        vx = 1 if dx > 0 else -1
    e["vx"] = vx
    e["vy"] = 2
    e["beam_t"] = 0

def step_diver(e, tick, level):
    wob = ((tick + e["phase"]) & 31)
    if wob < 8:
        e["x"] += e["vx"] + 1
    elif wob < 16:
        e["x"] += e["vx"]
    elif wob < 24:
        e["x"] += e["vx"] - 1
    else:
        e["x"] += e["vx"]

    e["y"] += e["vy"] + (1 if level >= 6 else 0)

    if e["x"] < -3:
        e["x"] = -3
        e["vx"] = abs(e["vx"])
    elif e["x"] > W - EN_W + 3:
        e["x"] = W - EN_W + 3
        e["vx"] = -abs(e["vx"])

    if e["y"] >= H - 26:
        e["state"] = "return"

def step_return(e):
    hx, hy = e["home_x"], e["home_y"]
    dx = hx - e["x"]
    dy = hy - e["y"]

    if dx > 0: e["x"] += 1
    elif dx < 0: e["x"] -= 1

    if dy > 0: e["y"] += 2
    elif dy < 0: e["y"] -= 2

    if abs(dx) <= 1 and abs(dy) <= 2:
        e["x"] = hx
        e["y"] = hy
        e["state"] = "form"

# Enemy shooting tuning
def enemy_shot_interval_ms(level, etype, diving):
    base = 1400 if not diving else 900
    if etype == 1:
        base -= 220
    base -= level * 40
    return max(350, base)

def can_enemy_shoot(e, ship_x):
    ex = int(e["x"]) + EN_W // 2
    px = ship_x + SHIP_W // 2
    dx = abs(px - ex)
    if e["state"] == "form":
        return dx <= 4
    return dx <= 10

# ----------------------------
# Challenge Stage
# ----------------------------
def is_challenge_stage(level):
    return (level % 3) == 0

def init_challenge(enemies):
    # Give each enemy a scripted phase offset so they "take turns" swooping.
    # We'll reuse state="dive"/"return" but drive motion by script step.
    order = 0
    for e in enemies:
        if not e["alive"]:
            continue
        e["script"] = order
        order += 1

def challenge_should_launch(e, t_ms):
    # Launch in staggered groups
    # every ~350ms start another enemy
    launch_at = e["script"] * 350
    return t_ms >= launch_at and e["state"] == "form"

def step_challenge_dive(e, tick):
    # tighter "show off" swoop pattern, always returns
    # mild S-curve using phase
    wob = ((tick + e["phase"]) & 31)
    if wob < 8:
        e["x"] += 2
    elif wob < 16:
        e["x"] += 1
    elif wob < 24:
        e["x"] -= 1
    else:
        e["x"] -= 2
    e["y"] += 2
    if e["y"] >= H - 22:
        e["state"] = "return"

# ----------------------------
# Game run
# ----------------------------
def play_once():
    wait_for_all_released()
    show_splash()
    wait_for_all_released()

    while True:
        if not btn_up.value():
            time.sleep_ms(180)
            break
        if not btn_down.value():
            time.sleep_ms(180)
            sys.exit()
        time.sleep_ms(20)

    score = 0
    level = 1
    lives = 3
    bombs = 2

    # capture-lite powerup: if True, next life has double-shot until you die again
    double_shot = False

    def bullets_cap():
        return 4 if double_shot else 2

    ship_x = (W - SHIP_W) // 2
    player_bullets = []
    enemy_bullets = []

    enemies = make_wave(level)

    form_x = (W - FORM_W) // 2
    form_y = PLAY_TOP
    dir_x = 1

    eb = EdgeButtons()
    last_lr = time.ticks_ms()
    last_form = time.ticks_ms()
    last_dive = time.ticks_ms()
    last_anim = time.ticks_ms()
    anim_phase = 0
    tick = 0
    invuln_until = 0

    def lr_cd():
        return 45

    show_centered_portrait(["READY", "", "TAP UP", "TO FIRE"])
    time.sleep(0.6)

    challenge = False
    challenge_start_ms = 0
    challenge_perfect = False

    while True:
        now = time.ticks_ms()
        tick = (tick + 1) & 0xFFFF

        if time.ticks_diff(now, last_anim) > 160:
            last_anim = now
            anim_phase ^= 1

        pressed_up, pressed_down, _, _ = eb.update()

        # ship move
        if time.ticks_diff(now, last_lr) > lr_cd():
            if not btn_left.value():
                ship_x -= 2
                last_lr = now
            elif not btn_right.value():
                ship_x += 2
                last_lr = now
        ship_x = clamp(ship_x, 0, W - SHIP_W)

        # fire (tap) - double-shot if powerup
        if pressed_up:
            if len(player_bullets) < bullets_cap():
                cx = ship_x + SHIP_W // 2
                if double_shot:
                    player_bullets.append({"x": cx - 2, "y": SHIP_Y - 2})
                    if len(player_bullets) < bullets_cap():
                        player_bullets.append({"x": cx + 2, "y": SHIP_Y - 2})
                else:
                    player_bullets.append({"x": cx, "y": SHIP_Y - 2})

        # bomb (tap)
        if pressed_down and bombs > 0:
            bombs -= 1
            player_bullets.clear()
            enemy_bullets.clear()
            for e in enemies:
                if e["alive"] and e["state"] in ("dive", "return", "beam"):
                    e["state"] = "form"
                    e["x"], e["y"] = e["home_x"], e["home_y"]
                    e["beam_t"] = 0
            oled.invert(1); time.sleep_ms(60)
            oled.invert(0); time.sleep_ms(60)

        # formation hover
        if time.ticks_diff(now, last_form) > form_step_ms(level):
            last_form = now
            form_x += dir_x
            if form_x < 0:
                form_x = 0
                dir_x = 1
            elif form_x > (W - FORM_W):
                form_x = (W - FORM_W)
                dir_x = -1

        # update homes + snap form enemies
        for e in enemies:
            if not e["alive"]:
                continue
            hx, hy = compute_home(form_x, form_y, e)
            e["home_x"], e["home_y"] = hx, hy
            if e["state"] == "form":
                e["x"], e["y"] = hx, hy

        # enter challenge stage
        if (not challenge) and is_challenge_stage(level):
            challenge = True
            challenge_start_ms = now
            challenge_perfect = True
            init_challenge(enemies)
            player_bullets.clear()
            enemy_bullets.clear()
            show_centered_portrait(["CHALLNG", "STAGE", "", "BONUS!"])
            time.sleep(0.55)

        # start dives
        if challenge:
            tms = time.ticks_diff(now, challenge_start_ms)
            for e in enemies:
                if not e["alive"]:
                    continue
                if challenge_should_launch(e, tms):
                    e["state"] = "dive"
                    # start from home position
                    e["x"], e["y"] = e["home_x"], e["home_y"]
        else:
            diving_now = 0
            for e in enemies:
                if e["alive"] and e["state"] in ("dive", "return", "beam"):
                    diving_now += 1

            if diving_now < max_divers(level) and time.ticks_diff(now, last_dive) > dive_interval_ms(level):
                last_dive = now
                diver = pick_diver(enemies)
                if diver:
                    start_dive(diver, ship_x)

        # move bullets
        i = 0
        while i < len(player_bullets):
            b = player_bullets[i]
            b["y"] -= 3
            if b["y"] < 0:
                player_bullets.pop(i)
            else:
                i += 1

        j = 0
        while j < len(enemy_bullets):
            b = enemy_bullets[j]
            b["y"] += 2 + (1 if level >= 7 else 0)
            if b["y"] > H:
                enemy_bullets.pop(j)
            else:
                j += 1

        # move enemies (divers/return/beam)
        for e in enemies:
            if not e["alive"]:
                continue

            if challenge:
                if e["state"] == "dive":
                    step_challenge_dive(e, tick)
                elif e["state"] == "return":
                    step_return(e)
            else:
                if e["state"] == "dive":
                    # boss capture-lite: sometimes switch to beam when aligned near bottom
                    if e["type"] == 1 and e["beam_t"] == 0:
                        # only attempt beam when around lower mid
                        if int(e["y"]) > 68 and int(e["y"]) < 92:
                            ex = int(e["x"]) + EN_W // 2
                            px = ship_x + SHIP_W // 2
                            if abs(px - ex) <= 3 and (random.getrandbits(3) == 0):  # ~1/8 chance when aligned
                                e["state"] = "beam"
                                e["beam_t"] = 18  # frames
                    if e["state"] == "dive":
                        step_diver(e, tick, level)

                elif e["state"] == "beam":
                    # hold position, extend beam for a short time, then return
                    e["beam_t"] -= 1
                    if e["beam_t"] <= 0:
                        e["beam_t"] = 0
                        e["state"] = "return"
                elif e["state"] == "return":
                    step_return(e)

        # enemy shooting (disabled during challenge)
        if (not challenge):
            # cap bullets for sanity
            if len(enemy_bullets) < 4 + (level // 3):
                for e in enemies:
                    if not e["alive"]:
                        continue
                    if e["state"] == "beam":
                        continue
                    if time.ticks_diff(now, e["next_shot"]) >= 0:
                        diving = (e["state"] != "form")
                        if can_enemy_shoot(e, ship_x):
                            enemy_bullets.append({
                                "x": int(e["x"]) + EN_W // 2,
                                "y": int(e["y"]) + EN_H
                            })
                        e["next_shot"] = time.ticks_add(
                            now,
                            enemy_shot_interval_ms(level, e["type"], diving) + random.randint(0, 250)
                        )

        # player bullets hit enemies
        bi = 0
        while bi < len(player_bullets):
            b = player_bullets[bi]
            hit = False
            for e in enemies:
                if not e["alive"]:
                    continue
                if aabb(b["x"], b["y"], PB_W, PB_H, int(e["x"]), int(e["y"]), EN_W, EN_H):
                    player_bullets.pop(bi)
                    e["hp"] -= 1
                    if e["hp"] <= 0:
                        e["alive"] = False
                        score += 25 if e["type"] == 1 else 10
                    else:
                        score += 5
                    hit = True
                    break
            if not hit:
                bi += 1

        # capture-lite beam hits player (boss only)
        if (not challenge) and (time.ticks_diff(invuln_until, now) < 0):
            captured = False
            for e in enemies:
                if not e["alive"]:
                    continue
                if e["state"] == "beam" and e["beam_t"] > 0:
                    bx = int(e["x"]) + EN_W // 2
                    # If beam overlaps player x-range, it's a hit
                    if bx >= ship_x and bx <= ship_x + SHIP_W - 1:
                        # beam reaches ship area
                        if int(e["y"]) + EN_H < SHIP_Y + SHIP_H:
                            captured = True
                            break
            if captured:
                lives -= 1
                # grant double-shot for the next life
                double_shot = True
                player_bullets.clear()
                enemy_bullets.clear()
                for ee in enemies:
                    if ee["alive"]:
                        ee["state"] = "form"
                        ee["x"], ee["y"] = ee["home_x"], ee["home_y"]
                        ee["beam_t"] = 0
                for _ in range(2):
                    oled.invert(1); time.sleep_ms(70)
                    oled.invert(0); time.sleep_ms(70)
                invuln_until = time.ticks_add(now, 1200)
                ship_x = (W - SHIP_W) // 2
                # capture costs you a life; if that was the last one, end
                if lives <= 0:
                    break

        # enemy bullets hit player
        if time.ticks_diff(invuln_until, now) < 0:
            k = 0
            while k < len(enemy_bullets):
                ebull = enemy_bullets[k]
                if aabb(ship_x, SHIP_Y, SHIP_W, SHIP_H, ebull["x"], ebull["y"], EB_W, EB_H):
                    enemy_bullets.pop(k)
                    lives -= 1
                    # losing a normal life clears double-shot
                    double_shot = False
                    player_bullets.clear()
                    enemy_bullets.clear()
                    for e in enemies:
                        if e["alive"]:
                            e["state"] = "form"
                            e["x"], e["y"] = e["home_x"], e["home_y"]
                            e["beam_t"] = 0
                    for _ in range(2):
                        oled.invert(1); time.sleep_ms(70)
                        oled.invert(0); time.sleep_ms(70)
                    invuln_until = time.ticks_add(now, 1200)
                    ship_x = (W - SHIP_W) // 2
                    break
                else:
                    k += 1

        # enemy collides with player
        if time.ticks_diff(invuln_until, now) < 0:
            for e in enemies:
                if not e["alive"]:
                    continue
                if e["state"] in ("dive", "return", "beam"):
                    if aabb(ship_x, SHIP_Y, SHIP_W, SHIP_H, int(e["x"]), int(e["y"]), EN_W, EN_H):
                        lives -= 1
                        double_shot = False
                        player_bullets.clear()
                        enemy_bullets.clear()
                        for ee in enemies:
                            if ee["alive"]:
                                ee["state"] = "form"
                                ee["x"], ee["y"] = ee["home_x"], ee["home_y"]
                                ee["beam_t"] = 0
                        for _ in range(2):
                            oled.invert(1); time.sleep_ms(70)
                            oled.invert(0); time.sleep_ms(70)
                        invuln_until = time.ticks_add(now, 1200)
                        ship_x = (W - SHIP_W) // 2
                        break

        if lives <= 0:
            break

        # end of challenge stage:
        if challenge:
            # if all enemies cleared -> bonus
            if all((not e["alive"]) for e in enemies):
                score += 200 + level * 30
                show_centered_portrait(["PERFECT", "BONUS", "+%d" % (200 + level * 30)])
                time.sleep(0.7)
                challenge = False
                # advance to next level after a cleared challenge
                level += 1
                if bombs < 3:
                    bombs += 1
                enemies = make_wave(level)
                player_bullets.clear()
                enemy_bullets.clear()
                form_x = (W - FORM_W) // 2
                dir_x = 1
                show_centered_portrait(["LEVEL", str(level), "", "GO!"])
                time.sleep(0.6)
                continue

            # timeout after ~12 seconds even if not cleared
            if time.ticks_diff(now, challenge_start_ms) > 12000:
                # if you didn't clear, just continue (no bonus)
                challenge = False
                level += 1
                if bombs < 3:
                    bombs += 1
                enemies = make_wave(level)
                player_bullets.clear()
                enemy_bullets.clear()
                form_x = (W - FORM_W) // 2
                dir_x = 1
                show_centered_portrait(["LEVEL", str(level), "", "GO!"])
                time.sleep(0.6)
                continue

        # normal wave clear
        if (not challenge) and all((not e["alive"]) for e in enemies):
            level += 1
            if bombs < 3:
                bombs += 1
            enemies = make_wave(level)
            player_bullets.clear()
            enemy_bullets.clear()
            form_x = (W - FORM_W) // 2
            dir_x = 1
            show_centered_portrait(["LEVEL", str(level), "", "GO!"])
            time.sleep(0.6)

        # draw
        oled.fill(0)
        oled.hline(0, 9, W, 1)
        # HUD: lives + bombs + DS indicator
        hud = "L:%d B:%d" % (lives, bombs)
        if double_shot:
            hud = "L:%d DS" % lives
        oled.text(hud[:8], 0, 0, 1)

        for e in enemies:
            if not e["alive"]:
                continue
            draw_enemy(int(e["x"]), int(e["y"]), e["type"], anim_phase)
            if e["state"] == "beam" and e["beam_t"] > 0:
                bx = int(e["x"]) + EN_W // 2
                draw_beam(bx, int(e["y"]) + EN_H, SHIP_Y + SHIP_H)

        for b in player_bullets:
            draw_player_bullet(b["x"], b["y"])

        if not challenge:
            for b in enemy_bullets:
                draw_enemy_bullet(b["x"], b["y"])

        if time.ticks_diff(invuln_until, now) < 0 or (tick & 2) == 0:
            draw_ship(ship_x, SHIP_Y)

        oled.show()
        time.sleep_ms(16)

    wait_for_all_released()
    show_centered_sideways([
        "GAME OVER",
        "SCORE %d" % score,
        "LEVEL %d" % level,
        "",
        "UP: RETRY",
        "DOWN: QUIT",
    ])
    while True:
        if not btn_up.value():
            time.sleep_ms(180)
            return True
        if not btn_down.value():
            time.sleep_ms(180)
            sys.exit()
        time.sleep_ms(20)

while True:
    play_once()
