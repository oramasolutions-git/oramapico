# asteroids.py - Classic Asteroids for Pico 2 W + 64x128 portrait OLED (SH1106 rotate=90)
#
# Matches your working game mappings:
#   I2C(0): SCL=GP21, SDA=GP20
#   OLED: sh1106.SH1106_I2C(128, 64, rotate=90)  -> 64x128 portrait
#   Buttons (PULL_UP, active LOW):
#       UP=GP19, DOWN=GP18, RIGHT=GP16, LEFT=GP17
#
# Controls:
#   LEFT  = rotate left
#   RIGHT = rotate right
#   UP    = thrust
#   DOWN  = fire (edge-triggered: click to shoot, no autofire)
#
# Optional splash: asteroids.pbm (128x64 P4). If missing, simple title text.
#
# Gameplay:
# - Wrap-around playfield
# - 3 asteroid sizes, split on hit
# - Lives + score, sideways Game Over screen like your other games
#
# Tip: If you want hyperspace later, we can add "hold DOWN for 400ms" etc.

from machine import Pin, I2C
import sh1106
import framebuf
import time
import random
import sys

time.sleep(0.25)

# --- Display / input (same style as your other games) ---
i2c = I2C(0, scl=Pin(21), sda=Pin(20))
oled = sh1106.SH1106_I2C(128, 64, i2c, rotate=90)  # 64x128 portrait

btn_up    = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down  = Pin(18, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_left  = Pin(17, Pin.IN, Pin.PULL_UP)

W, H = 64, 128

# --- Helpers ---
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
    # rotate 128x64 -> 64x128
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
        blit_pbm("asteroids.pbm")
    except Exception:
        oled.fill(0)
        oled.text("ASTEROIDS", 0, 34, 1)
        oled.text("UP=THRUST", 0, 52, 1)
        oled.text("DN=FIRE",   0, 62, 1)
        oled.text("L/R=TURN",  0, 72, 1)
        oled.text("UP=START",  0, 92, 1)
        oled.text("DN=QUIT",   0, 102, 1)
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

# Fixed-point scale
FP = 256

def wrap_fp(x_fp, max_px):
    # x_fp in fixed-point, wrap within [0, max_px)
    max_fp = max_px * FP
    if x_fp < 0:
        x_fp += max_fp
    elif x_fp >= max_fp:
        x_fp -= max_fp
    return x_fp

# 16-direction LUT (dx, dy) scaled by FP, for angle indices 0..15
# 0 = up, 4 = right, 8 = down, 12 = left
DIR = [
    (0,   -256),
    (98,  -236),
    (181, -181),
    (236, -98),
    (256, 0),
    (236, 98),
    (181, 181),
    (98,  236),
    (0,   256),
    (-98, 236),
    (-181,181),
    (-236,98),
    (-256,0),
    (-236,-98),
    (-181,-181),
    (-98, -236),
]

def line(x0, y0, x1, y1):
    oled.line(x0, y0, x1, y1, 1)

def draw_ship(x, y, ang_idx, blink=False):
    if blink:
        return
    # triangle points based on direction vectors
    dx, dy = DIR[ang_idx]
    # nose
    nx = x + (dx * 6) // FP
    ny = y + (dy * 6) // FP
    # left/right wings are perpendicular-ish: use ang +/- 4 (90deg)
    lx, ly = DIR[(ang_idx - 4) & 15]
    rx, ry = DIR[(ang_idx + 4) & 15]
    wx1 = x + (lx * 4) // FP
    wy1 = y + (ly * 4) // FP
    wx2 = x + (rx * 4) // FP
    wy2 = y + (ry * 4) // FP

    line(nx, ny, wx1, wy1)
    line(nx, ny, wx2, wy2)
    line(wx1, wy1, wx2, wy2)

def draw_asteroid(a):
    # draw as a jagged polygon-ish loop from a small template scaled by size
    # templates are tiny so it looks more "Asteroids" than circles
    # points are in a 9x9 space centered at (0,0)
    pts = a["pts"]
    s = a["s"]  # size radius-ish in pixels
    cx = a["x"] // FP
    cy = a["y"] // FP

    # scale from template (-4..+4) to size
    last = None
    first = None
    for px, py in pts:
        x = cx + (px * s) // 4
        y = cy + (py * s) // 4
        if first is None:
            first = (x, y)
            last = (x, y)
        else:
            line(last[0], last[1], x, y)
            last = (x, y)
    if first and last:
        line(last[0], last[1], first[0], first[1])

def rand_asteroid_shape():
    # pick from a few classic-ish jagged shapes
    shapes = [
        [(-4,-1), (-2,-4), (1,-4), (4,-2), (3,2), (1,4), (-2,3), (-4,1)],
        [(-4,-2), (-1,-4), (2,-3), (4,-1), (3,3), (0,4), (-3,2), (-2,0)],
        [(-3,-4), (1,-4), (4,-1), (2,1), (4,4), (0,3), (-4,4), (-2,0)],
    ]
    return random.choice(shapes)

def spawn_asteroid(size, avoid_x, avoid_y):
    # spawn away from ship
    for _ in range(20):
        x = random.randint(0, W-1)
        y = random.randint(10, H-1)
        if (x-avoid_x)*(x-avoid_x) + (y-avoid_y)*(y-avoid_y) > (22*22):
            break
    # velocity
    ang = random.getrandbits(4) & 15
    dx, dy = DIR[ang]
    speed = random.randint(40, 90)  # fixed-point per tick divisor-ish
    vx = (dx * speed) // 256
    vy = (dy * speed) // 256
    return {
        "x": x * FP,
        "y": y * FP,
        "vx": vx,
        "vy": vy,
        "size": size,           # 3 big, 2 mid, 1 small
        "s": 12 if size == 3 else (8 if size == 2 else 5),
        "r2": (12 if size == 3 else (8 if size == 2 else 5))**2,
        "pts": rand_asteroid_shape(),
    }

def spawn_wave(n_big, shipx, shipy):
    ast = []
    for _ in range(n_big):
        ast.append(spawn_asteroid(3, shipx, shipy))
    return ast

def dist2(x0, y0, x1, y1):
    dx = x0 - x1
    dy = y0 - y1
    return dx*dx + dy*dy

def play_once():
    wait_for_all_released()
    show_title()
    wait_for_all_released()
    # UP start, DOWN quit
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
    wave = 1

    # Ship state
    ship_x = (W//2) * FP
    ship_y = (H//2) * FP
    ship_vx = 0
    ship_vy = 0
    ang = 0
    invuln_until = 0

    bullets = []  # {x,y,vx,vy,ttl}
    asteroids = spawn_wave(3, W//2, H//2)

    last_fire_ms = 0

    while True:
        now = time.ticks_ms()
        pu, pd, pl, pr, held_u, held_d, held_l, held_r = eb.update()

        # --- input ---
        if held_l:
            ang = (ang - 1) & 15
        if held_r:
            ang = (ang + 1) & 15

        if held_u:
            dx, dy = DIR[ang]
            # thrust (add small accel)
            ship_vx += (dx * 10) // 256
            ship_vy += (dy * 10) // 256

        # fire on click only
        if pd:
            # small debounce window to avoid double-taps from bounce
            if time.ticks_diff(now, last_fire_ms) > 140:
                dx, dy = DIR[ang]
                # bullet speed
                bvx = ship_vx + (dx * 180) // 256
                bvy = ship_vy + (dy * 180) // 256
                bullets.append({
                    "x": ship_x + (dx * 7),
                    "y": ship_y + (dy * 7),
                    "vx": bvx,
                    "vy": bvy,
                    "ttl": 38,
                })
                last_fire_ms = now

        # --- physics ---
        # mild friction to keep it controllable on tiny screen
        ship_vx = (ship_vx * 245) // 256
        ship_vy = (ship_vy * 245) // 256

        ship_x = wrap_fp(ship_x + ship_vx, W)
        ship_y = wrap_fp(ship_y + ship_vy, H)

        # asteroids move
        for a in asteroids:
            a["x"] = wrap_fp(a["x"] + a["vx"], W)
            a["y"] = wrap_fp(a["y"] + a["vy"], H)

        # bullets move / expire
        nb = []
        for b in bullets:
            b["x"] = wrap_fp(b["x"] + b["vx"], W)
            b["y"] = wrap_fp(b["y"] + b["vy"], H)
            b["ttl"] -= 1
            if b["ttl"] > 0:
                nb.append(b)
        bullets = nb

        # --- collisions ---
        ship_px = ship_x // FP
        ship_py = ship_y // FP

        # bullet vs asteroid
        new_asteroids = []
        hit_any = False
        for a in asteroids:
            ax = a["x"] // FP
            ay = a["y"] // FP
            hit = False
            for b in bullets:
                bx = b["x"] // FP
                by = b["y"] // FP
                if dist2(ax, ay, bx, by) <= a["r2"]:
                    b["ttl"] = 0
                    hit = True
                    hit_any = True
                    break
            if hit:
                score += 20 if a["size"] == 3 else (50 if a["size"] == 2 else 100)
                # split
                if a["size"] > 1:
                    for _ in range(2):
                        na = spawn_asteroid(a["size"] - 1, ship_px, ship_py)
                        na["x"] = a["x"]
                        na["y"] = a["y"]
                        # tweak velocities so they diverge
                        na["vx"] += random.randint(-35, 35)
                        na["vy"] += random.randint(-35, 35)
                        new_asteroids.append(na)
            else:
                new_asteroids.append(a)

        # remove dead bullets
        if hit_any:
            bullets = [b for b in bullets if b["ttl"] > 0]

        asteroids = new_asteroids

        # ship vs asteroid (with invuln blink)
        if time.ticks_diff(now, invuln_until) >= 0:
            for a in asteroids:
                ax = a["x"] // FP
                ay = a["y"] // FP
                # ship collision radius about 4px
                if dist2(ax, ay, ship_px, ship_py) <= (a["s"] + 4) * (a["s"] + 4):
                    lives -= 1
                    # quick flash
                    for _ in range(2):
                        oled.invert(1); time.sleep_ms(60)
                        oled.invert(0); time.sleep_ms(60)

                    if lives <= 0:
                        return score, wave

                    # respawn ship centered, clear bullets, give invuln
                    ship_x = (W//2) * FP
                    ship_y = (H//2) * FP
                    ship_vx = 0
                    ship_vy = 0
                    ang = 0
                    bullets = []
                    invuln_until = time.ticks_add(now, 1800)
                    break

        # next wave
        if not asteroids:
            wave += 1
            # short banner
            oled.fill(0)
            oled.text("WAVE", 18, 52, 1)
            oled.text(str(wave), 26, 64, 1)
            oled.show()
            time.sleep(0.6)
            asteroids = spawn_wave(min(6, 2 + wave), ship_x//FP, ship_y//FP)
            invuln_until = time.ticks_add(time.ticks_ms(), 1200)

        # --- draw ---
        oled.fill(0)

        # tiny HUD
        oled.text("L:%d" % lives, 0, 0, 1)
        sc = str(score)
        if len(sc) > 6: sc = sc[-6:]
        oled.text(sc, W - len(sc)*8, 0, 1)
        oled.hline(0, 9, W, 1)

        # asteroids
        for a in asteroids:
            draw_asteroid(a)

        # bullets
        for b in bullets:
            bx = b["x"] // FP
            by = b["y"] // FP
            oled.pixel(bx, by, 1)

        # ship (blink while invulnerable)
        blink = False
        if time.ticks_diff(now, invuln_until) < 0:
            blink = ((now // 120) & 1) == 0
        draw_ship(ship_px, ship_py, ang, blink=blink)

        oled.show()
        time.sleep_ms(30)

def main():
    while True:
        score, wave = play_once()
        wait_for_all_released()
        show_centered_sideways([
            "GAME OVER",
            "SCORE %d" % score,
            "WAVE %d" % wave,
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
