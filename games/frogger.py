# frogger_fixed_v3.py - Vertical Frogger for Pico + SH1106 rotated portrait
# Hardware mapping matches your working SH1106 games:
# - I2C(0) on GP21/GP20
# - SH1106 rotate=90 (portrait coordinate space is 64x128)
# - Buttons PULL_UP (active LOW): UP=GP19, DOWN=GP18, RIGHT=GP16, LEFT=GP17
#
# Changes vs v2:
# - Removed SCORE from the in-game HUD (more play space; like your other games)
# - Game Over screen is rendered "sideways" (landscape layout) so text fits nicely
# - Score is shown on Game Over screen

from machine import Pin, I2C
import sh1106
import framebuf
import time
import random
import sys

# ----------------------------
# Hardware init
# ----------------------------
time.sleep(0.3)
i2c = I2C(0, scl=Pin(21), sda=Pin(20))
oled = sh1106.SH1106_I2C(128, 64, i2c, rotate=90)  # portrait coords: 64x128

btn_up    = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down  = Pin(18, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_left  = Pin(17, Pin.IN, Pin.PULL_UP)

# ----------------------------
# Game constants (portrait world)
# ----------------------------
WIDTH  = 64
HEIGHT = 128

TILE = 8
COLS = WIDTH // TILE   # 8
ROWS = HEIGHT // TILE  # 16

FROG_W = 6
FROG_H = 6

ROW_GOALS = 0
ROW_HUD   = 14
ROW_START = 15

GOAL_COLS = [1, 3, 5]  # 3 goals across

MOVE_COOLDOWN_MS = 120

# ----------------------------
# Input helpers
# ----------------------------
class Input:
    def __init__(self):
        self.last_move = time.ticks_ms()

    def read_move(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_move) < MOVE_COOLDOWN_MS:
            return 0, 0

        dx = 0
        dy = 0

        # active-low
        if not btn_up.value():
            dy = -1
        elif not btn_down.value():
            dy = +1
        elif not btn_left.value():
            dx = -1
        elif not btn_right.value():
            dx = +1

        if dx or dy:
            self.last_move = now
        return dx, dy

def wait_for_all_released():
    # active-low: released == 1
    while (not btn_up.value()) or (not btn_down.value()) or (not btn_left.value()) or (not btn_right.value()):
        time.sleep_ms(10)
    time.sleep_ms(60)

# ----------------------------
# Portrait text screens (upright, 8-char lines)
# ----------------------------
def _wrap_to_8_chars(s, max_chars=8):
    s = str(s).replace("\n", " ").strip()
    if len(s) <= max_chars:
        return [s]

    words = s.split(" ")
    out = []
    line = ""
    for w in words:
        if not w:
            continue
        if len(w) > max_chars:
            if line:
                out.append(line)
                line = ""
            for i in range(0, len(w), max_chars):
                out.append(w[i:i+max_chars])
            continue

        trial = w if not line else (line + " " + w)
        if len(trial) <= max_chars:
            line = trial
        else:
            if line:
                out.append(line)
            line = w
    if line:
        out.append(line)
    return out

def show_centered_portrait(lines):
    oled.fill(0)

    wrapped = []
    for t in lines:
        if t == "":
            wrapped.append("")
        else:
            wrapped.extend(_wrap_to_8_chars(t, 8))

    line_h = 10
    total_h = len(wrapped) * line_h - 2
    y = (HEIGHT - total_h) // 2
    if y < 0:
        y = 0

    for t in wrapped:
        x = (WIDTH - (len(t) * 8)) // 2
        if x < 0:
            x = 0
        oled.text(t, x, y, 1)
        y += line_h

    oled.show()

# ----------------------------
# Landscape text screen rendered sideways (128x64 -> rotate into 64x128)
# Use for Game Over so long lines fit (16 chars wide).
# ----------------------------
def show_centered_sideways(lines):
    fb = framebuf.FrameBuffer(bytearray(128 * 64 // 8), 128, 64, framebuf.MONO_HLSB)
    fb.fill(0)

    line_h = 10
    total_h = len(lines) * line_h - 2
    y = (64 - total_h) // 2
    if y < 0:
        y = 0

    for i, t in enumerate(lines):
        t = str(t)
        # 128px width => 16 chars max at 8px each (we'll hard-trim)
        if len(t) > 16:
            t = t[:16]
        x = (128 - len(t) * 8) // 2
        if x < 0:
            x = 0
        fb.text(t, x, y + i * line_h, 1)

    rotated = bytearray(64 * 128 // 8)
    fb_rot = framebuf.FrameBuffer(rotated, 64, 128, framebuf.MONO_HLSB)
    fb_rot.fill(0)

    # Rotate the 128x64 landscape buffer into our 64x128 portrait space
    for xx in range(128):
        for yy in range(64):
            if fb.pixel(xx, yy):
                fb_rot.pixel(63 - yy, xx, 1)

    oled.fill(0)
    oled.blit(fb_rot, 0, 0)
    oled.show()

# ----------------------------
# Optional PBM splash (128x64 P4)
# Rotated into 64x128 for our portrait world.
# ----------------------------
def blit_pbm(filename):
    with open(filename, "rb") as f:
        if f.readline().strip() != b"P4":
            raise ValueError("Not a P4 PBM")

        line = f.readline()
        while line.startswith(b"#"):
            line = f.readline()

        parts = line.split()
        w = int(parts[0]); h = int(parts[1])
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
        blit_pbm("frogger.pbm")
    except Exception:
        show_centered_portrait(["FROGGER", "", "UP: Start", "DOWN: Quit"])

# ----------------------------
# Lane generation
# ----------------------------
def make_lane(ltype, row, dir=1, speed_px=1, period_ms=200,
              obj_min=2, obj_max=3, w_choices=(14, 18, 22),
              gap_min=10, gap_max=18):
    lane = {
        "type": ltype,
        "row": row,
        "dir": dir,
        "speed": speed_px,
        "period": period_ms,
        "last": time.ticks_ms(),
        "objs": []
    }
    if ltype in ("road", "river"):
        x = random.randint(0, 10)
        count = random.randint(obj_min, obj_max)
        for _ in range(count):
            w = random.choice(w_choices)
            lane["objs"].append([x, w])
            x += w + random.randint(gap_min, gap_max)
        lane["objs"].append([x, random.choice(w_choices)])
    return lane

def build_level(level):
    s = 1 + (level // 3)
    s = min(s, 3)

    lanes = {}
    lanes[ROW_GOALS] = make_lane("safe", ROW_GOALS)

    # River (logs)
    lanes[1] = make_lane("river", 1, dir=+1, speed_px=s, period_ms=max(120, 220 - level*6), w_choices=(12, 14, 16), gap_min=12, gap_max=22)
    lanes[2] = make_lane("river", 2, dir=-1, speed_px=s, period_ms=max(110, 210 - level*6), w_choices=(14, 16, 18), gap_min=12, gap_max=22)
    lanes[3] = make_lane("river", 3, dir=+1, speed_px=s, period_ms=max(100, 200 - level*6), w_choices=(12, 14, 18), gap_min=12, gap_max=22)

    lanes[4] = make_lane("safe", 4)

    # Road (cars)
    lanes[5] = make_lane("road", 5, dir=-1, speed_px=s, period_ms=max(115, 210 - level*6), w_choices=(10, 12, 14), gap_min=10, gap_max=18)
    lanes[6] = make_lane("road", 6, dir=+1, speed_px=s, period_ms=max(110, 205 - level*6), w_choices=(12, 14, 16), gap_min=10, gap_max=18)

    lanes[7] = make_lane("safe", 7)

    lanes[8] = make_lane("road", 8, dir=-1, speed_px=s, period_ms=max(105, 200 - level*6), w_choices=(10, 12, 14), gap_min=10, gap_max=18)
    lanes[9] = make_lane("road", 9, dir=+1, speed_px=s, period_ms=max(95,  180 - level*6), w_choices=(12, 14, 16), gap_min=12, gap_max=22)

    lanes[10] = make_lane("safe", 10)

    lanes[11] = make_lane("road", 11, dir=-1, speed_px=s, period_ms=max(105, 200 - level*6), w_choices=(10, 12, 14), gap_min=12, gap_max=22)
    lanes[12] = make_lane("safe", 12)
    lanes[13] = make_lane("road", 13, dir=+1, speed_px=s, period_ms=max(110, 210 - level*6), w_choices=(12, 14, 16), gap_min=12, gap_max=22)

    lanes[ROW_HUD] = make_lane("safe", ROW_HUD)
    lanes[ROW_START] = make_lane("safe", ROW_START)
    return lanes

# ----------------------------
# Helpers / collision
# ----------------------------
def clamp(v, lo, hi):
    if v < lo: return lo
    if v > hi: return hi
    return v

def rects_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return (ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by)

def frog_pixel_pos(frog_col, frog_row):
    x = frog_col * TILE + (TILE - FROG_W) // 2
    y = frog_row * TILE + (TILE - FROG_H) // 2
    return x, y

# ----------------------------
# Drawing
# ----------------------------
def draw_frog(x, y):
    oled.fill_rect(x, y, FROG_W, FROG_H, 1)
    oled.pixel(x + 1, y + 1, 0)
    oled.pixel(x + FROG_W - 2, y + 1, 0)

def draw_game(lanes, frog_col, frog_row, goals_filled, lives):
    oled.fill(0)

    # Goals row underline
    oled.hline(0, TILE - 1, WIDTH, 1)
    for i, gc in enumerate(GOAL_COLS):
        gx = gc * TILE
        oled.rect(gx + 1, 1, TILE - 2, TILE - 2, 1)
        if goals_filled[i]:
            oled.fill_rect(gx + 2, 2, TILE - 4, TILE - 4, 1)

    # Lanes
    for row, lane in lanes.items():
        if row in (ROW_GOALS, ROW_HUD, ROW_START):
            continue

        y = row * TILE

        if lane["type"] == "river":
            for x in range(0, WIDTH, 4):
                oled.pixel(x, y + TILE - 2, 1)

        if lane["type"] in ("road", "river"):
            for ox, ow in lane["objs"]:
                x = int(ox) % (WIDTH + 40) - 40
                if lane["type"] == "road":
                    oled.fill_rect(x, y + 2, ow, TILE - 4, 1)
                else:
                    oled.rect(x, y + 2, ow, TILE - 4, 1)
                    oled.hline(x + 2, y + 4, max(0, ow - 4), 1)

    # HUD line: keep ONLY lives (no score)
    hud_y = ROW_HUD * TILE + 1
    oled.hline(0, hud_y - 1, WIDTH, 1)
    oled.text("L:%d" % lives, 0, hud_y, 1)

    # Frog
    fx, fy = frog_pixel_pos(frog_col, frog_row)
    draw_frog(fx, fy)

    oled.show()

# ----------------------------
# Gameplay logic
# ----------------------------
def reset_frog():
    return (COLS // 2, ROW_START)

def frog_die_anim():
    for _ in range(2):
        oled.invert(1)
        time.sleep_ms(80)
        oled.invert(0)
        time.sleep_ms(80)

def _find_log_under_frog(river_lane, frog_col):
    frog_center = frog_col * TILE + TILE // 2
    for ox, ow in river_lane["objs"]:
        x = int(ox) % (WIDTH + 40) - 40
        left = x
        right = x + ow
        if frog_center >= left and frog_center <= right:
            return (left, right)
    return None

def move_lanes(lanes, frog_col, frog_row):
    """
    Returns (carry_dx_px, drowned, log_bounds)
    log_bounds is (left,right) for the log the frog is currently on (if on a river row).
    """
    drowned = False
    carry_dx = 0
    log_bounds = None

    # Advance due lanes
    for row, lane in lanes.items():
        if lane["type"] not in ("road", "river"):
            continue

        now = time.ticks_ms()
        if time.ticks_diff(now, lane["last"]) < lane["period"]:
            continue

        lane["last"] = now
        for obj in lane["objs"]:
            obj[0] += lane["dir"] * lane["speed"]

        if lane["type"] == "river" and row == frog_row:
            carry_dx = lane["dir"] * lane["speed"]

    # Evaluate log overlap every tick
    lane = lanes.get(frog_row)
    if lane and lane["type"] == "river":
        log_bounds = _find_log_under_frog(lane, frog_col)
        if not log_bounds:
            drowned = True

    return carry_dx, drowned, log_bounds

def check_road_collision(lane, frog_col, frog_row):
    fx, fy = frog_pixel_pos(frog_col, frog_row)
    y = frog_row * TILE
    for ox, ow in lane["objs"]:
        x = int(ox) % (WIDTH + 40) - 40
        if rects_overlap(fx, fy, FROG_W, FROG_H, x, y + 2, ow, TILE - 4):
            return True
    return False

# ----------------------------
# One run (returns True to restart)
# ----------------------------
def play_once():
    wait_for_all_released()
    show_splash()
    wait_for_all_released()

    # Title input
    while True:
        if not btn_up.value():
            time.sleep_ms(180)
            break
        if not btn_down.value():
            time.sleep_ms(180)
            sys.exit()
        time.sleep_ms(20)

    level = 1
    score = 0
    lives = 3

    lanes = build_level(level)
    frog_col, frog_row = reset_frog()
    best_row = frog_row
    goals_filled = [False, False, False]
    inp = Input()

    show_centered_portrait(["LEVEL %d" % level, "", "GET READY"])
    time.sleep(0.8)

    while True:
        carry_dx_px, drowned, log_bounds = move_lanes(lanes, frog_col, frog_row)

        if drowned:
            lives -= 1
            frog_die_anim()
            if lives <= 0:
                break
            frog_col, frog_row = reset_frog()
            best_row = frog_row
            continue

        # Sticky log carry: clamp frog center inside the log (and apply carry if row advanced this tick)
        lane_here = lanes.get(frog_row)
        if lane_here and lane_here["type"] == "river" and log_bounds:
            left, right = log_bounds
            frog_center = frog_col * TILE + TILE // 2
            frog_center += carry_dx_px

            margin = 2
            if frog_center < left + margin:
                frog_center = left + margin
            if frog_center > right - margin:
                frog_center = right - margin

            frog_col = clamp(int(frog_center // TILE), 0, COLS - 1)

        # Input
        dx, dy = inp.read_move()
        if dx or dy:
            frog_col = clamp(frog_col + dx, 0, COLS - 1)
            frog_row = clamp(frog_row + dy, 0, ROW_START)
            if frog_row < best_row:
                score += 10
                best_row = frog_row

        # Goal row
        if frog_row == ROW_GOALS:
            if frog_col in GOAL_COLS:
                idx = GOAL_COLS.index(frog_col)
                if not goals_filled[idx]:
                    goals_filled[idx] = True
                    score += 200
                    frog_col, frog_row = reset_frog()
                    best_row = frog_row

                    if all(goals_filled):
                        level += 1
                        goals_filled = [False, False, False]
                        lanes = build_level(level)
                        show_centered_portrait(["LEVEL %d" % level, "", "GET READY"])
                        time.sleep(0.8)
                else:
                    lives -= 1
                    frog_die_anim()
                    if lives <= 0:
                        break
                    frog_col, frog_row = reset_frog()
                    best_row = frog_row
            else:
                lives -= 1
                frog_die_anim()
                if lives <= 0:
                    break
                frog_col, frog_row = reset_frog()
                best_row = frog_row

        # Road collision checks
        lane = lanes.get(frog_row)
        if lane and lane["type"] == "road":
            if check_road_collision(lane, frog_col, frog_row):
                lives -= 1
                frog_die_anim()
                if lives <= 0:
                    break
                frog_col, frog_row = reset_frog()
                best_row = frog_row

        draw_game(lanes, frog_col, frog_row, goals_filled, lives)
        time.sleep_ms(20)

    # Game over: sideways so longer text fits
    show_centered_sideways([
        "GAME OVER",
        "SCORE %d" % score,
        "",
        "UP: RETRY",
        "DOWN: QUIT"
    ])
    wait_for_all_released()
    while True:
        if not btn_up.value():
            time.sleep_ms(180)
            return True
        if not btn_down.value():
            time.sleep_ms(180)
            sys.exit()
        time.sleep_ms(20)

# ----------------------------
# Auto-run like your other games
# ----------------------------
while True:
    play_once()
