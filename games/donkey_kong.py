# donkey_kong_v6.py - Donkey Kong (barrels stage) - easier tuning + DK sideways profile sprite
#
# Updates vs v5 (per your request):
# - Slightly easier overall:
#   * Fewer simultaneous barrels (MAX_BARRELS=5)
#   * Barrel roll speed slowed (level 1-6 speed=1, later speed=2)
#   * More generous random spawn timing (wider interval range)
#   * Ladder drop chance reduced (barrels drop less often)
#   * Hammer lasts longer (7.5s) and scores a bit more (90 per barrel)
# - Donkey Kong sprite updated to a more "side profile" feel (classic DK stance):
#   * Head/face looking right
#   * Forward arm + back arm
#   * Hunched back silhouette
#
# Hardware mapping (matches your working games):
#   I2C(0): SCL=GP21, SDA=GP20
#   OLED: sh1106.SH1106_I2C(128, 64, rotate=90) -> 64x128 portrait
#   Buttons (PULL_UP, active LOW): UP=19, DOWN=18, RIGHT=16, LEFT=17
#
# Controls:
#   LEFT/RIGHT = move
#   UP held    = climb up (when on ladder)
#   DOWN held  = climb down (when on ladder)
#   DOWN click = jump (when NOT on ladder)

from machine import Pin, I2C
import sh1106
import framebuf
import time
import random
import sys

time.sleep(0.25)

i2c = I2C(0, scl=Pin(21), sda=Pin(20))
oled = sh1106.SH1106_I2C(128, 64, i2c, rotate=90)

btn_up    = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down  = Pin(18, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_left  = Pin(17, Pin.IN, Pin.PULL_UP)

W, H = 64, 128

def wait_for_all_released():
    while (not btn_up.value()) or (not btn_down.value()) or (not btn_left.value()) or (not btn_right.value()):
        time.sleep_ms(10)
    time.sleep_ms(60)

def show_centered_sideways(lines):
    fb = framebuf.FrameBuffer(bytearray(128 * 64 // 8), 128, 64, framebuf.MONO_HLSB)
    fb.fill(0)
    line_h = 10
    total_h = len(lines) * line_h - 2
    y = (64 - total_h) // 2
    if y < 0: y = 0
    for i, t in enumerate(lines):
        t = str(t)
        if len(t) > 16: t = t[:16]
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

def show_title():
    try:
        blit_pbm("donkeykong.pbm")
    except Exception:
        oled.fill(0)
        oled.text("DONKEY", 8, 30, 1)
        oled.text("KONG",  16, 42, 1)
        oled.text("UP:START", 4, 70, 1)
        oled.text("DN:QUIT",  4, 82, 1)
        oled.text("L/R MOVE", 4, 102, 1)
        oled.text("DN JUMP",  4, 114, 1)
        oled.show()

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
        return pu, pd, pl, pr, (nu == 0), (nd == 0), (nl == 0), (nr == 0)

# ---------------- Geometry ----------------
PLATS = [24, 46, 68, 90, 112]
PLAT_THICK = 2
PLAT_DIR = [1, -1, 1, -1, 1]

LADDERS = [
    (12, PLATS[0], PLATS[1]),
    (44, PLATS[0], PLATS[1]),
    (20, PLATS[1], PLATS[2]),
    (52, PLATS[1], PLATS[2]),
    (10, PLATS[2], PLATS[3]),
    (38, PLATS[2], PLATS[3]),
    (26, PLATS[3], PLATS[4]),
    (54, PLATS[3], PLATS[4]),
]

DK_X, DK_Y = 5, PLATS[0] - 16
PAUL_X, PAUL_Y = 50, PLATS[0] - 16

PX_W, PX_H = 7, 9

def clamp(v, a, b):
    if v < a: return a
    if v > b: return b
    return v

def rects_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return (ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by)

def platform_index_for_feet(feet_y):
    best_i = None
    best_d = 999
    for i, py in enumerate(PLATS):
        d = abs(feet_y - py)
        if d < best_d:
            best_d = d
            best_i = i
    if best_d <= 2:
        return best_i
    return None

def ladder_at(px, py):
    cx = px + PX_W // 2
    for (lx, y_top, y_bot) in LADDERS:
        if abs(cx - lx) <= 3 and (py + PX_H) >= y_top and py <= y_bot:
            return (lx, y_top, y_bot)
    return None

# ---------------- Sprites ----------------
def draw_mario(x, y, jumping=False, blink=False, hammer=False):
    if blink:
        return
    # hat
    oled.hline(x+1, y+0, 5, 1)
    oled.hline(x+0, y+1, 7, 1)
    # face
    oled.pixel(x+1, y+2, 1)
    oled.pixel(x+2, y+2, 1)
    oled.pixel(x+4, y+2, 1)
    oled.pixel(x+5, y+2, 1)
    oled.hline(x+2, y+3, 3, 1)
    # body
    oled.fill_rect(x+2, y+4, 3, 3, 1)
    oled.pixel(x+1, y+5, 1)
    oled.pixel(x+5, y+5, 1)
    # feet
    oled.hline(x+1, y+8, 2, 1)
    oled.hline(x+4, y+8, 2, 1)
    if jumping:
        oled.pixel(x+3, y+7, 0)
    if hammer:
        oled.hline(x+7, y+2, 3, 1)
        oled.vline(x+9, y+2, 4, 1)

def draw_dk_side_profile():
    # Side profile DK (facing right): hunched back + face + forward arm
    x, y = DK_X, DK_Y
    # back hump
    oled.fill_rect(x+3, y+3, 9, 3, 1)
    oled.fill_rect(x+2, y+5, 11, 4, 1)
    # torso
    oled.fill_rect(x+4, y+8, 9, 5, 1)
    # head (front)
    oled.fill_rect(x+10, y+4, 5, 5, 1)
    # snout/jaw
    oled.fill_rect(x+13, y+7, 3, 2, 1)
    # face carve
    oled.pixel(x+12, y+5, 0)
    oled.pixel(x+14, y+5, 0)
    oled.hline(x+12, y+6, 3, 0)
    oled.pixel(x+14, y+6, 0)
    oled.pixel(x+15, y+6, 1)
    # forward arm (throwing)
    oled.fill_rect(x+12, y+10, 4, 3, 1)
    oled.fill_rect(x+14, y+12, 2, 3, 1)
    # back arm
    oled.fill_rect(x+2, y+9, 3, 4, 1)
    # legs/base
    oled.fill_rect(x+5, y+13, 6, 2, 1)

    # belly hint (carve a little oval)
    oled.fill_rect(x+7, y+10, 3, 2, 0)
    oled.pixel(x+6, y+11, 0)
    oled.pixel(x+10, y+11, 0)

def draw_pauline(x=PAUL_X, y=PAUL_Y):
    # 10x14-ish character with hair shape
    oled.fill_rect(x+1, y+0, 8, 3, 1)
    oled.fill_rect(x+0, y+2, 10, 2, 1)
    oled.pixel(x+0, y+4, 1)
    oled.pixel(x+9, y+4, 1)
    oled.fill_rect(x+2, y+4, 6, 4, 1)
    oled.pixel(x+3, y+5, 0)
    oled.pixel(x+6, y+5, 0)
    oled.fill_rect(x+3, y+8, 4, 6, 1)
    oled.hline(x+2, y+13, 6, 1)
    oled.pixel(x+2, y+9, 1)
    oled.pixel(x+7, y+9, 1)

def _blit7(x, y, rows):
    # rows: list[int] 7-bit each, MSB on left
    for yy in range(7):
        row = rows[yy]
        for xx in range(7):
            if (row >> (6-xx)) & 1:
                oled.pixel(x+xx, y+yy, 1)

def draw_barrel(bx, by, age=0):
    """
    Round-ish Donkey Kong barrel (7x7) with a tiny 'rolling' illusion.
    age: int (use b["age"])
    """
    # Two animation frames: swap which band is solid to fake rotation
    frame = (age // 6) & 1  # slow wobble

    # Outline + fill silhouette (round)
    #  ..###..
    # .#####.
    # #######
    # ###.###
    # #######
    # .#####.
    #  ..###..
    base = [
        0b0011100,
        0b0111110,
        0b1111111,
        0b1110111,
        0b1111111,
        0b0111110,
        0b0011100,
    ]
    _blit7(bx, by, base)

    # Hollow center a bit so it reads like a barrel
    # (keep rim)
    for yy in range(2, 5):
        for xx in range(2, 5):
            oled.pixel(bx+xx, by+yy, 0)

    # Bands (swap between rows to suggest roll)
    if frame == 0:
        oled.hline(bx+1, by+2, 5, 1)
        oled.hline(bx+1, by+4, 5, 1)
    else:
        oled.hline(bx+1, by+3, 5, 1)

    # Rivets
    oled.pixel(bx+2, by+1, 1)
    oled.pixel(bx+4, by+5, 1)

def draw_hammer(hx, hy):
    oled.hline(hx+0, hy+1, 5, 1)
    oled.hline(hx+0, hy+2, 5, 1)
    oled.vline(hx+4, hy+2, 5, 1)

def draw_platforms_and_ladders():
    for py in PLATS:
        oled.fill_rect(0, py, W, PLAT_THICK, 1)
        for gx in range(0, W, 8):
            oled.pixel(gx+2, py+1, 0)
            oled.pixel(gx+6, py+1, 0)
    for (lx, y_top, y_bot) in LADDERS:
        oled.vline(lx-2, y_top, y_bot-y_top, 1)
        oled.vline(lx+2, y_top, y_bot-y_top, 1)
        yy = y_top + 2
        while yy < y_bot - 1:
            oled.hline(lx-1, yy, 3, 1)
            yy += 5

# ---------------- Barrels ----------------
MAX_BARRELS = 5

def spawn_barrel():
    return {"x": DK_X + 15, "y": PLATS[0] - 7, "plat": 0, "state": "roll",
            "dir": PLAT_DIR[0], "vy": 2, "age": 0}

def barrel_roll_speed(level):
    # slower for longer
    return 1 if level < 7 else 2

def update_barrel(b, level):
    b["age"] += 1
    spd = barrel_roll_speed(level)
    if b["state"] == "roll":
        b["dir"] = PLAT_DIR[b["plat"]]
        b["x"] += b["dir"] * spd
        if b["dir"] == 1 and b["x"] >= W - 7:
            b["x"] = W - 7
            b["state"] = "fall" if b["plat"] < len(PLATS) - 1 else "exit"
        elif b["dir"] == -1 and b["x"] <= 0:
            b["x"] = 0
            b["state"] = "fall" if b["plat"] < len(PLATS) - 1 else "exit"

        # ladder drop (reduced chance)
        if b["plat"] < len(PLATS) - 1 and random.randint(0, 55) == 0:
            for (lx, y_top, y_bot) in LADDERS:
                if y_top == PLATS[b["plat"]] and abs((b["x"]+3) - lx) <= 2:
                    b["state"] = "fall"
                    break
    elif b["state"] == "fall":
        b["y"] += b["vy"]
        nxt = b["plat"] + 1
        if nxt < len(PLATS) and b["y"] + 7 >= PLATS[nxt]:
            b["plat"] = nxt
            b["y"] = PLATS[nxt] - 7
            b["state"] = "roll"
    else:
        b["x"] += b["dir"] * 3

def next_spawn_delay_ms(level):
    # Wider, more natural randomness + slightly slower overall
    lo = 1050
    hi = 2400
    tighten = (level - 1) * 60
    lo = max(800, lo - tighten)
    hi = max(lo + 350, hi - tighten)
    # occasional long gap (very DK)
    if random.randint(0, 11) == 0:
        return random.randint(hi, hi + 900)
    return random.randint(lo, hi)

HAMMER_DURATION_MS = 7500
HAMMER_SCORE = 90

HAMMER_SPAWNS = [
    (6,  3),
    (52, 1),
]

# ---------------- Physics ----------------
GRAV = 1
JUMP_V = -6

def play_once():
    wait_for_all_released()
    show_title()
    wait_for_all_released()

    while True:
        if not btn_up.value():
            time.sleep_ms(180)
            break
        if not btn_down.value():
            time.sleep_ms(180)
            sys.exit()
        time.sleep_ms(20)

    eb = EdgeButtons()
    score = 0
    lives = 3
    level = 1

    while True:
        px, py = 4, PLATS[-1] - PX_H
        vy = 0
        jumping = False
        climbing = False
        invuln_until = 0

        barrels = []
        next_spawn = time.ticks_add(time.ticks_ms(), 1400)

        hammer_active_until = 0
        hammers = []
        for hx, pi in HAMMER_SPAWNS:
            hammers.append({"x": hx, "y": PLATS[pi] - 7, "taken": False})

        while True:
            now = time.ticks_ms()
            pu, pd, pl, pr, held_u, held_d, held_l, held_r = eb.update()

            vx = 0
            if held_l: vx = -1
            elif held_r: vx = 1

            lad = ladder_at(px, py)
            feet = py + PX_H
            pi = platform_index_for_feet(feet)

            # step off ladder to platform
            if lad and pi is not None and vx != 0 and not jumping:
                climbing = False
                vy = 0
                py = PLATS[pi] - PX_H
                lad = None

            if lad and (held_u or held_d) and not jumping:
                climbing = True
            if climbing and not lad:
                climbing = False

            # jump: DOWN click only when not on ladder/climbing
            if pd and (not jumping) and (not climbing) and (lad is None):
                if pi is not None:
                    jumping = True
                    vy = JUMP_V

            px = clamp(px + vx, 0, W - PX_W)

            if climbing and lad:
                if vx == 0:
                    lx = lad[0]
                    if abs((px + PX_W//2) - lx) <= 3:
                        px = clamp(lx - PX_W//2, 0, W - PX_W)
                if held_u and not held_d:
                    py -= 1
                elif held_d and not held_u:
                    py += 1
                py = clamp(py, lad[1]-PX_H, lad[2])
                vy = 0
                jumping = False
            else:
                vy += GRAV
                py += vy
                feet = py + PX_H
                landed = False
                for pyy in PLATS:
                    if feet >= pyy and feet <= pyy + 4 and vy >= 0:
                        py = pyy - PX_H
                        vy = 0
                        jumping = False
                        landed = True
                        break
                if not landed and py > H - PX_H:
                    py = H - PX_H
                    vy = 0
                    jumping = False

            # hammer pickup
            hammer_active = time.ticks_diff(now, hammer_active_until) < 0
            if not hammer_active:
                for hm in hammers:
                    if (not hm["taken"]) and rects_overlap(px, py, PX_W, PX_H, hm["x"], hm["y"], 7, 7):
                        hm["taken"] = True
                        hammer_active_until = time.ticks_add(now, HAMMER_DURATION_MS)
                        break
            hammer_active = time.ticks_diff(now, hammer_active_until) < 0

            # barrel spawn control (pause near goal)
            on_top = (pi == 0 and py <= PLATS[0] - PX_H + 1)
            near_goal = on_top and (px >= 40)
            allow_spawn = not near_goal

            if allow_spawn and time.ticks_diff(now, next_spawn) >= 0:
                # "fake-out" (a bit rarer now to reduce pressure)
                if len(barrels) < MAX_BARRELS and random.randint(0, 11) != 0:  # ~92% spawn
                    barrels.append(spawn_barrel())
                next_spawn = time.ticks_add(now, next_spawn_delay_ms(level))
            elif not allow_spawn:
                next_spawn = time.ticks_add(now, 750)

            # update barrels
            nb = []
            for b in barrels:
                update_barrel(b, level)
                if b["state"] == "exit" and (b["x"] < -10 or b["x"] > W + 10):
                    continue
                if b["age"] > 1700:
                    continue
                if b["y"] > H + 10:
                    continue
                nb.append(b)
            barrels = nb

            # hammer smash
            if hammer_active:
                killed = []
                for idx, b in enumerate(barrels):
                    if b["state"] != "exit" and rects_overlap(px, py, PX_W, PX_H, b["x"], b["y"], 7, 7):
                        killed.append(idx)
                if killed:
                    for idx in reversed(killed):
                        barrels.pop(idx)
                    score += HAMMER_SCORE * len(killed)

            # collisions (only if no hammer)
            if (not hammer_active) and time.ticks_diff(now, invuln_until) >= 0:
                for b in barrels:
                    if b["state"] != "exit" and rects_overlap(px, py, PX_W, PX_H, b["x"], b["y"], 7, 7):
                        lives -= 1
                        for _ in range(2):
                            oled.invert(1); time.sleep_ms(70)
                            oled.invert(0); time.sleep_ms(70)
                        if lives <= 0:
                            return score, level
                        px, py = 4, PLATS[-1] - PX_H
                        vy = 0
                        jumping = False
                        climbing = False
                        invuln_until = time.ticks_add(now, 1600)
                        break

            # win
            if rects_overlap(px, py, PX_W, PX_H, PAUL_X, PAUL_Y, 10, 14):
                score += 200
                level += 1
                oled.fill(0)
                oled.text("STAGE", 14, 52, 1)
                oled.text("CLEAR!", 10, 64, 1)
                oled.show()
                time.sleep(0.8)
                break

            # draw
            oled.fill(0)
            oled.text("L:%d" % lives, 0, 0, 1)
            s = str(score)
            if len(s) > 6: s = s[-6:]
            oled.text(s, W - len(s)*8, 0, 1)
            oled.hline(0, 9, W, 1)

            if hammer_active:
                oled.text("H", 28, 0, 1)

            draw_platforms_and_ladders()
            draw_dk_side_profile()
            draw_pauline()

            for hm in hammers:
                if not hm["taken"]:
                    draw_hammer(hm["x"], hm["y"])

            for b in barrels:
                if b["state"] != "exit":
                    draw_barrel(b["x"], b["y"], b["age"])

            blink = False
            if time.ticks_diff(now, invuln_until) < 0:
                blink = ((now // 120) & 1) == 0
            draw_mario(px, py, jumping=jumping, blink=blink, hammer=hammer_active)

            oled.show()
            time.sleep_ms(28)

def main():
    while True:
        score, level = play_once()
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
                break
            if not btn_down.value():
                time.sleep_ms(180)
                sys.exit()
            time.sleep_ms(20)

main()
