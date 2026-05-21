# ssd1306.py
import framebuf

class SSD1306:
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.width * self.pages)
        self.framebuf = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.poweron()
        self.init_display()

    def init_display(self):
        for cmd in (
            0xae, 0xa4, 0xd5, 0xf0, 0xa8, 0x3f, 0xd3, 0x00, 0x40,
            0x8d, 0x14, 0x20, 0x00, 0xa1, 0xc8, 0xda, 0x12, 0x81,
            0xcf, 0xd9, 0xf1, 0xdb, 0x40, 0xa6, 0xaf):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweron(self):
        pass

    def poweroff(self):
        self.write_cmd(0xae)

    def contrast(self, contrast):
        self.write_cmd(0x81)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(0xa7 if invert else 0xa6)

    def show(self):
        for page in range(0, self.height // 8):
            self.write_cmd(0xb0 | page)
            self.write_cmd(0x02)
            self.write_cmd(0x10)
            start = self.width * page
            end = start + self.width
            self.write_data(self.buffer[start:end])

    def fill(self, col):
        self.framebuf.fill(col)

    def pixel(self, x, y, col):
        self.framebuf.pixel(x, y, col)

    def scroll(self, dx, dy):
        self.framebuf.scroll(dx, dy)

    def text(self, string, x, y, col=1):
        self.framebuf.text(string, x, y, col)

    def rect(self, x, y, w, h, col):
        self.framebuf.rect(x, y, w, h, col)

    def fill_rect(self, x, y, w, h, col):
        self.framebuf.fill_rect(x, y, w, h, col)

    def blit(self, fbuf, x, y):
        self.framebuf.blit(fbuf, x, y)

class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3c, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        self.i2c.writeto(self.addr, b'\x40' + buf)
