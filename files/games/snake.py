from machine import Pin, I2C, Timer
import ssd1306
import time
import urandom
import sys


# Initialize I2C and OLED
i2c = I2C(0, scl=Pin(21), sda=Pin(20))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# Button setup
btn_left = Pin(17, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_up = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down = Pin(18, Pin.IN, Pin.PULL_UP)

# Constants
WIDTH, HEIGHT = 128, 64
GRID_SIZE = 5
COLS = (WIDTH // GRID_SIZE)  # Now COLS = 31
ROWS = HEIGHT // GRID_SIZE
# --- Speed parameters -------------------------------------------------------
INITIAL_DELAY   = 0.15   # starting “tick” length  (seconds)
DELAY_STEP      = 0.005   # how much to shave off after every apple
MIN_DELAY       = 0.04   # don’t let it get faster than this
# ---------------------------------------------------------------------------
# Snake state
start_x = COLS // 2
start_y = ROWS // 2
snake = [(start_x, start_y), (start_x - 1, start_y), (start_x - 2, start_y)]
direction = (1, 0)  # initially moving right
food = (urandom.getrandbits(5) % COLS, urandom.getrandbits(5) % ROWS)
game_over = False

def draw_circle(x0, y0, r):
    for y in range(-r, r+1):
        for x in range(-r, r+1):
            if x*x + y*y <= r*r:
                oled.pixel(x0 + x, y0 + y, 1)
apple_bitmap = [
    "00110",
    "01111",
    "11111",
    "01111",
    "00110",
]

def draw_apple(x, y):
    # Convert grid coords to pixel coords with left offset
    px = x * GRID_SIZE
    py = y * GRID_SIZE

    for j, row in enumerate(apple_bitmap):
        for i, pixel in enumerate(row):
            if pixel == "1":
                # Bounds check just in case
                if 0 <= px + i < WIDTH and 0 <= py + j < HEIGHT:
                    oled.pixel(px + i, py + j, 1)
def draw_snake():
    for i, segment in enumerate(snake):
        x, y = segment
        px, py = x * GRID_SIZE, y * GRID_SIZE

        if i == 0:
            # Head with eyes
            oled.fill_rect(px, py, GRID_SIZE, GRID_SIZE, 1)
            oled.pixel(px + 1, py + 1, 0)  # Left eye
            oled.pixel(px + 2, py + 1, 0)  # Right eye
        elif i == len(snake) - 1:
            # Tail - round or dot
            draw_circle(px + GRID_SIZE // 2, py + GRID_SIZE // 2, GRID_SIZE // 2 - 1)
        else:
            # Body
            if i % 2 == 0:
                oled.fill_rect(px, py, GRID_SIZE, GRID_SIZE, 1)
            else:
                oled.rect(px, py, GRID_SIZE, GRID_SIZE, 1)

def wrap(pos):
    x, y = pos
    return (x % COLS, y % ROWS)

def update_snake():
    global food, game_over, step_delay
    head_x, head_y = snake[0]
    dx, dy = direction
    new_head = wrap((head_x + dx, head_y + dy))

    if new_head in snake:
        game_over = True
        return

    snake.insert(0, new_head)

    # ‑‑‑ Check for apple ‑‑‑
    if new_head == food:
        # place new apple at a free spot
        while True:
            food = (urandom.getrandbits(5) % COLS, urandom.getrandbits(5) % ROWS)
            if food not in snake:
                break

        # speed‑up
        step_delay = max(MIN_DELAY, step_delay - DELAY_STEP)
    else:
        snake.pop()

def check_buttons():
    global direction
    if not btn_right.value() and direction != (0, 1):
        direction = (0, -1)
    elif not btn_left.value() and direction != (0, -1):
        direction = (0, 1)
    elif not btn_down.value() and direction != (-1, 0):
        direction = (1, 0)
    elif not btn_up.value() and direction != (1, 0):
        direction = (-1, 0)
def draw():
    oled.fill(0)
    draw_snake()
    fx, fy = food
    draw_apple(fx, fy)
    oled.show()
def show_game_over(level):
    oled.fill(0)
    oled.text("GAME OVER", 30, 0)
    oled.text("Score: " + str(level), 30, 20)
    oled.text("LEFT to Restart", 5, 40)
    oled.text("UP to menu", 30, 50)
    oled.show()

    # Wait until down button is pressed
    while True:
        if not btn_left.value():
            restart_game()
            break

        if not btn_up.value():

            sys.exit()
            break

        time.sleep(0.1)


def restart_game():
    global snake, direction, food, game_over, step_delay

    start_x = COLS // 2
    start_y = ROWS // 2
    snake   = [(start_x, start_y), (start_x - 1, start_y), (start_x - 2, start_y)]
    direction = (1, 0)
    food      = (urandom.getrandbits(5) % COLS, urandom.getrandbits(5) % ROWS)
    game_over = False

    step_delay = INITIAL_DELAY        # <<< new line



# Main game loop (infinite restarts)
while True:
    restart_game()

    while not game_over:
        check_buttons()
        update_snake()
        draw()
        time.sleep(step_delay)

    show_game_over(len(snake) - 3)

