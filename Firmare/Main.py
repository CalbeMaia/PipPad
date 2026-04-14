# ============================================================
#  PipPad Firmware  —  CircuitPython 9.x
#  MCU : Seeed XIAO RP2040
#
#  Matrix  : 3 rows × 3 cols  (SW1-SW9)
#  Encoder : EC11 rotary + push-switch  (SW10)
#  Connector: J1  (spare GPIO6 / GPIO7 — e.g. I2C OLED)
#
#  GPIO map
#  --------
#  COL1 = GP26   COL2 = GP27   COL3 = GP28
#  ROW1 = GP29   ROW2 = GP0    ROW3 = GP1
#  ENC_A = GP2   ENC_B = GP4   ENC_SW = GP3
#  J1_SDA= GP6   J1_SCL= GP7   (free for OLED/I2C)
#
#  Layout (top-down view)
#  ┌─────┬─────┬─────┐
#  │ SW1 │ SW2 │ SW3 │  Row 1
#  ├─────┼─────┼─────┤
#  │ SW4 │ SW5 │ SW6 │  Row 2
#  ├─────┼─────┼─────┤
#  │ SW7 │ SW8 │ SW9 │  Row 3
#  └─────┴─────┴─────┘
#  [ SW10 encoder knob — below grid ]
#
#  Required libraries (copy to /lib on CIRCUITPY):
#    adafruit_hid
#    adafruit_debouncer
# ============================================================

import board
import busio
import digitalio
import rotaryio
import usb_hid
import time

from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode
from adafruit_debouncer import Debouncer

# ── HID devices ─────────────────────────────────────────────
kbd = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(kbd)
cc = ConsumerControl(usb_hid.devices)

# ── Matrix pin definitions ───────────────────────────────────
COL_PINS = (board.D0, board.D1, board.D2)   # GP26, GP27, GP28
ROW_PINS = (board.D3, board.D6, board.D7)   # GP29, GP0,  GP1

# Columns are driven LOW one at a time (output).
cols = []
for pin in COL_PINS:
    p = digitalio.DigitalInOut(pin)
    p.direction = digitalio.Direction.OUTPUT
    p.value = True          # idle HIGH
    cols.append(p)

# Rows are read with internal pull-ups (input).
rows = []
for pin in ROW_PINS:
    p = digitalio.DigitalInOut(pin)
    p.direction = digitalio.Direction.INPUT
    p.pull = digitalio.Pull.UP
    rows.append(p)

# ── Rotary encoder ───────────────────────────────────────────
encoder = rotaryio.IncrementalEncoder(board.D8, board.D9)   # GP2, GP4
# Note: rotaryio.IncrementalEncoder takes (phase_a, phase_b)
# Map board.D8 = GP2 = ENC_A, board.D9 = GP4 = ENC_B

enc_sw_pin = digitalio.DigitalInOut(board.D10)  # GP3
enc_sw_pin.direction = digitalio.Direction.INPUT
enc_sw_pin.pull = digitalio.Pull.UP
enc_sw = Debouncer(enc_sw_pin)

last_enc_position = encoder.position

# ── Key map ──────────────────────────────────────────────────
# key_map[row][col] — one tuple per key.
# Each tuple is either:
#   ("key",  Keycode.X, ...)          — regular keystroke(s)
#   ("cc",   ConsumerControlCode.X)   — media / consumer key
#   ("macro", string)                 — types a string via layout
#
# Customise to taste!

key_map = [
    # Row 1           Col 1                       Col 2                        Col 3
    [("key",  Keycode.F13),             ("key",  Keycode.F14),             ("key",  Keycode.F15)],
    # Row 2
    [("key",  Keycode.F16),             ("key",  Keycode.F17),             ("key",  Keycode.F18)],
    # Row 3
    [("key",  Keycode.F19),             ("key",  Keycode.F20),             ("key",  Keycode.F21)],
]

# Encoder push action
enc_push_action = ("cc", ConsumerControlCode.MUTE)

# Encoder rotation actions
enc_cw_action  = ("cc", ConsumerControlCode.VOLUME_INCREMENT)
enc_ccw_action = ("cc", ConsumerControlCode.VOLUME_DECREMENT)

# ── Action dispatcher ────────────────────────────────────────
def do_action(action):
    kind = action[0]
    if kind == "key":
        kbd.press(*action[1:])
        kbd.release_all()
    elif kind == "cc":
        cc.send(action[1])
    elif kind == "macro":
        layout.write(action[1])

# ── Matrix state tracking ────────────────────────────────────
NUM_ROWS = len(rows)
NUM_COLS = len(cols)
prev_state = [[False] * NUM_COLS for _ in range(NUM_ROWS)]

def scan_matrix():
    """Return current key state as list-of-lists of bools (True = pressed)."""
    state = [[False] * NUM_COLS for _ in range(NUM_ROWS)]
    for c, col in enumerate(cols):
        col.value = False                   # drive column LOW
        time.sleep(0.001)                   # settle
        for r, row in enumerate(rows):
            state[r][c] = not row.value     # LOW when pressed (pull-up)
        col.value = True                    # release column
    return state

# ── Main loop ────────────────────────────────────────────────
print("PipPad ready!")

while True:
    # --- Matrix scan ----------------------------------------
    cur_state = scan_matrix()
    for r in range(NUM_ROWS):
        for c in range(NUM_COLS):
            was = prev_state[r][c]
            now = cur_state[r][c]
            if now and not was:             # key just pressed
                do_action(key_map[r][c])
    prev_state = cur_state

    # --- Encoder rotation -----------------------------------
    pos = encoder.position
    delta = pos - last_enc_position
    if delta > 0:
        for _ in range(delta):
            do_action(enc_cw_action)
    elif delta < 0:
        for _ in range(-delta):
            do_action(enc_ccw_action)
    last_enc_position = pos

    # --- Encoder push switch --------------------------------
    enc_sw.update()
    if enc_sw.fell:                         # button pressed
        do_action(enc_push_action)

    time.sleep(0.002)                       # ~500 Hz poll rate
