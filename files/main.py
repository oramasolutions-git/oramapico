from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
import framebuf
import time
import os
import sys

# Setup I2C display
i2c = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
display = SSD1306_I2C(128, 64, i2c)

# Buttons
btn_left = Pin(17, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_up = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down = Pin(18, Pin.IN, Pin.PULL_UP)

# Scan for games (expecting .pbm and .py pairs)
games_folder = 'games'
game_files = [f[:-4] for f in os.listdir(games_folder) if f.endswith('.pbm')]
game_files.sort()
current_game = 0

def load_and_display_image(name):
    path = f"{games_folder}/{name}.pbm"
    try:
        with open(path, 'rb') as f:
            f.readline()  # P4
            f.readline()  # comment
            f.readline()  # dimensions
            data = bytearray(f.read())
        fbuf = framebuf.FrameBuffer(data, 128, 64, framebuf.MONO_HLSB)
        display.fill(0)
        display.blit(fbuf, 0, 0)
        display.show()
    except Exception as e:
        display.fill(0)
        display.text("Error loading", 0, 0)
        display.text(name, 0, 10)
        display.show()
        print("Failed to load image:", e)

def launch_game(name):
    game_path = f"{games_folder}.{name}"
    try:
        __import__(game_path)
    except Exception as e:
        display.fill(0)
        display.text("Error running", 0, 0)
        display.text(name, 0, 10)
        display.show()
        print("Game crash:", e)
    finally:
        # After game ends, go back to menu
        time.sleep(2)
        display.fill(0)
        display.show()
def show_logo():
    try:
        with open('logo.pbm', 'rb') as f:
            f.readline()  # P4
            f.readline()  # Comment
            f.readline()  # Dimensions
            data = bytearray(f.read())
        fbuf = framebuf.FrameBuffer(data, 128, 64, framebuf.MONO_HLSB)
        display.fill(0)
        display.blit(fbuf, 0, 0)
        display.show()
        time.sleep(2)  # Wait 1 second before proceeding
    except Exception as e:
        display.fill(0)
        display.text("Logo load error", 0, 0)
        display.show()
        print("Error loading logo:", e)
        time.sleep(1)

# Call once at the start of your program
show_logo()
# Initial display
load_and_display_image(game_files[current_game])

while True:
    if not btn_right.value():
        current_game = (current_game + 1) % len(game_files)
        load_and_display_image(game_files[current_game])
        time.sleep(0.2)

    if not btn_left.value():
        current_game = (current_game - 1) % len(game_files)
        load_and_display_image(game_files[current_game])
        time.sleep(0.2)

    if not btn_up.value() or not btn_down.value():
        # Clear memory
        display.fill(0)
        display.text("Starting game...", 0, 0)
        display.show()
        time.sleep(0.5)
        launch_game(game_files[current_game])
        # Re-display menu after game exits
        load_and_display_image(game_files[current_game])
        time.sleep(0.2)
