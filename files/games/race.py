from machine import Pin, I2C
import ssd1306
import utime
import urandom
import time
import sys

# --- OLED setup ---
i2c = I2C(0, scl=Pin(21), sda=Pin(20))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# --- Button setup (vertical hold) ---
btn_left = Pin(17, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_up = Pin(19, Pin.IN, Pin.PULL_UP)     # Move up
btn_down = Pin(18, Pin.IN, Pin.PULL_UP)   # Move down

# --- Player car setup ---
player_y = 28  # Vertical center
player_x = 118  # Car starts on right side
player_w = 5
player_h = 7
level=0
# --- Obstacles ---
obstacles = []
base_speed = 2
spawn_timer = 0
spawn_interval = 20
maxspeed = 1
max_maxspeed = 10  # Optional: don't go above this
min_spawn_interval = 5
last_decrease_time = utime.ticks_ms()  # track time in milliseconds

# --- Lane border ---
lane_thickness = 2
game_over = False

# --- Car drawing (simple top-down view) ---
def draw_car(x, y):
    # Body
    oled.fill_rect(x, y + 2, player_w, 3, 1)
    # Wheels
    oled.pixel(x, y, 1)
    oled.pixel(x + player_w - 1, y, 1)
    oled.pixel(x, y + 6, 1)
    oled.pixel(x + player_w - 1, y + 6, 1)

# --- Obstacle drawing ---
def draw_obstacle_car(x, y):
    # Car body
    oled.fill_rect(x, y + 2, 5, 3, 1)
    # Wheels
    oled.pixel(x, y, 1)
    oled.pixel(x + 4, y, 1)
    oled.pixel(x, y + 6, 1)
    oled.pixel(x + 4, y + 6, 1)



def draw_obstacles():
    for obs in obstacles:

            draw_obstacle_car(obs['x'], obs['y'])


def update_obstacles():
    global game_over
    for obs in obstacles:
        obs['x'] += obs['speed']  # Use per-obstacle speed
        # Collision detection
        if (player_x < obs['x'] + obs['w'] and player_x + player_w > obs['x']):
            if (player_y < obs['y'] + obs['h'] and player_y + player_h > obs['y']):
                game_over = True

    # Remove obstacles that went off-screen
    obstacles[:] = [obs for obs in obstacles if obs['x'] < 120]

def spawn_obstacle():
    
    y = urandom.getrandbits(6) % (64 - lane_thickness*2 - 10) + lane_thickness
    w, h = 5, 7
    
    # Random speed with a base that increases every 30 levels
     
    random_variation = urandom.getrandbits(4) % maxspeed 
    speed = base_speed + random_variation

    obstacles.append({'x': 0, 'y': y, 'w': w, 'h': h, 'speed': speed})
def draw_lanes():
    oled.fill_rect(0, 0, 125, lane_thickness, 1)  # Top lane
    oled.fill_rect(0, 64 - lane_thickness, 125, lane_thickness, 1)  # Bottom lane

def show_game_over(level):
    oled.fill(0)
    oled.text("GAME OVER", 30, 0)
    oled.text("Score: " + str(level), 30, 20)
    oled.text("LEFT to Restart", 5, 40)
    oled.text("UP to Menu", 30, 50)
    oled.show()

    while True:
        if not btn_left.value():  # Restart
            reset_game()
            break
        if not btn_up.value():  # Exit
            sys.exit()
        time.sleep(0.1)
def reset_game():
    global level, game_over, player_y, obstacles, spawn_timer, maxspeed
    level = 0
    game_over = False
    player_y = 28  # Reset to vertical center
    obstacles.clear()
    spawn_timer = 0
    maxspeed=1
    oled.fill(0)
    oled.show()

# --- Main loop ---
while True:
    if game_over:
        show_game_over(level)
        

    oled.fill(0)
    draw_lanes()

    # Movement input
    if not btn_right.value() and player_y > lane_thickness:
        player_y -= 2
    if not btn_left.value() and player_y < (64 - lane_thickness - player_h):
        player_y += 2

    # Obstacles
    update_obstacles()
    spawn_timer += 1
    if spawn_timer >= spawn_interval:
        level +=1
        spawn_obstacle()
        spawn_timer = 0

    # Drawing
    draw_car(player_x, player_y)
    draw_obstacles()
    oled.show()
    current_time = utime.ticks_ms()
    if utime.ticks_diff(current_time, last_decrease_time) >= 60000:  # 60,000 ms = 60 sec
        if spawn_interval > min_spawn_interval:
            spawn_interval -= 1
        if maxspeed < max_maxspeed:  # Optional cap
            maxspeed += 1
        last_decrease_time = current_time

    # reset timer
    utime.sleep_ms(50)
