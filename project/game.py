"""SUSPICION - a turn-based mystery for the terminal (80 x 24).

Act 1: search the bedroom before your partner gets home.
Act 2: confront them with what you found, then accuse them or let it go.

Run:  python3 game.py      (Python standard library only)
Art:  every picture is a PNG in the art folder, redraw them in Pixilart.
"""
import os, sys, tty, termios, shutil, struct, zlib, random, textwrap

WIDTH, HEIGHT = 80, 24
ART_W, ART_H = WIDTH, (HEIGHT - 2) * 2   # 80 x 44 pixels, 2 text rows below

# "truecolor" = exact colours, "256" = closest of 256 colours (works everywhere).
# Change to "truecolor" by hand if your terminal supports it.
COLOR_MODE = "truecolor" if os.environ.get("COLORTERM") in ("truecolor", "24bit") else "256"

RESET, CLEAR = "\x1b[0m", "\x1b[H\x1b[2J"
HIDE_CURSOR, SHOW_CURSOR = "\x1b[?25l", "\x1b[?25h"

# ---------------------------------------------------------------- art
# Each art is a list of strings, one character per pixel.
# Each character is looked up in a palette dict that maps it to (R, G, B).
# In a sprite, "." means transparent (the background shows through).

MENU_PALETTE = {
    "N": (24, 28, 58),     # night background
    "*": (200, 200, 255),  # star
    "Y": (255, 214, 64),   # face
    "y": (214, 140, 30),   # face outline
    "h": (255, 245, 170),  # shine
    "E": (40, 30, 30),     # eyes and mouth
    "e": (255, 255, 255),  # eye sparkle
    "B": (255, 140, 140),  # blush
}

SMILEY = [
    ".............yyyy.............",
    ".........yyyyyyyyyyyy.........",
    ".......yyyYYYYYYYYYYyyy.......",
    "......yyYYYYYYYYYYYYYYyy......",
    ".....yyhhhYYYYYYYYYYYYYyy.....",
    "....yyhhhhhYYYYYYYYYYYYYyy....",
    "...yyYhhhhhYYYYYYYYYYYYYYyy...",
    "..yyYYhhhhhYYYYYYYYYYYYYYYyy..",
    "..yYYYYhheEEYYYYYYeEEYYYYYYy..",
    ".yyYYYYYYEEEYYYYYYEEEYYYYYYyy.",
    ".yYYYYYYYEEEYYYYYYEEEYYYYYYYy.",
    ".yYYYYYYYEEEYYYYYYEEEYYYYYYYy.",
    ".yYYYYYYYEEEYYYYYYEEEYYYYYYYy.",
    "yyYYYYYYYYYYYYYYYYYYYYYYYYYYyy",
    "yyYYYYYYYYYYYYYYYYYYYYYYYYYYyy",
    "yyYYYYYYYYYYYYYYYYYYYYYYYYYYyy",
    "yyYYYYYYYYYYYYYYYYYYYYYYYYYYyy",
    ".yYYYBBBYYYYYYYYYYYYYYBBBYYYy.",
    ".yYYYBBBYYYYYYYYYYYYYYBBBYYYy.",
    ".yYYYYYYYYYYYYYYYYYYYYYYYYYYy.",
    ".yyYYYYYYYYYYYYYYYYYYYYYYYYyy.",
    "..yYYYYYYYYYYYYYYYYYYYYYYYYy..",
    "..yyYYYEEYYYYYYYYYYYYEEYYYyy..",
    "...yyYYEEEEYYYYYYYYEEEEYYyy...",
    "....yyYYYEEEEEEEEEEEEYYYyy....",
    ".....yyYYYYYYEEEEYYYYYYyy.....",
    "......yyYYYYYYYYYYYYYYyy......",
    ".......yyyYYYYYYYYYYyyy.......",
    ".........yyyyyyyyyyyy.........",
    ".............yyyy.............",
]

ROOM_PALETTE = {
    "W": (196, 160, 120),  # wallpaper
    "w": (180, 142, 104),  # wallpaper stripe
    "b": (92, 60, 40),     # skirting board
    "F": (150, 98, 58),    # floor planks
    "f": (118, 74, 42),    # plank gaps
    "K": (238, 232, 220),  # window frame
    "S": (34, 46, 96),     # night sky
    "s": (255, 255, 210),  # stars
    "M": (245, 240, 200),  # moon
    "C": (168, 44, 52),    # curtain
    "c": (128, 30, 40),    # curtain fold
    "G": (212, 170, 60),   # gold picture frame
    "A": (140, 200, 236),  # painting sky
    "Y": (255, 220, 80),   # painting sun
    "H": (90, 160, 80),    # painting hill
    "h": (60, 120, 60),    # painting grass
    "L": (255, 230, 150),  # lamp shade
    "l": (220, 180, 90),   # lamp shade edge
    "P": (60, 60, 64),     # metal (lamp pole, curtain rod)
    "O": (64, 104, 150),   # sofa
    "o": (44, 76, 116),    # sofa shadow
    "U": (84, 128, 176),   # seat cushions
    "u": (100, 146, 192),  # back cushions
    "T": (110, 70, 40),    # coffee table top
    "t": (70, 44, 26),     # table/sofa legs
    "R": (150, 60, 70),    # rug
    "r": (220, 180, 120),  # rug pattern
    "D": (130, 86, 50),    # cabinet
    "d": (96, 62, 36),     # cabinet shadow
    "k": (230, 200, 90),   # knobs, book spine
    "n": (250, 250, 245),  # book pages
    "V": (70, 150, 70),    # plant leaves, mug
    "v": (170, 90, 60),    # plant pot
}

LIVING_ROOM = [
    "wWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwW",
    "wWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwW",
    "wWWCCCPPPPPPPPPPPPPPPPCCCWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwW",
    "wWWCcCKKKKKKKKKKKKKKKKCcCWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwW",
    "wWWCcCSSSSSSSKKSSSSSSSCcCWWWWWwWWGGGGGGGGGGGGGGGwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwW",
    "wWWCcCSsSSSSSKKSSSSSSSCcCWWWWWwWWGAAAAAAAAAAAAAGwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwW",
    "wWWCcCSSSSSSSKKSSsSSSSCcCWWWWWwWWGAAAAAAAAAYYAAGwWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwW",
    "wWWCcCSSSSSSSKKSSSSSSSCcCWWWWWwWWGAAAAAAAAAYYAAGwWWWWWwWlllllllWWWwWWWWWwWWWWWwW",
    "wWWCcCSSSSsSSKKSSSSSSSCcCWWWWWwWWGHHAAAAAAAHHHHGwWWWWWwLLLLLLLLLWWwWWWWWwWWWWWwW",
    "wWWCcCSSSSSSSKKSSSSsSSCcCWWWWWwWWGHHHHAAAHHHHHHGwWWWWWwLLLLLLLLLWWwWWWWVwWWWWWwW",
    "wWWCcCSSSSSSSKKSSSSSSSCcCWWWWWwWWGHHHHHHHHHHHHHGwWWWWWwLLLLLLLLLWWwWVVVVVVVWWWwW",
    "wWWCcCKKKKKKKKKKKKKKKKCcCWWWWWwWWGHHHHHHHHHHHHHGwWWWWWwLLLLLLLLLWWwWVVVVVVVVWWwW",
    "wWWCcCSSSSSSSKKSSSSSSSCcCWWWWWwWWGhhhhhhhhhhhhhGwWWWWWlllllllllllWwVVVVVVVVWWWwW",
    "wWWCcCSSSSSSSKKSSSMMsSCcCWWWWWwWWGhhhhhhhhhhhhhGwWWWWWwWWWWPwWWWWWwWVVVVVVVWWWwW",
    "wWWCcCSSsSSSSKKSSMMMSSCcCWWWWWwWWGGGGGGGGGGGGGGGwWWWWWwWWWWPwWWWWWwWWvvvvvWWWWwW",
    "wWWCcCSSSSSSSKKSsMMMSSCcCWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWWwWWvvvvvWWWWwW",
    "wWWCcCSSSSSsSKKSSSSSSSCcCWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWWwWWvvvvvWWWWwW",
    "wWWCcCSSSSSSSKKSSSSSSSCcCWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWdddddddddddddwW",
    "wWWCcCSSSSSSSKKSSSSSSSCcCWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDDDDDDDDDDDDDwW",
    "wWWCcCKKKKKKKKKKKKKKKKCcCWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDdddddddddddDwW",
    "wWWCcCwWWWWWwWWWWWwWWWCcCWWWWWwWWWWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDdDDDDDDDDDdDwW",
    "wWWCcCwOOOOOOOOOOOOOOOOOOOOOOOOOWWWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDdDDDDkDDDDdDwW",
    "wWWWWWwOOOuuuuuuuuuOuuuuuuuuuOOOWWWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDdDDDDDDDDDdDwW",
    "wWWWWWwOOOuuuuuuuuuOuuuuuuuuuOOOWWWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDdddddddddddDwW",
    "wWWWWWwOOOuuuuuuuuuOuuuuuuuuuOOOWWWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDDDDDDDDDDDDDwW",
    "wWWWWooooOuuuuuuuuuOuuuuuuuuuOooooWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDdddddddddddDwW",
    "wWWWWooooOuuuuuuuuuOuuuuuuuuuOooooWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDdDDDDDDDDDdDwW",
    "wWWWWooooUUUUUUUUUUoUUUUUUUUUUooooWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDdDDDDkDDDDdDwW",
    "wWWWWooooUUUUUUUUUUoUUUUUUUUUUooooWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDdDDDDDDDDDdDwW",
    "wWWWWooooUUUUUUUUUUoUUUUUUUUUUooooWWwWWWWWwWWWWWwWWWWWwWWWWPwWWWWDdddddddddddDwW",
    "bbbbbooooUUUUUUUUUUoUUUUUUUUUUoooobbbbbVbbbbbbbbbbbbbbbbbbbPbbbbbDDDDDDDDDDDDDbb",
    "fFFFFooooOOOOOOOOOOOOOOOOOOOOOooooFFFFVVVFFnnknnFFFFFFFFFFFPfFFFFDDDDDDDDDDDDDFF",
    "fFFFFooooOOOOOOOOOOOOOOOOOOOOOooooFFFFVVVFFnnknnFFFFFFFFFFFPfFFFFFdFFFFFFFFFdFFF",
    "fFFFFoottFFFFFFFFFFFfFFFFFFFFFttTTTTTTTTTTTTTTTTTTTFFFFFFPPPPPFFFFdFFFFFFFFFdFFF",
    "fffffffttfffffffffffffffffffffttTTTTTTTTTTTTTTTTTTTfffffffffffffffffffffffffffff",
    "FFFFFFFfFFFFFFFFFFFFFFFFFFFfFFFFFttFFFFFFFFFFFFfttFFFFFFFFFFFFFFFFFfFFFFFFFFFFFF",
    "FFFFFFFfFFFFFFFFFFFFFFFFFFRRRRRRRttRRRRRRRRRRRRRttRRRRRFFFFFFFFFFFFfFFFFFFFFFFFF",
    "FFFFFFFfFFFFFFFFFFFFFFFFFFRRrrrrrttrrrrrrrrrrrrrttrrrRRFFFFFFFFFFFFfFFFFFFFFFFFF",
    "ffffffffffffffffffffffffffRRrRRRRttRRRRRRRRRRRRRttRRrRRfffffffffffffffffffffffff",
    "FFFFFFFFFFFFFFfFFFFFFFFFFFRRrRRRRRRRRRRRRRRRRRRRRRRRrRRFFFFFFFFFFFFFFFFFFFfFFFFF",
    "FFFFFFFFFFFFFFfFFFFFFFFFFFRRrRRRRRRRRRRRRRRRRRRRRRRRrRRFFFFFFFFFFFFFFFFFFFfFFFFF",
    "FFFFFFFFFFFFFFfFFFFFFFFFFFRRrrrrrrrrrrrrrrrrrrrrrrrrrRRFFFFFFFFFFFFFFFFFFFfFFFFF",
    "ffffffffffffffffffffffffffRRRRRRRRRRRRRRRRRRRRRRRRRRRRRfffffffffffffffffffffffff",
    "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
]

# ------------------------------------------------------ loading PNGs
# Draw in Pixilart (or any editor), export as PNG at its original size
# (no scaling), at most 80 x 44, and save it next to game.py.

HERE = os.path.dirname(os.path.abspath(__file__))

def load_png(filename):
    """Read a PNG with only the standard library.
    Returns rows of (R, G, B) tuples, with None for see-through pixels."""
    path = os.path.join(HERE, filename)
    if not os.path.exists(path):
        sys.exit(f"Can't find {filename}. Put it in the same folder as game.py.")
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit(f"{filename} is not a PNG file.")

    # A PNG is a list of chunks: length, type, data, checksum
    pos, idat, palette, alpha = 8, b"", [], b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif kind == b"tRNS":
            alpha = body
        elif kind == b"IDAT":
            idat += body
    if interlace or depth == 16 or (depth < 8 and ctype not in (0, 3)):
        sys.exit(f"{filename}: please export as a normal 8-bit, non-interlaced PNG.")
    if width > ART_W or height > ART_H:
        sys.exit(f"{filename} is {width}x{height}, but the biggest picture is {ART_W}x{ART_H}.")

    # Bytes per pixel for each colour type: grey, RGB, palette, grey+alpha, RGBA
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw, stride = zlib.decompress(idat), (width * bpp * depth + 7) // 8
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(height):
        kind, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):   # undo the PNG row filter
            a = line[x - bpp] if x >= bpp else 0
            b, c = prev[x], prev[x - bpp] if x >= bpp else 0
            if kind == 1:
                line[x] = (line[x] + a) & 255
            elif kind == 2:
                line[x] = (line[x] + b) & 255
            elif kind == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line

        if depth < 8:   # small palettes pack several pixels into one byte
            per_byte, mask = 8 // depth, (1 << depth) - 1
            line = [(byte >> (8 - depth * (k + 1))) & mask
                    for byte in line for k in range(per_byte)][:width]
            if ctype == 0:
                line = [v * 255 // mask for v in line]
        row = []
        for x in range(0, width * bpp, bpp):
            px = line[x:x + bpp]
            if ctype == 0:
                rgb, a = (px[0],) * 3, 255
            elif ctype == 2:
                rgb, a = tuple(px), 255
            elif ctype == 3:
                rgb, a = palette[px[0]], alpha[px[0]] if px[0] < len(alpha) else 255
            elif ctype == 4:
                rgb, a = (px[0],) * 3, px[1]
            else:
                rgb, a = tuple(px[:3]), px[3]
            row.append(rgb if a >= 128 else None)
        rows.append(row)
    return rows


# ------------------------------------------------------------- frame
# A pixel frame drawn over the edges of every screen.
#  - SHOW_FRAME = False turns it off.
#  - FRAME_COLOURS recolours it. FRAME_PROFILE lists its layers from the
#    outside in, one pixel each, so add or remove names to make it thicker.
#  - Or draw your own: an 80 x 44 frame.png next to game.py, see-through
#    in the middle, is used instead of the built-in one.

SHOW_FRAME = True
FRAME_COLOURS = {
    "outline": (70, 40, 16),    # dark wood
    "gold":    (214, 162, 58),
    "shadow":  (150, 104, 30),  # darker gold on the inside edge
    "stud":    (255, 230, 140), # little shiny dots along the gold
    "gem":     (200, 40, 70),   # corner gems
}
FRAME_PROFILE = ["outline", "gold", "shadow"]
STUD_GAP = 6                    # pixels between studs, 0 for none

def make_frame():
    """Build the default frame as an ART_W x ART_H picture with a see-through middle."""
    frame = [[None] * ART_W for _ in range(ART_H)]
    for depth, name in enumerate(FRAME_PROFILE):
        rgb = FRAME_COLOURS[name]
        for x in range(depth, ART_W - depth):
            frame[depth][x] = frame[ART_H - 1 - depth][x] = rgb
        for y in range(depth, ART_H - depth):
            frame[y][depth] = frame[y][ART_W - 1 - depth] = rgb
    t = len(FRAME_PROFILE)
    if STUD_GAP and "gold" in FRAME_PROFILE:
        d = FRAME_PROFILE.index("gold")
        for x in range(t + STUD_GAP // 2, ART_W - t, STUD_GAP):
            frame[d][x] = frame[ART_H - 1 - d][x] = FRAME_COLOURS["stud"]
        for y in range(t + STUD_GAP // 2, ART_H - t, STUD_GAP):
            frame[y][d] = frame[y][ART_W - 1 - d] = FRAME_COLOURS["stud"]
    for cx in (0, ART_W - t):                      # square gems in the corners
        for cy in (0, ART_H - t):
            for y in range(cy, cy + t):
                for x in range(cx, cx + t):
                    frame[y][x] = FRAME_COLOURS["gem"]
    return frame

if not SHOW_FRAME:
    FRAME = None
elif os.path.exists(os.path.join(HERE, "frame.png")):
    FRAME = load_png("frame.png")
    if len(FRAME) != ART_H or len(FRAME[0]) != ART_W:
        sys.exit(f"frame.png must be exactly {ART_W}x{ART_H}.")
else:
    FRAME = make_frame()

# ----------------------------------------------------------- drawing
# A "picture" is a list of rows of (R, G, B) colours, ART_W x ART_H.

def colour(rgb, ground):
    """ANSI code for a colour. ground is 38 (text colour) or 48 (background)."""
    r, g, b = rgb
    if COLOR_MODE == "truecolor":
        return f"\x1b[{ground};2;{r};{g};{b}m"
    to6 = lambda v: 0 if v < 48 else (v - 35) // 40     # nearest 0..5 level
    return f"\x1b[{ground};5;{16 + 36 * to6(r) + 6 * to6(g) + to6(b)}m"

def pixels(art, palette):
    """Turn a character grid into colours. '.' becomes None (see-through)."""
    return [[None if ch == "." else palette[ch] for ch in row] for row in art]

def canvas(rgb):
    """A blank ART_W x ART_H picture of one colour."""
    return [[rgb] * ART_W for _ in range(ART_H)]

def paste(picture, sprite, x, y):
    """Copy sprite onto picture with its top-left at (x, y).
    See-through pixels are skipped. Returns a new picture."""
    rows = [list(row) for row in picture]
    for dy, line in enumerate(sprite):
        for dx, rgb in enumerate(line):
            if rgb is not None and 0 <= y + dy < ART_H and 0 <= x + dx < ART_W:
                rows[y + dy][x + dx] = rgb
    return rows

def render_art(picture, rows=ART_H // 2):
    """Turn pixel rows into text rows using '▀', two pixels per character.
    The text colour paints the top pixel, the background paints the bottom one.
    rows = how many text rows to show (the rest of the picture is cut off,
    to make room for more lines of text underneath)."""
    if FRAME:
        picture = paste(picture, FRAME, 0, 0)
    lines = []
    for y in range(0, rows * 2, 2):
        line, last = "", None
        for x in range(ART_W):
            pair = (picture[y][x], picture[y + 1][x])
            if pair != last:   # only send colour codes when they change
                line += colour(pair[0], 38) + colour(pair[1], 48)
                last = pair
            line += "▀"
        lines.append(line + RESET)
    return lines

def frame_sides():
    """The frame's left and right edge colours, read from its middle row,
    so the text rows below the picture carry the frame down."""
    if not FRAME:
        return [], []
    row = FRAME[ART_H // 2]
    left, right = [], []
    while row[len(left)] is not None:
        left.append(row[len(left)])
    while row[-1 - len(right)] is not None:
        right.insert(0, row[-1 - len(right)])
    return left, right

TEXT_FG, TEXT_BG = (240, 240, 240), (30, 30, 40)

def inner_width():
    left, right = frame_sides()
    return WIDTH - len(left) - len(right)

def text_row(text, fg=TEXT_FG, bg=TEXT_BG):
    """One 80-column row of centred text between the frame's sides.
    text is either a string, or a list of (string, colour) pieces for
    several colours on one row. Colour codes are added after centring,
    so they never count towards the width."""
    left, right = frame_sides()
    inner = inner_width()
    pieces = [(text, fg)] if isinstance(text, str) else list(text)
    plain = "".join(t for t, _ in pieces)[:inner]
    pad_left = (inner - len(plain)) // 2
    middle, used = colour(bg, 48) + " " * pad_left, 0
    for t, rgb in pieces:
        t = t[:inner - used]
        middle += colour(rgb, 38) + t
        used += len(t)
    middle += " " * (inner - pad_left - used)
    return ("".join(colour(rgb, 48) + " " for rgb in left) + middle +
            "".join(colour(rgb, 48) + " " for rgb in right) + RESET)

def bottom_row(text):
    """The last row: the frame's bottom bar with the text engraved in it."""
    left, _ = frame_sides()
    if not left:
        return text_row(text, fg=(160, 160, 180))
    edge, bar = left[0], left[len(left) // 2]
    return (colour(edge, 48) + " " + colour(edge, 38) + colour(bar, 48) +
            text[:WIDTH - 2].center(WIDTH - 2) + colour(edge, 48) + " " + RESET)

def wait_for_big_enough_terminal():
    while True:
        cols, rows = shutil.get_terminal_size()
        if cols >= WIDTH and rows >= HEIGHT:
            return
        sys.stdout.write(RESET + CLEAR +
                         f"Your terminal is {cols}x{rows}.\r\n"
                         f"Please make it at least {WIDTH}x{HEIGHT},\r\n"
                         "then press any key (Q to quit).")
        sys.stdout.flush()
        if get_key() == "q":
            raise SystemExit

def draw(art_lines, lines=(), hint=""):
    """Put art rows on screen with lines of text and a hint under them."""
    if isinstance(lines, str):
        lines = [lines]
    lines = list(lines) or [""]
    wait_for_big_enough_terminal()
    screen = art_lines[:HEIGHT - 1 - len(lines)] + [text_row(l) for l in lines] + [bottom_row(hint)]
    sys.stdout.write(CLEAR + "\r\n".join(screen))   # no newline after the last row
    sys.stdout.flush()

# -------------------------------------------------------------- input

def get_key():
    """Read one keypress without needing Enter."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":                 # arrow keys send ESC [ A/B/C/D
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if ch == "\x03":                     # Ctrl+C
        raise KeyboardInterrupt
    keys = {"\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right",
            "\x1b[D": "left", "\r": "enter", "\n": "enter"}
    return keys.get(ch, ch.lower())

# -------------------------------------------------------------- pages

STARS = [(5, 4), (14, 30), (22, 9), (60, 6), (70, 25), (75, 12), (8, 38), (66, 40)]

def menu_picture():
    picture = canvas(MENU_PALETTE["N"])
    for x, y in STARS:
        picture[y][x] = MENU_PALETTE["*"]
    x = (ART_W - len(SMILEY[0])) // 2
    y = (ART_H - len(SMILEY)) // 2
    return render_art(paste(picture, pixels(SMILEY, MENU_PALETTE), x, y))
def show(picture, lines=(), hint=""):
    """Draw a picture with lines of text underneath it.
    The more lines of text, the more of the picture's bottom is cut off."""
    if isinstance(lines, str):
        lines = [lines]
    lines = list(lines) or [""]
    art = render_art(picture, HEIGHT - 1 - len(lines))
    draw(art, lines, hint)

def wrap(text):
    """Split a long sentence into lines that fit between the frame's sides."""
    return textwrap.wrap(text, inner_width() - 4) or [""]

# ------------------------------------------------------- pixel font
# A tiny 3 x 5 font for numbers on the hotspots and the big titles.
# "#" is a pixel. Add more letters the same way if you need them.

FONT = {
    "A": ["###", "#.#", "###", "#.#", "#.#"], "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": ["###", "#..", "#..", "#..", "###"], "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"], "F": ["###", "#..", "##.", "#..", "#.."],
    "G": ["###", "#..", "#.#", "#.#", "###"], "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"], "J": ["..#", "..#", "..#", "#.#", "###"],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"], "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"], "N": ["##.", "#.#", "#.#", "#.#", "#.#"],
    "O": ["###", "#.#", "#.#", "#.#", "###"], "P": ["###", "#.#", "###", "#..", "#.."],
    "Q": ["###", "#.#", "#.#", "###", "..#"], "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": ["###", "#..", "###", "..#", "###"], "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"], "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"], "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."], "Z": ["###", "..#", ".#.", "#..", "###"],
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["##.", "..#", ".#.", "#..", "###"], "3": ["##.", "..#", ".#.", "..#", "##."],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "##.", "..#", "##."],
    "6": [".##", "#..", "###", "#.#", "###"], "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "##."],
    " ": ["...", "...", "...", "...", "..."], "-": ["...", "...", "###", "...", "..."],
    ".": ["...", "...", "...", "...", ".#."], ":": ["...", ".#.", "...", ".#.", "..."], "!": [".#.", ".#.", ".#.", "...", ".#."],
    "?": ["##.", "..#", ".#.", "...", ".#."], "'": [".#.", ".#.", "...", "...", "..."],
}

def text_pixels(text, rgb, scale=1):
    """Turn text into a sprite (rows of colours) using FONT."""
    rows = [[] for _ in range(5 * scale)]
    for i, ch in enumerate(text.upper()):
        glyph = FONT.get(ch, FONT["?"])
        for gy in range(5):
            line = [rgb if c == "#" else None for c in glyph[gy]]
            if i < len(text) - 1:
                line.append(None)                        # gap between letters
            line = [c for c in line for _ in range(scale)]
            for sy in range(scale):
                rows[gy * scale + sy].extend(line)
    return rows

def scale_up(sprite, n):
    """Make a sprite n times bigger (each pixel becomes n x n)."""
    return [[c for c in row for _ in range(n)] for row in sprite for _ in range(n)]

# --------------------------------------------------------- the art
# Every picture below is a PNG in the art folder, so you can open it in
# Pixilart, redraw it, and export it again at the same size.

ROOM = load_png("art/bedroom.png")              # 80 x 40, the bedroom search
CONFRONT_ROOM = load_png("art/confront-room.png")  # 80 x 32, the doorway
EMPTY_DOORWAY = load_png("art/empty-doorway.png")  # 80 x 32, after they leave
FACES = {name: load_png(f"art/partner-{name}.png")   # 26 x 28 each
         for name in ("neutral", "happy", "nervous", "shocked", "angry", "annoyed", "sad")}

def item_art(name):
    return load_png(f"art/items/{name}.png")    # 16 x 16 each

# --------------------------------------------------------- the story
# Ten places to search. Each has a "guilty" clue (left there if your
# partner is cheating) and an "innocent" one (if that spot is clean).
#   key      = the key you press in the bedroom
#   tag      = top-left pixel of the number tag drawn on the bedroom picture
#   backdrop = the colour behind the close-up of what you found
#   item     = PNG in art/items, face = partner's face when you show it,
#   guilt / paranoia = how much each meter rises when you show it

AREAS = [
    {"key": "1", "name": "Closet", "action": "CHECK CLOSET", "tag": (6, 9),
     "backdrop": (96, 64, 42),
     "guilty": {
        "find": "You find a designer tie hanging behind your winter coats. It definitely "
                "isn't yours. There is a faint whiff of expensive cologne you've never smelled before.",
        "evidence": "Designer Silk Tie", "short": "Silk tie", "item": "tie",
        "say": "Care to explain why I found a designer silk tie behind the winter coats? "
               "It's not mine, and it smells like a cologne I've never bought.",
        "reply": "They freeze, eyes widening. “Oh… uh, that? Wait, let me explain. A coworker "
                 "left it in the car after a ride-share and I just tossed it there... Look, "
                 "it's not what you think!”",
        "face": "shocked", "guilt": 2, "paranoia": 0},
     "innocent": {
        "find": "You find an old, oversized college hoodie stuffed in the back. It looks "
                "entirely foreign; you're unsure if this is the hoodie they wore in college or not.",
        "evidence": "Old Dirty Hoodie", "short": "Old hoodie", "item": "hoodie",
        "say": "I found this old college hoodie stuffed way in the back of the closet. Is this "
               "yours and why are you keeping ratty old clothes?",
        "reply": "They roll their eyes and laugh nervously. “Seriously? You're interrogating me "
                 "over a college hoodie I've owned for five years? Are you hearing yourself right now?”",
        "face": "annoyed", "guilt": 0, "paranoia": 2}},

    {"key": "2", "name": "Under bed", "action": "LOOK UNDER BED", "tag": (43, 32),
     "backdrop": (40, 34, 52),
     "guilty": {
        "find": "Your hand feels an unfamiliar black smartphone tucked near the baseboard. The "
                "screen lights up with a passcode prompt, and a text pops up from an unsaved "
                "contact: “Can't wait to see you again.”",
        "evidence": "Hidden Burner Phone", "short": "Burner phone", "item": "phone",
        "say": "I was looking under the bed and found a secret burner phone. It just lit up with "
               "a text from an unsaved number saying, 'Can't wait to see you again.' Care to comment?",
        "reply": "Their face instantly drains of colour. Their voice stammers. “Th-that's... where "
                 "did you even find that? It's an old phone for work, I swear, someone must have "
                 "left it—stop looking at me like that!”",
        "face": "shocked", "guilt": 4, "paranoia": 0},
     "innocent": {
        "find": "You pull out an old locked shoebox. After unlocking it you find dusty photo "
                "albums from your first year dating and a lost TV remote.",
        "evidence": "Old Photo Album", "short": "Photo album", "item": "album",
        "say": "I pulled out our old photo album from when we first started dating from under "
               "the bed. Are you trying to hide our history?",
        "reply": "They look genuinely confused and soften up. “Hide it? No... I just put it there "
                 "so it wouldn't get ruined. Why are you digging through our old pictures like a detective?”",
        "face": "neutral", "guilt": 0, "paranoia": 2}},

    {"key": "3", "name": "Bed sheets", "action": "EXAMINE SHEETS", "tag": (35, 24),
     "backdrop": (70, 90, 140),
     "guilty": {
        "find": "Tucked between the mattress and the headboard, you find a long, blonde hair "
                "strand. Neither you nor your partner has blonde hair.",
        "evidence": "Foreign Blonde Hair", "short": "Blonde hair", "item": "blonde-hair",
        "say": "Tucked right against the headboard, I found a long blonde hair strand. Neither "
               "of us are blonde. Who was in our bed?",
        "reply": "They cross their arms defensively. “Are you serious? It's probably from a "
                 "coworker at the office or a customer interaction, people shed everywhere! "
                 "You're grasping at straws.”",
        "face": "angry", "guilt": 1, "paranoia": 1},
     "innocent": {
        "find": "You find a stray feather from the down pillow that's been leaking slightly "
                "over the past week. Someone's been rushing the laundry.",
        "evidence": "Pillow Feather", "short": "Feather", "item": "feather",
        "say": "The down pillow has been leaking feathers all over the sheets. Why aren't you "
               "taking care of the house?",
        "reply": "They let out an exasperated sigh. “It's a cheap pillow, it leaks! Is this "
                 "really what we're arguing about right now?”",
        "face": "annoyed", "guilt": 0, "paranoia": 2}},

    {"key": "4", "name": "Bedside drawer", "action": "OPEN BEDSIDE DRAWER", "tag": (58, 23),
     "backdrop": (96, 64, 42),
     "guilty": {
        "find": "Pushed to the back beneath some old charging cables is a receipt from a "
                "run-down motel dated last Tuesday—when your partner claimed they were "
                "working late at the office.",
        "evidence": "Motel Receipt", "short": "Motel receipt", "item": "motel-receipt",
        "say": "I found a receipt from a run-down motel dated from last Tuesday. You told me "
               "you were working late at the office.",
        "reply": "They bite their lip, struggling for words. “That... okay, look, the office "
                 "conference room was booked, so we had to move a corporate client meeting to a "
                 "hotel lobby lounge. It's a business expense!”",
        "face": "nervous", "guilt": 3, "paranoia": 0},
     "innocent": {
        "find": "You find a receipt for late-night takeout from the local diner and a spare "
                "packet of all sorts of pills (Xanax, ibuprofen, Adderall, morphine, Ambien...).",
        "evidence": "Diner Takeout Receipt and Pills", "short": "Diner receipt", "item": "diner-receipt",
        "say": "I found a receipt for late-night diner takeout in your drawer along with an "
               "assortment of drugs. Who were you eating late-night burgers with without me and "
               "what are these drugs for?",
        "reply": "They stare at you incredulously. “It was midnight, I was starving after working "
                 "overtime, so I grabbed a burger by myself! Plus, I've been getting headaches "
                 "recently. Do I need to run my midnight cravings and headaches by you too?”",
        "face": "angry", "guilt": 0, "paranoia": 1}},

    {"key": "5", "name": "Laundry", "action": "SEARCH LAUNDRY", "tag": (22, 31),
     "backdrop": (150, 120, 80),
     "guilty": {
        "find": "At the bottom of the hamper, buried beneath towels, is a pair of underwear in a "
                "brand and size you and your partner do not own.",
        "evidence": "Foreign Underwear", "short": "Underwear", "item": "underwear",
        "say": "At the bottom of the laundry hamper, buried under the towels, I found a pair of "
               "underwear that is definitely not mine or yours.",
        "reply": "They panic, stepping back. “That's—ugh, that must have gotten mixed up in the "
                 "public laundromat dryer last week! It happens all the time!”",
        "face": "nervous", "guilt": 3, "paranoia": 0},
     "innocent": {
        "find": "You find your partner's gym clothes from a week ago, smelling faintly of "
                "standard laundry detergent and sweat.",
        "evidence": "Dirty Gym Clothes", "short": "Gym clothes", "item": "gym-clothes",
        "say": "I checked the laundry and found your gym clothes from yesterday smelling like "
               "standard sweat. What are you trying to mask?",
        "reply": "They sniff the air, looking offended. “They smell like sweat because I went to "
                 "the gym! What do you want them to smell like, roses?”",
        "face": "annoyed", "guilt": 0, "paranoia": 2}},

    {"key": "6", "name": "Vanity", "action": "CHECK DRESSER", "tag": (23, 21),
     "backdrop": (120, 70, 100),
     "guilty": {
        "find": "Next to the perfume tray sits a custom silver lipstick with the initials "
                "“J.K.” engraved. It definitely does not belong to you.",
        "evidence": "Foreign Lipstick", "short": "J.K. lipstick", "item": "lipstick-jk",
        "say": "Next to your perfume tray, there's a custom silver lipstick with the initials "
               "'J.K.' engraved. Who is J.K.?",
        "reply": "They touch their face nervously. “Oh, that's just... a brand sample a friend "
                 "gave me at brunch! Yeah, a friend!”",
        "face": "nervous", "guilt": 2, "paranoia": 0},
     "innocent": {
        "find": "You find a standard tube of lipstick and a receipt from the local grocery store "
                "for the weekly meat and vegetables.",
        "evidence": "Grocery Store Receipt", "short": "Grocery receipt", "item": "grocery-receipt",
        "say": "I found a grocery store receipt for vegetables. Why are you hiding your shopping "
               "habits from me?",
        "reply": "They burst out laughing, though it's tense. “I bought meat and vegetables to "
                 "make dinner! Are carrots a red flag now?”",
        "face": "happy", "guilt": 0, "paranoia": 3}},

    {"key": "7", "name": "Windowsill", "action": "INSPECT WINDOW", "tag": (38, 5),
     "backdrop": (34, 46, 96),
     "guilty": {
        "find": "Looking closely at the outside windowsill, you find a crushed cigarette "
                "butt—even though neither of you smokes.",
        "evidence": "Outside Cigarette Butt", "short": "Cigarette", "item": "cigarette",
        "say": "There's a fresh, crushed cigarette butt on the outside windowsill. Neither of us "
               "smokes. Who was standing outside our bedroom window?",
        "reply": "They blink rapidly. “Um... maybe the apartment maintenance guy dropped it "
                 "while fixing the roof? Yeah, maintenance!”",
        "face": "nervous", "guilt": 1, "paranoia": 1},
     "innocent": {
        "find": "The window is locked tight, and you just find a light layer of dust and a "
                "dead houseplant leaf.",
        "evidence": "Dust", "short": "Dust", "item": "dust",
        "say": "The window is completely locked, and there's just a layer of dust. What are you "
               "keeping locked away?",
        "reply": "“Dust? Really? It's an apartment window, it gets dusty! You're losing your mind.”",
        "face": "angry", "guilt": 0, "paranoia": 3}},

    {"key": "8", "name": "Trash can", "action": "CHECK TRASH CAN", "tag": (64, 31),
     "backdrop": (80, 86, 94),
     "guilty": {
        "find": "At the bottom lies a crumpled piece of paper with a handwritten phone number, "
                "signed with a small heart doodle.",
        "evidence": "Handwritten Number Note", "short": "Number note", "item": "number-note",
        "say": "At the bottom of the trash, I found a crumpled paper with a handwritten phone "
               "number and a little heart doodle on it.",
        "reply": "They look down at the floor, voice dropping. “Someone handed it to me at the "
                 "coffee shop and I threw it away immediately! The fact that you're digging "
                 "through the trash is toxic.”",
        "face": "sad", "guilt": 2, "paranoia": 0},
     "innocent": {
        "find": "You find crumpled wrapping paper and empty coffee cups from the morning rush. "
                "Doesn't your partner prefer tea?",
        "evidence": "Coffee Cups", "short": "Coffee cups", "item": "coffee-cups",
        "say": "Why are there empty coffee cups in the trash can? You don't even drink coffee.",
        "reply": "“I have to pull a lot of late nights lately so I'm just trying coffee out for "
                 "now, what's the big deal?”",
        "face": "annoyed", "guilt": 0, "paranoia": 1}},

    {"key": "9", "name": "Laptop", "action": "CHECK DESK", "tag": (70, 22),
     "backdrop": (50, 60, 80),
     "guilty": {
        "find": "The laptop is sitting open. A messaging app window was hastily minimized, "
                "revealing a chat where someone calls your partner “sweetheart” and talks "
                "about “booking a motel.”",
        "evidence": "Chat Log Snippet", "short": "Chat log", "item": "chat-log",
        "say": "Your laptop was left open. I saw a minimized messaging app where someone called "
               "you 'sweetheart' and talked about booking a motel.",
        "reply": "They completely freeze, panic setting in. “You hacked into my laptop?! Look... "
                 "it was a joke, a friend from college was messing around, it doesn't mean anything—!”",
        "face": "shocked", "guilt": 4, "paranoia": 0},
     "innocent": {
        "find": "The laptop is open to a spreadsheet tracking your household grocery budget and "
                "upcoming utility bills.",
        "evidence": "Household Budget Spreadsheet", "short": "Budget sheet", "item": "budget-sheet",
        "say": "Your laptop was open to a spreadsheet tracking our utility bills and grocery "
               "budget. What are you planning?",
        "reply": "“I'm trying to figure out how to pay our electric bill! Why are you snooping "
                 "through my open work spreadsheets?”",
        "face": "angry", "guilt": 0, "paranoia": 2}},

    {"key": "0", "name": "Shoe rack", "action": "CHECK SHOE RACK", "tag": (13, 31),
     "backdrop": (96, 64, 42),
     "guilty": {
        "find": "Pushed behind your winter boots is a pair of thigh-highs that clearly don't "
                "belong to you or your partner.",
        "evidence": "Unknown Thigh-Highs", "short": "Thigh-highs", "item": "thigh-highs",
        "say": "Pushed behind the winter boots is a pair of thigh-high stockings that belong to "
               "neither of us. Care to explain?",
        "reply": "They stammer, turning bright red. “Those were... a costume piece! From a party "
                 "last year! They just got shoved back there!”",
        "face": "nervous", "guilt": 2, "paranoia": 0},
     "innocent": {
        "find": "You find an old pair of running shoes caked in dried mud. You're unsure where "
                "the mud came from.",
        "evidence": "Old Running Shoes", "short": "Muddy shoes", "item": "running-shoes",
        "say": "I found your old running shoes caked in mud. Why are they hidden back there and "
               "why is there mud?",
        "reply": "“Because I went on a team hike last week? Do you even remember the things I say to you?”",
        "face": "angry", "guilt": 0, "paranoia": 2}},
]

# ----------------------------------------------------- game settings
# Change these to make the game easier or harder.

CHEAT_CHANCE = 0.8        # chance that your partner really is cheating
GUILTY_SPOTS = (4, 6)     # if they are, how many of the 10 spots hold a guilty clue
START_MINUTES = 21 * 60   # 9:00 PM
SEARCH_MINUTES = 15       # each search takes this long
HOME_MINUTES = 22 * 60 + 30   # they get home at 10:30 PM -> 6 searches
CONFESS_AT = 6            # guilt needed for a confession when you accuse
PARANOIA_MAX = 6          # at this much paranoia they walk out
METER_SIZE = 10           # blocks drawn for each meter

GOLD, GREY, RED, BLUE = (240, 200, 90), (130, 130, 150), (240, 90, 90), (120, 170, 250)

def clock(minutes):
    h, m = divmod(minutes, 60)
    return f"{(h - 1) % 12 + 1}:{m:02d} {'PM' if h >= 12 else 'AM'}"

def ask_menu(picture):
    """F was pressed. True means go back to the menu."""
    show(picture, "Return to menu? (Y/N)", "")
    return get_key() == "y"

def wait_key(picture, lines, hint="Press any key"):
    show(picture, lines, hint)
    return get_key()

class BackToMenu(Exception):
    pass

def press_on(picture, lines, hint="Press any key  |  F for menu"):
    """Show a page and wait. F asks to go back to the menu."""
    while True:
        if wait_key(picture, lines, hint) != "f":
            return
        if ask_menu(picture):
            raise BackToMenu

# ----------------------------------------------------------- scenes

def title_card(act, subtitle, colour_rgb=GOLD):
    picture = canvas((18, 14, 26))
    big = text_pixels(act, colour_rgb, 3)
    small = text_pixels(subtitle, (230, 230, 240), 1)
    picture = paste(picture, big, (ART_W - len(big[0])) // 2, 12)
    return paste(picture, small, (ART_W - len(small[0])) // 2, 31)

def bedroom_picture(searched):
    picture = [list(row) + [None] * (ART_W - len(row)) for row in ROOM]
    picture += [[ROOM[-1][x] for x in range(ART_W)] for _ in range(ART_H - len(ROOM))]
    for area in AREAS:
        # each spot gets its number in bright yellow with a dark outline,
        # turning grey once it has been searched
        x, y = area["tag"]
        done = area["key"] in searched
        digit = text_pixels(area["key"], (130, 130, 140) if done else (255, 226, 90))
        shadow = (50, 50, 56) if done else (40, 16, 24)
        for dy, row in enumerate(digit):
            for dx, rgb in enumerate(row):
                if rgb:
                    for oy in (-1, 0, 1):
                        for ox in (-1, 0, 1):
                            picture[y + 1 + dy + oy][x + 1 + dx + ox] = shadow
        picture = paste(picture, digit, x + 1, y + 1)
    return picture

def closeup_picture(area, clue):
    """A spotlight on the clue you just found."""
    back = area["backdrop"]
    dark = tuple(v // 2 for v in back)
    picture = canvas(dark)
    cx, cy = ART_W // 2, 18
    for y in range(ART_H):
        for x in range(ART_W):
            d = ((x - cx) ** 2 + ((y - cy) * 1.4) ** 2) ** 0.5
            if d < 20:
                picture[y][x] = back
            elif d < 23:
                picture[y][x] = tuple((a + b) // 2 for a, b in zip(back, dark))
    return paste(picture, scale_up(item_art(clue["item"]), 2), cx - 16, 2)

def confront_picture(face, holding=None, empty=False):
    room = EMPTY_DOORWAY if empty else CONFRONT_ROOM
    picture = [list(row) for row in room] + [list(room[-1]) for _ in range(ART_H - len(room))]
    if not empty:
        picture = paste(picture, FACES[face], 27, 32 - 28)
    if holding:     # the clue you're holding up, on a little card
        for y in range(11, 31):
            for x in range(5, 25):
                picture[y][x] = (250, 246, 236) if 5 < x < 24 and 11 < y < 30 else (60, 40, 30)
        picture = paste(picture, item_art(holding), 7, 13)
    return picture

def meter_line(guilt, paranoia):
    g = min(guilt, METER_SIZE)
    p = min(paranoia * METER_SIZE // PARANOIA_MAX, METER_SIZE)
    return [("GUILT ", RED), ("█" * g, RED), ("░" * (METER_SIZE - g), GREY), ("     ", GREY),
            ("PARANOIA ", BLUE), ("█" * p, BLUE), ("░" * (METER_SIZE - p), GREY)]

# ------------------------------------------------------------ act 1

def act_one(cheating):
    """Search the bedroom. Returns the clues you found, in order."""
    spots = set()
    if cheating:
        spots = set(random.sample([a["key"] for a in AREAS], random.randint(*GUILTY_SPOTS)))

    press_on(pixels(LIVING_ROOM, ROOM_PALETTE),
             ["It's 9:00 PM. Your phone buzzes. A text from your partner:",
              "“Working late again. Don't wait up.”",
              "That's the third time this week. Something isn't right."])
    press_on(title_card("ACT 1", "THE SEARCH"),
             ["They'll be home at " + clock(HOME_MINUTES) + ". Each search takes "
              f"{SEARCH_MINUTES} minutes.", "Search the bedroom for anything that doesn't add up."])

    found, searched, now = [], set(), START_MINUTES
    names = {a["key"]: a for a in AREAS}
    while now < HOME_MINUTES:
        left = (HOME_MINUTES - now) // SEARCH_MINUTES
        legend = []
        for half in (AREAS[:5], AREAS[5:]):
            row = []
            for a in half:
                col = GREY if a["key"] in searched else TEXT_FG
                row += [(a["key"] + " ", GOLD if a["key"] not in searched else GREY),
                        (a["name"] + "   ", col)]
            legend.append(row)
        status = (f"{clock(now)}   |   {left} search{'es' if left != 1 else ''} left   |   "
                  f"{len(found)} clue{'s' if len(found) != 1 else ''} found")
        picture = bedroom_picture(searched)
        show(picture, legend + [status], "Press a number to search  |  F for menu")
        key = get_key()
        if key == "f":
            if ask_menu(picture):
                raise BackToMenu
            continue
        if key not in names or key in searched:
            continue
        area = names[key]
        searched.add(key)
        now += SEARCH_MINUTES
        clue = area["guilty"] if key in spots else area["innocent"]
        found.append(clue)
        press_on(closeup_picture(area, clue),
                 ["> " + area["action"]] + wrap(clue["find"]) +
                 [[("Evidence gained: ", GREY), ("[" + clue["evidence"] + "]", GOLD)]])

    press_on(title_card("10:30", "KEYS IN THE DOOR", (200, 200, 220)),
             ["You hear keys turning in the front door.", "They're home."])
    return found

# ------------------------------------------------------------ act 2

def ending(picture, title, story, truth_line):
    lines = [[(title, GOLD)]] + wrap(story) + [[(truth_line, GREY)]]
    while len(lines) > 7:   # keep the picture big enough to see
        lines.pop(-2)
    press_on(picture, lines, "Press any key to return to the menu")

def act_two(cheating, found):
    press_on(title_card("ACT 2", "THE CONFRONTATION"),
             ["Show them what you found. Each clue makes a meter rise:",
              [("GUILT", RED), (" if it hits home, ", TEXT_FG), ("PARANOIA", BLUE),
               (" if it makes you look crazy.", TEXT_FG)],
              f"Guilt {CONFESS_AT}+ makes an accusation stick. Full paranoia: they walk out."])

    guilt = paranoia = 0
    face = "neutral"
    said = "“Hey... why is the bedroom such a mess? Why are you looking at me like that?”"
    left = list(found)
    while True:
        rows, row = [], []
        for i, clue in enumerate(left):
            row += [(f"{i + 1} ", GOLD), (clue["short"] + "    ", TEXT_FG)]
            if len(row) == 6:
                rows.append(row); row = []
        if row:
            rows.append(row)
        if not left:
            rows = [[("You have nothing left to show them.", GREY)]]
        said_lines = wrap(said)
        if len(said_lines) > 3:     # only room for 3 lines of what they last said
            said_lines = said_lines[:3]
            said_lines[2] += " ..."
        lines = ([meter_line(guilt, paranoia)] + said_lines + rows +
                 [[("A ", GOLD), ("Accuse them    ", TEXT_FG), ("T ", GOLD), ("Let it go", TEXT_FG)]])
        picture = confront_picture(face)
        show(picture, lines, "Press a number to show a clue  |  F for menu")
        key = get_key()
        if key == "f":
            if ask_menu(picture):
                raise BackToMenu
            continue
        if key == "a":
            return accuse(cheating, guilt)
        if key == "t":
            return let_it_go(cheating)
        if not key.isdigit() or not 1 <= int(key) <= len(left):
            continue

        clue = left.pop(int(key) - 1)
        press_on(confront_picture(face, clue["item"]),
                 [meter_line(guilt, paranoia), [("You:", GOLD)]] + wrap("“" + clue["say"] + "”"))
        guilt += clue["guilt"]
        paranoia += clue["paranoia"]
        face = clue["face"]
        change = []
        if clue["guilt"]:
            change += [(f"GUILT +{clue['guilt']}   ", RED)]
        if clue["paranoia"]:
            change += [(f"PARANOIA +{clue['paranoia']}", BLUE)]
        press_on(confront_picture(face, clue["item"]),
                 [meter_line(guilt, paranoia)] + wrap(clue["reply"])[:5] + [change])
        said = clue["reply"]

        if paranoia >= PARANOIA_MAX:
            return ending(confront_picture("neutral", empty=True), "ENDING: THE DOOR SLAMS",
                          "“I can't do this anymore. You tore the bedroom apart and now you're "
                          "interrogating me over nothing. You're paranoid.” They grab their keys. "
                          "The front door slams.",
                          "The truth: they were cheating. You'll never know now."
                          if cheating else "The truth: they were never cheating.")

def accuse(cheating, guilt):
    press_on(confront_picture("neutral"),
             [[("You:", GOLD)], "“Stop lying to me. I know what you've been doing.",
              "Just tell me the truth.”"])
    if cheating and guilt >= CONFESS_AT:
        ending(confront_picture("sad"), "ENDING: THE TRUTH",
               "They sink onto the edge of the bed and the excuses run out. “Okay. Okay... "
               "I've been seeing someone. I'm so sorry.” It hurts, but you know the truth.",
               "You saw through every lie.")
    elif cheating:
        ending(confront_picture("angry"), "ENDING: NO PROOF",
               "“A few random things and you're calling me a cheater? You've got nothing!” "
               "They storm off to the couch. Somewhere under the bed, a phone buzzes.",
               "The truth: they WERE cheating, but you couldn't make it stick.")
    else:
        ending(confront_picture("sad"), "ENDING: FALSE ACCUSATION",
               "“After everything... you really think that of me?” Their voice breaks. They pack "
               "a bag and leave to stay with a friend.",
               "The truth: they were never cheating.")

def let_it_go(cheating):
    press_on(confront_picture("neutral"),
             [[("You:", GOLD)], "“Forget it. I'm sorry... I'm just tired.”"])
    if cheating:
        ending(confront_picture("happy"), "ENDING: BLISSFUL IGNORANCE",
               "“Thanks, babe. Night.” They kiss your forehead and turn off the lamp. In the dark, "
               "a phone you never found lights up: “Can't wait to see you again.”",
               "The truth: they were cheating.")
    else:
        ending(confront_picture("happy"), "ENDING: TRUST",
               "“Come here. I know I've been working too much. Let's take Saturday off, just us.” "
               "You let the doubts go.",
               "The truth: they were faithful all along. Best ending!")

def play():
    cheating = random.random() < CHEAT_CHANCE
    try:
        found = act_one(cheating)
        act_two(cheating, found)
    except BackToMenu:
        pass

def menu():
    art = menu_picture()
    while True:
        draw(art, [[("SUSPICION", GOLD), ("   -   Press Enter to start", TEXT_FG)]], "Q to quit")
        key = get_key()
        if key == "enter":
            return True
        if key == "q":
            return False

def main():
    if os.environ.get("SEED"):      # SEED=1 python3 game.py replays the same game
        random.seed(os.environ["SEED"])
    sys.stdout.write(HIDE_CURSOR)
    # Keep the terminal in raw mode for the whole game, so keys pressed
    # while a picture is still drawing are not lost.
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        while menu():
            play()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        sys.stdout.write(RESET + SHOW_CURSOR + CLEAR)
        print("Thanks for playing!")

if __name__ == "__main__":
    main()
