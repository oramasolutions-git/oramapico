# Vertical Space Invaders for Raspberry Pi Pico + 0.96" OLED (SSD1306)
from machine import Pin, I2C
import ssd1306
import time
import random  # Make sure this is at the top
import framebuf
import sys

class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-1.5, 1.5)
        self.vy = random.uniform(-1.5, 1.5)
        self.life = random.randint(10, 20)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def is_alive(self):
        return self.life > 0

# === Configurable Parameters ===
enemy_size = 4
enemy_columns = 8
enemy_rows = 5
movement_y = 3  # vertical movement step in pixels
movedown_interval_time = 1500  # ms
next_wave_time = 50  # ms to reduce per wave
reset_movedown_interval_time = movedown_interval_time + next_wave_time # ms


# OLED 128x64, vertical orientation (treated as 64x128)
WIDTH = 64
HEIGHT = 128

# I2C init
i2c = I2C(0, scl=Pin(21), sda=Pin(20))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# Buttons

btn_left = Pin(17, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_up = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down = Pin(18, Pin.IN, Pin.PULL_UP)
# Game variables
ship_x = WIDTH // 2
ship_y = HEIGHT - 8
bullets = []
particles = []
enemies = []
enemy_dir = 1
last_shot_time = 0
last_move_down_time = time.ticks_ms()

level = 0

minimum_movedown_time = 200  # to avoid going too fast
game_over = False



                

        
# Drawing helpers (rotated screen)
def draw_pixel(x, y, color=1):
    oled.pixel(y, 63 - x, color)

def draw_rect(x, y, w, h, color=1):
    for dx in range(w):
        for dy in range(h):
            draw_pixel(x + dx, y + dy, color)

def draw_enemy(x, y):
    # Classic alien design in 5x5 grid
    shape = [
        " 1 1 ",
        "11111",
        "1 1 1",
        " 1 1 ",
        "1   1"
    ]
    for row_idx, row in enumerate(shape):
        for col_idx, pixel in enumerate(row):
            if pixel == "1":
                draw_pixel(x + col_idx, y + row_idx)

def draw_ship():
    # Wings and central body, about 7 pixels wide
    draw_pixel(ship_x + 3, ship_y)           # Nose tip
    draw_pixel(ship_x + 2, ship_y + 1)
    draw_pixel(ship_x + 3, ship_y + 1)
    draw_pixel(ship_x + 4, ship_y + 1)

    draw_pixel(ship_x + 1, ship_y + 2)       # Wings start
    draw_pixel(ship_x + 2, ship_y + 2)
    draw_pixel(ship_x + 3, ship_y + 2)
    draw_pixel(ship_x + 4, ship_y + 2)
    draw_pixel(ship_x + 5, ship_y + 2)

    draw_pixel(ship_x, ship_y + 3)           # Full wings
    draw_pixel(ship_x + 1, ship_y + 3)
    draw_pixel(ship_x + 2, ship_y + 3)
    draw_pixel(ship_x + 3, ship_y + 3)
    draw_pixel(ship_x + 4, ship_y + 3)
    draw_pixel(ship_x + 5, ship_y + 3)
    draw_pixel(ship_x + 6, ship_y + 3)

    draw_pixel(ship_x + 2, ship_y + 4)       # Lower body
    draw_pixel(ship_x + 3, ship_y + 4)
    draw_pixel(ship_x + 4, ship_y + 4)
    
def draw_bullets():
    for b in bullets:
        draw_pixel(b[0], b[1])

def draw_enemies():
    for e in enemies:
        draw_enemy(e[0], e[1])

    
def update_bullets():
    global bullets
    new_bullets = []
    for b in bullets:
        b[1] -= 4
        if b[1] > 0:
            new_bullets.append(b)
    bullets = new_bullets

def check_collisions():
    global bullets, enemies
    new_bullets = []
    for b in bullets:
        hit = False
        for e in enemies:
            if e[0] <= b[0] <= e[0]+enemy_size and e[1] <= b[1] <= e[1]+enemy_size:
                enemies.remove(e)
                
                for _ in range(10):
                    particles.append(Particle(e[0] + enemy_size // 2, e[1] + enemy_size // 2))
                hit = True
                break
        if not hit:
            new_bullets.append(b)
    bullets = new_bullets

def update_enemies():
    global enemy_dir, game_over, last_move_down_time

    now = time.ticks_ms()

    move_down = False
    for e in enemies:
        e[0] += enemy_dir
        if e[0] <= 0 or e[0] >= WIDTH - enemy_size:
            enemy_dir *= -1
            move_down = True
            break  # Only flip direction once

    # Move down on regular interval
    if time.ticks_diff(now, last_move_down_time) >= movedown_interval_time:
        for e in enemies:
            e[1] += movement_y
            if e[1] + enemy_size >= HEIGHT:
                
                    game_over = True
                
                    break
        last_move_down_time = now

def spawn_enemies():
    global enemies, movedown_interval_time
    enemies = []
    spacing_x = (WIDTH - (enemy_columns * 5)) // (enemy_columns + 1)
    spacing_y = 6
    for row in range(enemy_rows):
        for col in range(enemy_columns):
            x = spacing_x + col * (enemy_size + spacing_x)
            y = 10 + row * (enemy_size + spacing_y)
            enemies.append([x, y])
    
    # Increase difficulty
    movedown_interval_time = max(minimum_movedown_time, movedown_interval_time - next_wave_time)

def reset_game():
    global bullets, game_over, last_move_down_time, movedown_interval_time, reset_movedown_interval_time
    bullets = []
    

    movedown_interval_time = reset_movedown_interval_time
    particles.clear()
    spawn_enemies()
    game_over = False
    last_move_down_time = time.ticks_ms()

def show_game_over(level):
    oled.fill(0)
    oled.text("GAME OVER", 30, 0)
    oled.text("Score: " + str(level), 30, 20)
    oled.text("LEFT to Restart", 5, 40)
    oled.text("UP to menu", 30, 50)
    oled.show()
    
    oled.show()
    
    while True:
        
        if not btn_left.value():
            
            reset_game()
            break
        if not btn_up.value():

            sys.exit()
            break
        time.sleep(0.1)

    

    
def update_particles():
    global particles
    new_particles = []
    for p in particles:
        p.update()
        if p.is_alive():
            draw_pixel(int(p.x), int(p.y))
            new_particles.append(p)
    particles = new_particles
    


# === Game Loop ===

while True:


    if game_over:
        
        show_game_over(level)

    # Input
    if not btn_left.value():
        ship_x = max(0, ship_x - 2)
    if not btn_right.value():
        ship_x = min(WIDTH - 7, ship_x + 2)
    if  time.ticks_ms() - last_shot_time > 500:
        bullets.append([ship_x + 3, ship_y])
        last_shot_time = time.ticks_ms()

    # Update
    update_bullets()
    check_collisions()
    update_enemies()
    if not enemies:
        level += 1
        spawn_enemies()

    # Draw
    oled.fill(0)
    update_particles()
    draw_ship()
    draw_bullets()
    draw_enemies()

    
    oled.show()
    time.sleep(0.05)
