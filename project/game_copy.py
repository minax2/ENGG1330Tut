import sys, tty, termios, shutil, struct, zlib, random, textwrap

WIDTH, HEIGHT = 80, 24
ART_H = 44
SIDE = 3   #width of the frame's left and right edges

RESET, CLEAR = "\x1b[0m", "\x1b[H\x1b[2J"

TEXT_FG, TEXT_BG, HINT_FG = (240, 240, 240), (30, 30, 40), (70, 40, 16)
GOLD, GREY, RED, BLUE = (240, 200, 90), (130, 130, 150), (240, 90, 90), (120, 170, 250)

def paeth(a, b, c):
    p = a + b - c
    if abs(p - a) <= abs(p - b) and abs(p - a) <= abs(p - c):
        return a
    if abs(p - b) <= abs(p - c):
        return b
    return c


def load_png(filename):
    #returns a list of rows, each pixel is (r, g, b) or None if see-through
    with open(filename, "rb") as f:
        data = f.read()

    pos = 8
    idat = b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, ctype = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            idat += body
        pos += length + 12

    if depth != 8 or ctype not in (2, 6):
        sys.exit(filename + " must be saved as an RGB or RGBA PNG")
    bpp = 3 if ctype == 2 else 4
    stride = width * bpp
    raw = zlib.decompress(idat)

    rows = []
    prev = [0] * stride
    i = 0
    for y in range(height):
        filter_type = raw[i]
        line = list(raw[i + 1:i + 1 + stride])
        i += stride + 1
        #every row is saved with a filter, this undoes it
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if filter_type == 1:
                line[x] = (line[x] + a) % 256
            elif filter_type == 2:
                line[x] = (line[x] + b) % 256
            elif filter_type == 3:
                line[x] = (line[x] + (a + b) // 2) % 256
            elif filter_type == 4:
                line[x] = (line[x] + paeth(a, b, c)) % 256
        prev = line

        row = []
        for x in range(0, stride, bpp):
            if bpp == 4 and line[x + 3] < 128:
                row.append(None)
            else:
                row.append(tuple(line[x:x + 3]))
        rows.append(row)
    return rows

FRAME = load_png("art/frame.png")
MENU = load_png("art/menu.png")
LIVING_ROOM = load_png("art/living-room.png")
ROOM = load_png("art/bedroom.png")
SPOTLIGHT = load_png("art/spotlight.png")
CONFRONT_ROOM = load_png("art/confront-room.png")
EMPTY_DOORWAY = load_png("art/empty-doorway.png")
TITLES = {name: load_png(f"art/title-{name}.png") for name in ("act1", "1030", "act2")}
CARD = load_png("art/card.png")
FACES = {name: load_png(f"art/partner-{name}.png")
         for name in ("neutral", "happy", "nervous", "shocked", "angry", "annoyed", "sad")}
NUMBERS = {d: load_png(f"art/numbers/{d}.png") for d in "0123456789"}
SEARCHED_NUMBERS = {d: load_png(f"art/numbers/{d}-searched.png") for d in "0123456789"}

#drawing

def colour(rgb, ground):
    #ground is 38 for the text colour, 48 for the background colour
    r, g, b = rgb
    return f"\x1b[{ground};2;{r};{g};{b}m"

def paste(picture, sprite, x, y):
    new = [list(row) for row in picture]
    for dy, line in enumerate(sprite):
        for dx, rgb in enumerate(line):
            if rgb is not None and 0 <= y + dy < ART_H and 0 <= x + dx < WIDTH:
                new[y + dy][x + dx] = rgb
    return new

def scale_up(sprite):
    big = []
    for row in sprite:
        big_row = []
        for c in row:
            for i in range(2):
                big_row.append(c)
        for i in range(2):
            big.append(big_row)
    return big

def half_block(top, bottom):
    #"▀" shows two pixels in one character: text colour on top, background below
    return colour(top, 38) + colour(bottom, 48) + "▀"

def render_art(picture, rows):
    picture = paste(picture, FRAME, 0, 0)
    lines = []
    for y in range(0, rows * 2, 2):
        line = ""
        for x in range(WIDTH):
            line += half_block(picture[y][x], picture[y + 1][x])
        lines.append(line + RESET)
    return lines

def frame_cell(x, row):
    top = FRAME[row * 2][x]
    bottom = FRAME[row * 2 + 1][x]
    if top is None:
        top = TEXT_BG
    if bottom is None:
        bottom = TEXT_BG
    return half_block(top, bottom)

def text_row(text, row):
    #text is a string, or a list of (string, colour) pairs for more than one colour
    inner = WIDTH - 2 * SIDE
    if isinstance(text, str):
        text = [(text, TEXT_FG)]
    length = min(sum(len(t) for t, _ in text), inner)
    pad = (inner - length) // 2
    middle = colour(TEXT_BG, 48) + " " * pad
    used = 0
    for t, rgb in text:
        middle += colour(rgb, 38) + t
        used += len(t)
    middle += " " * (inner - pad - used)
    left = "".join(frame_cell(x, row) for x in range(SIDE))
    right = "".join(frame_cell(x, row) for x in range(WIDTH - SIDE, WIDTH))
    return left + middle + right + RESET

def bottom_row(hint):
    row = HEIGHT - 1
    start = (WIDTH - len(hint)) // 2
    line = ""
    for x in range(WIDTH):
        i = x - start
        if 0 <= i < len(hint) and hint[i] != " ":
            line += colour(HINT_FG, 38) + colour(FRAME[row * 2][x], 48) + hint[i]
        else:
            line += frame_cell(x, row)
    return line + RESET

def wrap(text):
    return textwrap.wrap(text, WIDTH - 2 * SIDE - 4)

def get_key():
    ch = sys.stdin.read(1)
    if ch in ("\r", "\n"):
        return "enter"
    return ch.lower()

def show(picture, lines, hint=""):
    #the picture fills whatever rows are left above the text
    if isinstance(lines, str):
        lines = [lines]
    while True:
        cols, rows = shutil.get_terminal_size()
        if cols >= WIDTH and rows >= HEIGHT:
            break
        sys.stdout.write(RESET + CLEAR + f"Please make the terminal at least {WIDTH}x{HEIGHT}, "
                         "then press any key.")
        sys.stdout.flush()
        get_key()
    art = render_art(picture, HEIGHT - 1 - len(lines))
    text = [text_row(line, len(art) + i) for i, line in enumerate(lines)]
    sys.stdout.write(CLEAR + "\r\n".join(art + text + [bottom_row(hint)]))
    sys.stdout.flush()

#story
#tag = where the number goes on the bedroom picture

AREAS = [
    {"key": "1", "name": "Closet", "action": "CHECK CLOSET", "tag": (6, 9),
     "guilty": {
        "find": "You find a designer tie hanging behind your winter coats. It definitely "
                "isn't yours. There is a faint whiff of expensive cologne you've never smelled before.",
        "evidence": "Designer Silk Tie", "short": "Silk tie", "item": "tie",
        "say": "Care to explain why I found a designer silk tie behind the winter coats? "
               "It's not mine, and it smells like a cologne I've never bought.",
        "reply": "They freeze, eyes widening. 'Oh... uh, that? Wait, let me explain. A coworker "
                 "left it in the car after a ride-share and I just tossed it there... Look, "
                 "it's not what you think!'",
        "face": "shocked", "guilt": 2, "paranoia": 0},
     "innocent": {
        "find": "You find an old, oversized college hoodie stuffed in the back. It looks "
                "entirely foreign; you're unsure if this is the hoodie they wore in college or not.",
        "evidence": "Old Dirty Hoodie", "short": "Old hoodie", "item": "hoodie",
        "say": "I found this old college hoodie stuffed way in the back of the closet. Is this "
               "yours and why are you keeping ratty old clothes?",
        "reply": "They roll their eyes and laugh nervously. 'Seriously? You're interrogating me "
                 "over a college hoodie I've owned for five years? Are you hearing yourself right now?'",
        "face": "annoyed", "guilt": 0, "paranoia": 2}},

    {"key": "2", "name": "Under bed", "action": "LOOK UNDER BED", "tag": (43, 32),
     "guilty": {
        "find": "Your hand feels an unfamiliar black smartphone tucked near the baseboard. The "
                "screen lights up with a passcode prompt, and a text pops up from an unsaved "
                "contact: 'Can't wait to see you again.'",
        "evidence": "Hidden Burner Phone", "short": "Burner phone", "item": "phone",
        "say": "I was looking under the bed and found a secret burner phone. It just lit up with "
               "a text from an unsaved number saying, 'Can't wait to see you again.' Care to comment?",
        "reply": "Their face instantly drains of colour. Their voice stammers. 'Th-that's... where "
                 "did you even find that? It's an old phone for work, I swear, someone must have "
                 "left it-stop looking at me like that!'",
        "face": "shocked", "guilt": 4, "paranoia": 0},
     "innocent": {
        "find": "You pull out an old locked shoebox. After unlocking it you find dusty photo "
                "albums from your first year dating and a lost TV remote.",
        "evidence": "Old Photo Album", "short": "Photo album", "item": "album",
        "say": "I pulled out our old photo album from when we first started dating from under "
               "the bed. Are you trying to hide our history?",
        "reply": "They look genuinely confused and soften up. 'Hide it? No... I just put it there "
                 "so it wouldn't get ruined. Why are you digging through our old pictures like a detective?'",
        "face": "neutral", "guilt": 0, "paranoia": 2}},

    {"key": "3", "name": "Bed sheets", "action": "EXAMINE SHEETS", "tag": (35, 24),
     "guilty": {
        "find": "Tucked between the mattress and the headboard, you find a long, blonde hair "
                "strand. Neither you nor your partner has blonde hair.",
        "evidence": "Foreign Blonde Hair", "short": "Blonde hair", "item": "blonde-hair",
        "say": "Tucked right against the headboard, I found a long blonde hair strand. Neither "
               "of us are blonde. Who was in our bed?",
        "reply": "They cross their arms defensively. 'Are you serious? It's probably from a "
                 "coworker at the office or a customer interaction, people shed everywhere! "
                 "You're grasping at straws.'",
        "face": "angry", "guilt": 1, "paranoia": 1},
     "innocent": {
        "find": "You find a stray feather from the down pillow that's been leaking slightly "
                "over the past week. Someone's been rushing the laundry.",
        "evidence": "Pillow Feather", "short": "Feather", "item": "feather",
        "say": "The down pillow has been leaking feathers all over the sheets. Why aren't you "
               "taking care of the house?",
        "reply": "They let out an exasperated sigh. 'It's a cheap pillow, it leaks! Is this "
                 "really what we're arguing about right now?'",
        "face": "annoyed", "guilt": 0, "paranoia": 2}},

    {"key": "4", "name": "Bedside drawer", "action": "OPEN BEDSIDE DRAWER", "tag": (58, 23),
     "guilty": {
        "find": "Pushed to the back beneath some old charging cables is a receipt from a "
                "run-down motel dated last Tuesday-when your partner claimed they were "
                "working late at the office.",
        "evidence": "Motel Receipt", "short": "Motel receipt", "item": "motel-receipt",
        "say": "I found a receipt from a run-down motel dated from last Tuesday. You told me "
               "you were working late at the office.",
        "reply": "They bite their lip, struggling for words. 'That... okay, look, the office "
                 "conference room was booked, so we had to move a corporate client meeting to a "
                 "hotel lobby lounge. It's a business expense!'",
        "face": "nervous", "guilt": 3, "paranoia": 0},
     "innocent": {
        "find": "You find a receipt for late-night takeout from the local diner and a spare "
                "packet of all sorts of pills (Xanax, ibuprofen, Adderall, morphine, Ambien...).",
        "evidence": "Diner Takeout Receipt and Pills", "short": "Diner receipt", "item": "diner-receipt",
        "say": "I found a receipt for late-night diner takeout in your drawer along with an "
               "assortment of drugs. Who were you eating late-night burgers with without me and "
               "what are these drugs for?",
        "reply": "They stare at you incredulously. 'It was midnight, I was starving after working "
                 "overtime, so I grabbed a burger by myself! Plus, I've been getting headaches "
                 "recently. Do I need to run my midnight cravings and headaches by you too?'",
        "face": "angry", "guilt": 0, "paranoia": 1}},

    {"key": "5", "name": "Laundry", "action": "SEARCH LAUNDRY", "tag": (22, 31),
     "guilty": {
        "find": "At the bottom of the hamper, buried beneath towels, is a pair of underwear in a "
                "brand and size you and your partner do not own.",
        "evidence": "Foreign Underwear", "short": "Underwear", "item": "underwear",
        "say": "At the bottom of the laundry hamper, buried under the towels, I found a pair of "
               "underwear that is definitely not mine or yours.",
        "reply": "They panic, stepping back. 'That's-ugh, that must have gotten mixed up in the "
                 "public laundromat dryer last week! It happens all the time!'",
        "face": "nervous", "guilt": 3, "paranoia": 0},
     "innocent": {
        "find": "You find your partner's gym clothes from a week ago, smelling faintly of "
                "standard laundry detergent and sweat.",
        "evidence": "Dirty Gym Clothes", "short": "Gym clothes", "item": "gym-clothes",
        "say": "I checked the laundry and found your gym clothes from yesterday smelling like "
               "standard sweat. What are you trying to mask?",
        "reply": "They sniff the air, looking offended. 'They smell like sweat because I went to "
                 "the gym! What do you want them to smell like, roses?'",
        "face": "annoyed", "guilt": 0, "paranoia": 2}},

    {"key": "6", "name": "Vanity", "action": "CHECK DRESSER", "tag": (23, 21),
     "guilty": {
        "find": "Next to the perfume tray sits a custom silver lipstick with the initials "
                "'J.K.' engraved. It definitely does not belong to you.",
        "evidence": "Foreign Lipstick", "short": "J.K. lipstick", "item": "lipstick-jk",
        "say": "Next to your perfume tray, there's a custom silver lipstick with the initials "
               "'J.K.' engraved. Who is J.K.?",
        "reply": "They touch their face nervously. 'Oh, that's just... a brand sample a friend "
                 "gave me at brunch! Yeah, a friend!'",
        "face": "nervous", "guilt": 2, "paranoia": 0},
     "innocent": {
        "find": "You find a standard tube of lipstick and a receipt from the local grocery store "
                "for the weekly meat and vegetables.",
        "evidence": "Grocery Store Receipt", "short": "Grocery receipt", "item": "grocery-receipt",
        "say": "I found a grocery store receipt for vegetables. Why are you hiding your shopping "
               "habits from me?",
        "reply": "They burst out laughing, though it's tense. 'I bought meat and vegetables to "
                 "make dinner! Are carrots a red flag now?'",
        "face": "happy", "guilt": 0, "paranoia": 3}},

    {"key": "7", "name": "Windowsill", "action": "INSPECT WINDOW", "tag": (38, 5),
     "guilty": {
        "find": "Looking closely at the outside windowsill, you find a crushed cigarette "
                "butt-even though neither of you smokes.",
        "evidence": "Outside Cigarette Butt", "short": "Cigarette", "item": "cigarette",
        "say": "There's a fresh, crushed cigarette butt on the outside windowsill. Neither of us "
               "smokes. Who was standing outside our bedroom window?",
        "reply": "They blink rapidly. 'Um... maybe the apartment maintenance guy dropped it "
                 "while fixing the roof? Yeah, maintenance!'",
        "face": "nervous", "guilt": 1, "paranoia": 1},
     "innocent": {
        "find": "The window is locked tight, and you just find a light layer of dust and a "
                "dead houseplant leaf.",
        "evidence": "Dust", "short": "Dust", "item": "dust",
        "say": "The window is completely locked, and there's just a layer of dust. What are you "
               "keeping locked away?",
        "reply": "'Dust? Really? It's an apartment window, it gets dusty! You're losing your mind.'",
        "face": "angry", "guilt": 0, "paranoia": 3}},

    {"key": "8", "name": "Trash can", "action": "CHECK TRASH CAN", "tag": (64, 31),
     "guilty": {
        "find": "At the bottom lies a crumpled piece of paper with a handwritten phone number, "
                "signed with a small heart doodle.",
        "evidence": "Handwritten Number Note", "short": "Number note", "item": "number-note",
        "say": "At the bottom of the trash, I found a crumpled paper with a handwritten phone "
               "number and a little heart doodle on it.",
        "reply": "They look down at the floor, voice dropping. 'Someone handed it to me at the "
                 "coffee shop and I threw it away immediately! The fact that you're digging "
                 "through the trash is toxic.'",
        "face": "sad", "guilt": 2, "paranoia": 0},
     "innocent": {
        "find": "You find crumpled wrapping paper and empty coffee cups from the morning rush. "
                "Doesn't your partner prefer tea?",
        "evidence": "Coffee Cups", "short": "Coffee cups", "item": "coffee-cups",
        "say": "Why are there empty coffee cups in the trash can? You don't even drink coffee.",
        "reply": "'I have to pull a lot of late nights lately so I'm just trying coffee out for "
                 "now, what's the big deal?'",
        "face": "annoyed", "guilt": 0, "paranoia": 1}},

    {"key": "9", "name": "Laptop", "action": "CHECK DESK", "tag": (70, 22),
     "guilty": {
        "find": "The laptop is sitting open. A messaging app window was hastily minimized, "
                "revealing a chat where someone calls your partner 'sweetheart' and talks "
                "about 'booking a motel.'",
        "evidence": "Chat Log Snippet", "short": "Chat log", "item": "chat-log",
        "say": "Your laptop was left open. I saw a minimized messaging app where someone called "
               "you 'sweetheart' and talked about booking a motel.",
        "reply": "They completely freeze, panic setting in. 'You hacked into my laptop?! Look... "
                 "it was a joke, a friend from college was messing around, it doesn't mean anything-!'",
        "face": "shocked", "guilt": 4, "paranoia": 0},
     "innocent": {
        "find": "The laptop is open to a spreadsheet tracking your household grocery budget and "
                "upcoming utility bills.",
        "evidence": "Household Budget Spreadsheet", "short": "Budget sheet", "item": "budget-sheet",
        "say": "Your laptop was open to a spreadsheet tracking our utility bills and grocery "
               "budget. What are you planning?",
        "reply": "'I'm trying to figure out how to pay our electric bill! Why are you snooping "
                 "through my open work spreadsheets?'",
        "face": "angry", "guilt": 0, "paranoia": 2}},

    {"key": "0", "name": "Shoe rack", "action": "CHECK SHOE RACK", "tag": (13, 31),
     "guilty": {
        "find": "Pushed behind your winter boots is a pair of thigh-highs that clearly don't "
                "belong to you or your partner.",
        "evidence": "Unknown Thigh-Highs", "short": "Thigh-highs", "item": "thigh-highs",
        "say": "Pushed behind the winter boots is a pair of thigh-high stockings that belong to "
               "neither of us. Care to explain?",
        "reply": "They stammer, turning bright red. 'Those were... a costume piece! From a party "
                 "last year! They just got shoved back there!'",
        "face": "nervous", "guilt": 2, "paranoia": 0},
     "innocent": {
        "find": "You find an old pair of running shoes caked in dried mud. You're unsure where "
                "the mud came from.",
        "evidence": "Old Running Shoes", "short": "Muddy shoes", "item": "running-shoes",
        "say": "I found your old running shoes caked in mud. Why are they hidden back there and "
               "why is there mud?",
        "reply": "'Because I went on a team hike last week? Do you even remember the things I say to you?'",
        "face": "angry", "guilt": 0, "paranoia": 2}},
]

ITEMS = {}
for area in AREAS:
    for clue in (area["guilty"], area["innocent"]):
        ITEMS[clue["item"]] = load_png(f"art/items/{clue['item']}.png")

CHEAT_CHANCE = 0.8
GUILTY_SPOTS = (4, 6)        #how many spots have a guilty clue if they are cheating
START_MINUTES = 21 * 60      #9:00 PM
HOME_MINUTES = 22 * 60 + 30  #10:30 PM
SEARCH_MINUTES = 15
CONFESS_AT = 6
PARANOIA_MAX = 6
METER_SIZE = 10

class BackToMenu(Exception):
    pass

def clock(minutes):
    h, m = divmod(minutes, 60)
    return f"{(h - 1) % 12 + 1}:{m:02d} PM"

def ask_menu(picture):
    show(picture, "Return to menu? (Y/N)")
    return get_key() == "y"

def press_on(picture, lines, hint="Press any key  |  F for menu"):
    while True:
        show(picture, lines, hint)
        if get_key() != "f":
            return
        if ask_menu(picture):
            raise BackToMenu

def bedroom_picture(searched):
    picture = ROOM
    for area in AREAS:
        x, y = area["tag"]
        if area["key"] in searched:
            picture = paste(picture, SEARCHED_NUMBERS[area["key"]], x, y)
        else:
            picture = paste(picture, NUMBERS[area["key"]], x, y)
    return picture

def closeup_picture(clue):
    return paste(SPOTLIGHT, scale_up(ITEMS[clue["item"]]), 24, 2)

def confront_picture(face, holding=None):
    picture = paste(CONFRONT_ROOM, FACES[face], 28, 6)
    if holding:
        picture = paste(picture, CARD, 5, 11)
        picture = paste(picture, ITEMS[holding], 7, 13)
    return picture

def meter_line(guilt, paranoia):
    g = min(guilt, METER_SIZE)
    p = min(paranoia * METER_SIZE // PARANOIA_MAX, METER_SIZE)
    return [("GUILT ", RED), ("█" * g, RED), ("░" * (METER_SIZE - g), GREY), ("     ", GREY),
            ("PARANOIA ", BLUE), ("█" * p, BLUE), ("░" * (METER_SIZE - p), GREY)]

#act 1

def act_one(cheating):
    guilty = set()
    if cheating:
        keys = [area["key"] for area in AREAS]
        guilty = set(random.sample(keys, random.randint(*GUILTY_SPOTS)))

    press_on(LIVING_ROOM,
             ["It's 9:00 PM. Your phone buzzes. A text from your partner:",
              '"Working late again. Don\'t wait up."',
              "That's the third time this week. Something isn't right."])
    press_on(TITLES["act1"],
             [f"They'll be home at {clock(HOME_MINUTES)}. Each search takes {SEARCH_MINUTES} minutes.",
              "Search the bedroom for anything that doesn't add up."])

    found = []
    searched = set()
    now = START_MINUTES
    while now < HOME_MINUTES:
        legend = []
        for half in (AREAS[:5], AREAS[5:]):
            row = []
            for area in half:
                if area["key"] in searched:
                    row += [(area["key"] + " ", GREY), (area["name"] + "   ", GREY)]
                else:
                    row += [(area["key"] + " ", GOLD), (area["name"] + "   ", TEXT_FG)]
            legend.append(row)
        left = (HOME_MINUTES - now) // SEARCH_MINUTES
        searches = "search" if left == 1 else "searches"
        clues = "clue" if len(found) == 1 else "clues"
        status = f"{clock(now)}   |   {left} {searches} left   |   {len(found)} {clues} found"

        picture = bedroom_picture(searched)
        show(picture, legend + [status], "Press a number to search  |  F for menu")
        key = get_key()
        if key == "f":
            if ask_menu(picture):
                raise BackToMenu
            continue

        for area in AREAS:
            if area["key"] == key and key not in searched:
                searched.add(key)
                now += SEARCH_MINUTES
                if key in guilty:
                    clue = area["guilty"]
                else:
                    clue = area["innocent"]
                found.append(clue)
                press_on(closeup_picture(clue),
                         ["> " + area["action"]] + wrap(clue["find"]) +
                         [[("Evidence gained: ", GREY), ("[" + clue["evidence"] + "]", GOLD)]])

    press_on(TITLES["1030"], ["You hear keys turning in the front door.", "They're home."])
    return found

#act 2

def ending(picture, title, story, truth):
    lines = [[(title, GOLD)]] + wrap(story)[:5] + [[(truth, GREY)]]
    press_on(picture, lines, "Press any key to return to the menu")

def act_two(cheating, found):
    press_on(TITLES["act2"],
             ["Show them what you found. Each clue makes a meter rise:",
              [("GUILT", RED), (" if it hits home, ", TEXT_FG), ("PARANOIA", BLUE),
               (" if it makes you look crazy.", TEXT_FG)],
              f"Guilt {CONFESS_AT}+ makes an accusation stick. Full paranoia: they walk out."])

    guilt = 0
    paranoia = 0
    face = "neutral"
    said = '"Hey... why is the bedroom such a mess? Why are you looking at me like that?"'
    clues = list(found)
    while True:
        rows = []
        row = []
        for i, clue in enumerate(clues):
            row += [(f"{i + 1} ", GOLD), (clue["short"] + "    ", TEXT_FG)]
            if len(row) == 6:   #3 clues per row
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        if not clues:
            rows = [[("You have nothing left to show them.", GREY)]]

        lines = ([meter_line(guilt, paranoia)] + wrap(said)[:3] + rows +
                 [[("A ", GOLD), ("Accuse them    ", TEXT_FG), ("T ", GOLD), ("Let it go", TEXT_FG)]])
        picture = confront_picture(face)
        show(picture, lines, "Press a number to show a clue  |  F for menu")
        key = get_key()
        if key == "f":
            if ask_menu(picture):
                raise BackToMenu
            continue
        if key == "a":
            accuse(cheating, guilt)
            return
        if key == "t":
            let_it_go(cheating)
            return
        if not key.isdigit() or not 1 <= int(key) <= len(clues):
            continue

        clue = clues.pop(int(key) - 1)
        press_on(confront_picture(face, clue["item"]),
                 [meter_line(guilt, paranoia), [("You:", GOLD)]] + wrap('"' + clue["say"] + '"'))
        guilt += clue["guilt"]
        paranoia += clue["paranoia"]
        face = clue["face"]
        change = []
        if clue["guilt"]:
            change.append((f"GUILT +{clue['guilt']}   ", RED))
        if clue["paranoia"]:
            change.append((f"PARANOIA +{clue['paranoia']}", BLUE))
        press_on(confront_picture(face, clue["item"]),
                 [meter_line(guilt, paranoia)] + wrap(clue["reply"])[:5] + [change])
        said = clue["reply"]

        if paranoia >= PARANOIA_MAX:
            if cheating:
                truth = "The truth: they were cheating. You'll never know now."
            else:
                truth = "The truth: they were never cheating."
            ending(EMPTY_DOORWAY, "ENDING: THE DOOR SLAMS",
                   '"I can\'t do this anymore. You tore the bedroom apart and now you\'re '
                   'interrogating me over nothing." They grab their keys. The front door slams.',
                   truth)
            return

def accuse(cheating, guilt):
    press_on(confront_picture("neutral"),
             [[("You:", GOLD)], '"Stop lying to me. I know what you\'ve been doing.',
              'Just tell me the truth."'])
    if cheating and guilt >= CONFESS_AT:
        ending(confront_picture("sad"), "ENDING: THE TRUTH",
               "They sink onto the edge of the bed and the excuses run out. \"Okay. Okay... "
               "I've been seeing someone. I'm so sorry.\" It hurts, but you know the truth.",
               "You saw through every lie.")
    elif cheating:
        ending(confront_picture("angry"), "ENDING: NO PROOF",
               "\"A few random things and you're calling me a cheater? You've got nothing!\" "
               "They storm off to the couch. Somewhere under the bed, a phone buzzes.",
               "The truth: they WERE cheating, but you couldn't make it stick.")
    else:
        ending(confront_picture("sad"), "ENDING: FALSE ACCUSATION",
               "\"After everything... you really think that of me?\" Their voice breaks. They pack "
               "a bag and leave to stay with a friend.",
               "The truth: they were never cheating.")

def let_it_go(cheating):
    press_on(confront_picture("neutral"),
             [[("You:", GOLD)], '"Forget it. I\'m sorry... I\'m just tired."'])
    if cheating:
        ending(confront_picture("happy"), "ENDING: BLISSFUL IGNORANCE",
               "\"Thanks, babe. Night.\" They kiss your forehead and turn off the lamp. In the dark, "
               "a phone you never found lights up: \"Can't wait to see you again.\"",
               "The truth: they were cheating.")
    else:
        ending(confront_picture("happy"), "ENDING: TRUST",
               "\"Come here. I know I've been working too much. Let's take Saturday off, just us.\" "
               "You let the doubts go.",
               "The truth: they were faithful all along. Best ending!")

def play():
    cheating = random.random() < CHEAT_CHANCE
    try:
        found = act_one(cheating)
        act_two(cheating, found)
    except BackToMenu:
        pass

def main():
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setraw(fd)   #read keys straight away without waiting for Enter
    try:
        while True:
            show(MENU, [[("SUSPICION", GOLD), ("   -   Press Enter to start", TEXT_FG)]], "Q to quit")
            key = get_key()
            if key == "enter":
                play()
            elif key == "q":
                break
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        sys.stdout.write(RESET + CLEAR)
        print("Thanks for playing!")

if __name__ == "__main__":
    main()
