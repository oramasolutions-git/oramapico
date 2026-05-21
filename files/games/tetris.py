from machine import Pin, I2C
import ssd1306
import utime
import sys
import framebuf
import random

# === Configurable ===
SEGMENT_SIZE = 7
GRID_COLS = 128 // SEGMENT_SIZE
GRID_ROWS = 64 // SEGMENT_SIZE

INITIAL_DELAY = 400
DELAY_STEP = 20
MIN_DELAY = 40
speed_delay_interval=50000

# === Display ===
i2c = I2C(0, scl=Pin(21), sda=Pin(20))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# === Buttons ===
btn_left = Pin(17, Pin.IN, Pin.PULL_UP)   # Move forward (down)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)  # Move backward (up)
btn_up = Pin(19, Pin.IN, Pin.PULL_UP)     # Rotate
btn_down = Pin(18, Pin.IN, Pin.PULL_UP)   # Speed up

# === Tetromino Shapes ===
TETROMINOS = [
    [[1, 1, 1, 1]],  # I
    [[1, 1], [1, 1]],  # O
    [[0, 1, 0], [1, 1, 1]],  # T
    [[1, 0, 0], [1, 1, 1]],  # J
    [[0, 0, 1], [1, 1, 1]],  # L
    [[1, 1, 0], [0, 1, 1]],  # S
    [[0, 1, 1], [1, 1, 0]],  # Z
]

def rotate(shape):
    return [list(row) for row in zip(*shape[::-1])]

def draw_block(x, y):
    oled.rect(x, y, SEGMENT_SIZE, SEGMENT_SIZE, 1)

class Block:
    def __init__(self):
        self.shape = random.choice(TETROMINOS)
        self.x = 0
        self.y = GRID_ROWS // 2 - len(self.shape[0]) // 2

    def rotate(self):
        self.shape = rotate(self.shape)

    def get_cells(self):
        return [(self.x + i, self.y + j)
                for i, row in enumerate(self.shape)
                for j, val in enumerate(row) if val]

class Game:
    def __init__(self):
        self.grid = [[0] * GRID_ROWS for _ in range(GRID_COLS)]
        self.block = Block()
        self.level = 0
        self.delay = INITIAL_DELAY
        self.last_tick = utime.ticks_ms()
        self.last_speedup = utime.ticks_ms()
        self.last_rotate_state = 1  # Button not pressed
        self.last_move_time = utime.ticks_ms()
        self.move_delay = 150  # ms between repeated moves
        self.last_left_state = 1
        self.last_right_state = 1
    
    def can_move(self, dx, dy):
        for x, y in self.block.get_cells():
            nx, ny = x + dx, y + dy
            if nx < 0 or nx >= GRID_COLS or ny < 0 or ny >= GRID_ROWS:
                return False
            if self.grid[nx][ny]:
                return False
        return True

    def lock_block(self):
        for x, y in self.block.get_cells():
            self.grid[x][y] = 1
        self.level += 1
        self.block = Block()

    def clear_lines(self):
        lines_to_clear = [i for i in range(GRID_COLS)
                          if all(self.grid[i][j] for j in range(GRID_ROWS))]
        if lines_to_clear:
            self.blast_effect(lines_to_clear)
            for col in lines_to_clear:
                for j in range(GRID_ROWS):
                    self.grid[col][j] = 0
                for i in range(col, 0, -1):
                    self.grid[i] = self.grid[i-1][:]
                self.grid[0] = [0]*GRID_ROWS

    def blast_effect(self, cols):
        for _ in range(3):
            for col in cols:
                for y in range(GRID_ROWS):
                    oled.fill_rect(col * SEGMENT_SIZE, y * SEGMENT_SIZE, SEGMENT_SIZE, SEGMENT_SIZE, 1)
            oled.show()
            utime.sleep(0.05)
            for col in cols:
                for y in range(GRID_ROWS):
                    oled.fill_rect(col * SEGMENT_SIZE, y * SEGMENT_SIZE, SEGMENT_SIZE, SEGMENT_SIZE, 0)
            oled.show()
            utime.sleep(0.05)

    def update(self):
        now = utime.ticks_ms()
        if utime.ticks_diff(now, self.last_speedup) >= speed_delay_interval:
            self.delay = max(MIN_DELAY, self.delay - DELAY_STEP)
            self.last_speedup = now

        current_delay = self.delay
        if not btn_down.value():
            current_delay = 40  # Temporarily speed up
        if utime.ticks_diff(now, self.last_tick) >= current_delay:
            if self.can_move(1, 0):
                self.block.x += 1
            else:
                self.lock_block()
                self.clear_lines()
                if not self.can_move(0, 0):
                    show_game_over(self.level)
                    return
            self.last_tick = now

        now = utime.ticks_ms()

        left_state = btn_left.value()
        right_state = btn_right.value()

# Move Down (LEFT button) - one step per delay
        if self.last_left_state and not left_state:
        # Fresh press
            if self.can_move(0, 1):
                self.block.y += 1
                self.last_move_time = now
        elif not left_state and utime.ticks_diff(now, self.last_move_time) >= self.move_delay:
            if self.can_move(0, 1):
                self.block.y += 1
                self.last_move_time = now

# Move Up (RIGHT button) - one step per delay
        if self.last_right_state and not right_state:
            if self.can_move(0, -1):
                self.block.y -= 1
                self.last_move_time = now
        elif not right_state and utime.ticks_diff(now, self.last_move_time) >= self.move_delay:
            if self.can_move(0, -1):
                self.block.y -= 1
                self.last_move_time = now

        self.last_left_state = left_state
        self.last_right_state = right_state
        
        rotate_state = btn_up.value()
        if self.last_rotate_state and not rotate_state:
            # Button was released then pressed
            self.block.rotate()
            if not self.can_move(0, 0):
        # Undo rotation if not valid
                for _ in range(3):
                    self.block.rotate()
        self.last_rotate_state = rotate_state

    def render(self):
        oled.fill(0)
        # Draw grid
        for x in range(GRID_COLS):
            for y in range(GRID_ROWS):
                if self.grid[x][y]:
                    draw_block(x * SEGMENT_SIZE, y * SEGMENT_SIZE)
        # Draw current block
        for x, y in self.block.get_cells():
            draw_block(x * SEGMENT_SIZE, y * SEGMENT_SIZE)
        oled.show()


def show_game_over(level):
    oled.fill(0)
    oled.text("GAME OVER", 30, 0)
    oled.text("Score: " + str(level), 30, 20)
    oled.text("LEFT to Restart", 5, 40)
    oled.text("UP to menu", 30, 50)
    oled.show()

    while True:
        if not btn_left.value():
            restart_game()
            break
        if not btn_up.value():
            sys.exit()
            break
        utime.sleep(0.1)

def restart_game():
    main()

def main():
    game = Game()
    while True:
        game.update()
        game.render()
        utime.sleep_ms(10)

main()
