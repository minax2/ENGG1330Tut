import os, sys, tty, termios, shutil, struct, zlib, random, textwrap

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
TITLES = {name: load_png(f"art/title-{name}.png") for name in ("act1", "1030", "act2", "win", "lose")}
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
#every game, your partner is hiding ONE of these secrets
#each secret: name on the accuse menu, what you say, and how every ending plays out
#weight = % chance of that secret, they add up to 100

SECRETS = {
    "affair": {
        "name": "Cheating", "weight": 32,
        "truth": "they were cheating.",
        "accuse": "Stop lying to me. You're seeing someone, aren't you?",
        "confess": ("ENDING: THE TRUTH",
                    "They sink onto the edge of the bed and the excuses run out. \"Okay. Okay... "
                    "I've been seeing someone. I'm so sorry.\" It hurts, but you know the truth."),
        "deny": ("ENDING: NO PROOF",
                 "\"A few random things and you're calling me a cheater? You've got nothing!\" "
                 "They storm off to the couch. Somewhere under the bed, a phone buzzes."),
        "wrong": ("ENDING: WRONG TREE",
                  "\"What? No! That's insane.\" They laugh, a little too relieved, and kiss your "
                  "forehead. Later that night, a phone buzzes under the bed: \"Did they buy it?\""),
        "let_go": ("ENDING: BLISSFUL IGNORANCE",
                   "\"Thanks, babe. Night.\" They kiss your forehead and turn off the lamp. In the "
                   "dark, a phone you never found lights up: \"Can't wait to see you again.\""),
    },
    "surprise": {
        "name": "Planning something", "weight": 21,
        "truth": "they were planning to propose.",
        "accuse": "Stop lying to me. You're planning something behind my back.",
        "confess": ("ENDING: SURPRISE!",
                    "They throw their hands up, laughing. \"Fine! I was going to propose on "
                    "Saturday. You ruined it, you absolute detective.\" They pull out the ring anyway."),
        "deny": ("ENDING: ALMOST SPOILED",
                 "\"Planning something? Me? Nope. Nothing. Go to sleep.\" They're grinning way too "
                 "hard. You'll find out on Saturday, but the moment is already half spoiled."),
        "wrong": ("ENDING: RUINED SURPRISE",
                  "They stare at you, then set a small velvet box on the dresser. \"I was going to "
                  "ask you on Saturday. At the Lakeview Inn, where we had our first date.\" They "
                  "leave the box and walk out."),
        "let_go": ("ENDING: THE QUESTION",
                   "\"Get some sleep. Big weekend coming.\" On Saturday, at the Lakeview Inn where "
                   "you had your first date, they get down on one knee. Good thing you didn't make a scene."),
    },
    "jobless": {
        "name": "Lost their job", "weight": 21,
        "truth": "they had lost their job.",
        "accuse": "Stop lying to me. You don't have a job anymore, do you?",
        "confess": ("ENDING: THE TRUTH",
                    "They sink onto the bed. \"I got laid off three weeks ago. I've been pretending "
                    "to go to work every day. I'm so sorry.\" You hold them. You'll figure it out together."),
        "deny": ("ENDING: THE RENT BOUNCES",
                 "\"I didn't lose my job, okay? Drop it!\" They lock themselves in the bathroom. "
                 "You find out a month later, when the rent bounces."),
        "wrong": ("ENDING: ASHAMED",
                  "\"That's what you think of me?\" Their voice breaks. \"I lost my job three weeks "
                  "ago. I've been sitting in a diner every day because I was too ashamed to tell you.\""),
        "let_go": ("ENDING: KEEPING UP APPEARANCES",
                   "\"Night.\" They leave at 8 AM, briefcase and all. Six weeks later the savings "
                   "account hits zero, and the truth comes out in the worst possible way."),
    },
    "debt": {
        "name": "Gambling debt", "weight": 21,
        "truth": "they were drowning in gambling debt.",
        "accuse": "Stop lying to me. How much money do you owe?",
        "confess": ("ENDING: THE TRUTH",
                    "\"Forty thousand,\" they whisper. \"It started with one bet.\" It's a mess, but "
                    "it's out in the open now, and you can get them help."),
        "deny": ("ENDING: A KNOCK AT THE DOOR",
                 "\"Debt? Don't be dramatic, we're fine.\" They smile, too wide. The next week, a "
                 "man in a leather jacket knocks on the door asking for them by name."),
        "wrong": ("ENDING: WORSE THAN THAT",
                  "\"No. It's worse.\" They sit down heavily. \"I owe forty thousand dollars to "
                  "people who don't send letters. I thought I could win it back before you found out.\""),
        "let_go": ("ENDING: ALL IN",
                   "\"Night, babe.\" At 3 AM you wake to an empty bed and a text: \"Don't worry. "
                   "I'll win it all back tonight.\""),
    },
    "none": {
        "name": "Nothing", "weight": 5,
        "truth": "they were never hiding anything.",
        "wrong": ("ENDING: FALSE ACCUSATION",
                  "\"After everything... you really think that of me?\" Their voice breaks. They "
                  "pack a bag and leave to stay with a friend."),
        "let_go": ("ENDING: TRUST",
                   "\"Come here. I know I've been working too much. Let's take Saturday off, just "
                   "us.\" You let the doubts go."),
    },
}
ACCUSABLE = ["affair", "jobless", "debt", "surprise"]

#each spot has a few possible clues, "fits" = which secrets can leave that clue behind
#ANY clues are harmless and can turn up in every game
#replies = how they react to the clue, for each secret: (face, guilt, paranoia, what they say)
#tag = where the number goes on the bedroom picture
ANY = "any"

AREAS = [
    {"key": "1", "name": "Closet", "action": "CHECK CLOSET", "tag": (6, 9), "clues": [
        {"evidence": "Designer Silk Tie", "short": "Silk tie", "item": "tie",
         "fits": {"affair", "surprise"},
         "find": "You find a designer tie hanging behind your winter coats. It definitely "
                 "isn't yours. There is a faint whiff of expensive cologne you've never smelled before.",
         "say": "Care to explain why I found a designer silk tie behind the winter coats? "
                "It's not mine, and it smells like a cologne I've never bought.",
         "replies": {
            "affair": ("shocked", 2, 0,
                       "They freeze, eyes widening. 'Oh... uh, that? Wait, let me explain. A coworker "
                       "left it in the car after a ride-share and I just tossed it there... Look, "
                       "it's not what you think!'"),
            "surprise": ("nervous", 2, 0,
                         "They go red and snatch it off you. 'That's... for a thing. A work thing. "
                         "Can you please just stay out of the closet for a few more days?'")}},
        {"evidence": "Office ID Badge", "short": "ID badge", "item": "id-badge",
         "fits": {"jobless"},
         "find": "Their work tie is still knotted on its hanger, with their office ID badge "
                 "clipped to it. They said they badged in at 8 this morning.",
         "say": "Your office badge is hanging in the closet. How did you get into work today "
                "without it?",
         "replies": {
            "jobless": ("nervous", 3, 0,
                        "They hesitate a beat too long. 'Security knows me, they just wave me "
                        "through. It's fine. Why are you keeping track of my badge?'")}},
        {"evidence": "Old Dirty Hoodie", "short": "Old hoodie", "item": "hoodie",
         "fits": ANY,
         "find": "You find an old, oversized college hoodie stuffed in the back. It looks "
                 "entirely foreign; you're unsure if this is the hoodie they wore in college or not.",
         "say": "I found this old college hoodie stuffed way in the back of the closet. Is this "
                "yours and why are you keeping ratty old clothes?",
         "replies": {
            ANY: ("annoyed", 0, 2,
                  "They roll their eyes and laugh nervously. 'Seriously? You're interrogating me "
                  "over a college hoodie I've owned for five years? Are you hearing yourself right now?'")}}]},

    {"key": "2", "name": "Under bed", "action": "LOOK UNDER BED", "tag": (43, 32), "clues": [
        {"evidence": "Hidden Burner Phone", "short": "Burner phone", "item": "phone",
         "fits": {"affair", "debt"},
         "find": "Your hand finds an unfamiliar black smartphone by the baseboard. A text lights "
                 "up from an unsaved number: 'Friday. Same place. Don't make me wait again.'",
         "say": "I found a second phone under the bed. Someone just texted it: 'Friday. Same "
                "place. Don't make me wait again.' Who is that?",
         "replies": {
            "affair": ("shocked", 2, 0,
                       "Their face instantly drains of colour. Their voice stammers. 'Th-that's... "
                       "where did you even find that? It's an old phone for work, I swear, someone "
                       "must have left it-stop looking at me like that!'"),
            "debt": ("shocked", 2, 0,
                     "Their hands start shaking. 'Give me that. Please. If I miss Friday it gets "
                     "so much worse. You don't understand. Just give it back.'")}},
        {"evidence": "Gutted Photo Album", "short": "Photo album", "item": "album",
         "fits": {"surprise"},
         "find": "You pull out the photo album from your first year together. Half the photos "
                 "have been carefully peeled out.",
         "say": "Somebody's been pulling photos out of our album. Our photos. What are you doing "
                "with them?",
         "replies": {
            "surprise": ("happy", 2, 0,
                         "They try very hard not to smile. 'I... might have needed a few. For "
                         "reasons. You'll get them back, okay? Stop snooping!'")}},
        {"evidence": "Lost TV Remote", "short": "TV remote", "item": "tv-remote",
         "fits": ANY,
         "find": "Dust bunnies, one sock, and the TV remote you two have been blaming each other "
                 "for losing.",
         "say": "The TV remote was under the bed this whole time. Did you hide it there?",
         "replies": {
            ANY: ("annoyed", 0, 2,
                  "'Wow. You found the remote. Do you want a medal, or should I confess to "
                  "stealing it?'")}}]},

    {"key": "3", "name": "Bed sheets", "action": "EXAMINE SHEETS", "tag": (35, 24), "clues": [
        {"evidence": "Foreign Blonde Hair", "short": "Blonde hair", "item": "blonde-hair",
         "fits": {"affair", "none"},
         "find": "Tucked between the mattress and the headboard, you find a long, blonde hair "
                 "strand. Neither you nor your partner has blonde hair.",
         "say": "Tucked right against the headboard, I found a long blonde hair strand. Neither "
                "of us are blonde. Who was in our bed?",
         "replies": {
            "affair": ("angry", 1, 1,
                       "They cross their arms defensively. 'Are you serious? It's probably from a "
                       "coworker at the office or a customer interaction, people shed everywhere! "
                       "You're grasping at straws.'"),
            "none": ("annoyed", 0, 2,
                     "'My sister stayed over Saturday while you were at your mom's. She napped in "
                     "here. She's blonde. Call her if you want.'")}},
        {"evidence": "Pillow Feather", "short": "Feather", "item": "feather",
         "fits": ANY,
         "find": "You find a stray feather from the down pillow that's been leaking slightly "
                 "over the past week. Someone's been rushing the laundry.",
         "say": "The down pillow has been leaking feathers all over the sheets. Why aren't you "
                "taking care of the house?",
         "replies": {
            ANY: ("annoyed", 0, 2,
                  "They let out an exasperated sigh. 'It's a cheap pillow, it leaks! Is this "
                  "really what we're arguing about right now?'")}}]},

    {"key": "4", "name": "Bedside drawer", "action": "OPEN BEDSIDE DRAWER", "tag": (58, 23), "clues": [
        {"evidence": "Lakeview Inn Receipt", "short": "Inn receipt", "item": "motel-receipt",
         "fits": {"affair", "surprise"},
         "find": "Under some charging cables is a receipt from the Lakeview Inn, dated last "
                 "Tuesday, the night they said they were working late.",
         "say": "Why is there a receipt from the Lakeview Inn from last Tuesday? You told me you "
                "were working late.",
         "replies": {
            "affair": ("nervous", 2, 0,
                       "They bite their lip, struggling for words. 'That... okay, look, the office "
                       "conference room was booked, so we had to move a corporate client meeting to "
                       "a hotel lobby lounge. It's a business expense!'"),
            "surprise": ("nervous", 2, 0,
                         "'It's a deposit! For... ugh. You just had to look, didn't you? Don't "
                         "ask me what it's for. Please.'")}},
        {"evidence": "Diner Receipts", "short": "Diner receipts", "item": "diner-receipt",
         "fits": {"jobless"},
         "find": "A stack of receipts from the diner across town: 11:40 AM Monday, 11:15 AM "
                 "Tuesday, 12:05 PM Wednesday. Their office is an hour away.",
         "say": "You've eaten at the diner across town every lunchtime this week. Your office is "
                "an hour away. How?",
         "replies": {
            "jobless": ("sad", 3, 0,
                        "They stare at the receipts for a long moment. 'I've had a lot of "
                        "meetings out that way. Client stuff. Can we not do this tonight?'")}},
        {"evidence": "Unread Paperback", "short": "Paperback", "item": "paperback",
         "fits": ANY,
         "find": "Charging cables, hand cream, and a paperback whose bookmark has been stuck on "
                 "page 12 for six months.",
         "say": "You've been on page 12 of this book for six months. What have you been doing "
                "with your nights instead?",
         "replies": {
            ANY: ("annoyed", 0, 2,
                  "'Sleeping? Like a normal person? You're inventing a crime out of a book I'm "
                  "bad at reading.'")}}]},

    {"key": "5", "name": "Laundry", "action": "SEARCH LAUNDRY", "tag": (22, 31), "clues": [
        {"evidence": "Foreign Underwear", "short": "Underwear", "item": "underwear",
         "fits": {"affair"},
         "find": "At the bottom of the hamper, buried beneath towels, is a pair of underwear in a "
                 "brand and size you and your partner do not own.",
         "say": "At the bottom of the laundry hamper, buried under the towels, I found a pair of "
                "underwear that is definitely not mine or yours.",
         "replies": {
            "affair": ("nervous", 3, 0,
                       "They panic, stepping back. 'That's-ugh, that must have gotten mixed up in "
                       "the public laundromat dryer last week! It happens all the time!'")}},
        {"evidence": "Betting Slip", "short": "Betting slip", "item": "betting-slip",
         "fits": {"debt"},
         "find": "In a jeans pocket, washed half to pulp, is a betting slip: $500 on a horse "
                 "called Second Chance. It's dated yesterday.",
         "say": "This was in your jeans. $500 on a horse called Second Chance, yesterday. Since "
                "when do you bet?",
         "replies": {
            "debt": ("nervous", 3, 0,
                     "'A coworker put it on for me, as a joke. One time. Five hundred is "
                     "nothing, right? It's nothing.'")}},
        {"evidence": "Dirty Gym Clothes", "short": "Gym clothes", "item": "gym-clothes",
         "fits": ANY,
         "find": "You find your partner's gym clothes from a week ago, smelling faintly of "
                 "standard laundry detergent and sweat.",
         "say": "I checked the laundry and found your gym clothes from a week ago smelling like "
                "standard sweat. What are you trying to mask?",
         "replies": {
            ANY: ("annoyed", 0, 2,
                  "They sniff the air, looking offended. 'They smell like sweat because I went to "
                  "the gym! What do you want them to smell like, roses?'")}}]},

    {"key": "6", "name": "Vanity", "action": "CHECK DRESSER", "tag": (23, 21), "clues": [
        {"evidence": "Foreign Lipstick", "short": "J.K. lipstick", "item": "lipstick-jk",
         "fits": {"affair", "surprise"},
         "find": "Next to the perfume tray sits a custom silver lipstick with the initials "
                 "'J.K.' engraved. It definitely does not belong to you.",
         "say": "Next to your perfume tray, there's a custom silver lipstick with the initials "
                "'J.K.' engraved. Who is J.K.?",
         "replies": {
            "affair": ("nervous", 2, 0,
                       "They touch their face nervously. 'Oh, that's just... a brand sample a friend "
                       "gave me at brunch! Yeah, a friend!'"),
            "surprise": ("shocked", 2, 0,
                         "'Jess Kowalski? Your best friend? She came over Sunday to help me "
                         "with something. Call her. Actually, no, don't call her!'")}},
        {"evidence": "Pawn Shop Ticket", "short": "Pawn ticket", "item": "pawn-ticket",
         "fits": {"debt"},
         "find": "Under the jewellery box is a pawn shop ticket for one gold watch: the one "
                 "their grandfather left them.",
         "say": "Why is there a pawn ticket for your grandfather's watch under the jewellery box?",
         "replies": {
            "debt": ("sad", 3, 0,
                     "Their voice cracks. 'I'm getting it back. I just needed cash fast. It's "
                     "handled. I'm handling it.'")}},
        {"evidence": "Grocery Store Receipt", "short": "Grocery receipt", "item": "grocery-receipt",
         "fits": ANY,
         "find": "You find a standard tube of lipstick and a receipt from the local grocery store "
                 "for the weekly meat and vegetables.",
         "say": "I found a grocery store receipt for vegetables. Why are you hiding your shopping "
                "habits from me?",
         "replies": {
            ANY: ("happy", 0, 3,
                  "They burst out laughing, though it's tense. 'I bought meat and vegetables to "
                  "make dinner! Are carrots a red flag now?'")}}]},

    {"key": "7", "name": "Windowsill", "action": "INSPECT WINDOW", "tag": (38, 5), "clues": [
        {"evidence": "Outside Cigarette Butt", "short": "Cigarette", "item": "cigarette",
         "fits": {"affair", "debt"},
         "find": "Looking closely at the outside windowsill, you find a crushed cigarette "
                 "butt-even though neither of you smokes.",
         "say": "There's a fresh, crushed cigarette butt on the outside windowsill. Neither of us "
                "smokes. Who was standing outside our bedroom window?",
         "replies": {
            "affair": ("nervous", 1, 1,
                       "They blink rapidly. 'Um... maybe the apartment maintenance guy dropped it "
                       "while fixing the roof? Yeah, maintenance!'"),
            "debt": ("annoyed", 2, 0,
                     "They sigh and look away. 'Fine. I started again. It's been a stressful "
                     "month, okay? It's one cigarette.'")}},
        {"evidence": "Dust", "short": "Dust", "item": "dust",
         "fits": ANY,
         "find": "The window is locked tight, and you just find a light layer of dust and a "
                 "dead houseplant leaf.",
         "say": "The window is completely locked, and there's just a layer of dust. What are you "
                "keeping locked away?",
         "replies": {
            ANY: ("angry", 0, 3,
                  "'Dust? Really? It's an apartment window, it gets dusty! You're losing your mind.'")}}]},

    {"key": "8", "name": "Trash can", "action": "CHECK TRASH CAN", "tag": (64, 31), "clues": [
        {"evidence": "Handwritten Number Note", "short": "Number note", "item": "number-note",
         "fits": {"affair"},
         "find": "At the bottom lies a crumpled piece of paper with a handwritten phone number, "
                 "signed with a small heart doodle.",
         "say": "At the bottom of the trash, I found a crumpled paper with a handwritten phone "
                "number and a little heart doodle on it.",
         "replies": {
            "affair": ("sad", 2, 0,
                       "They look down at the floor, voice dropping. 'Someone handed it to me at the "
                       "coffee shop and I threw it away immediately! The fact that you're digging "
                       "through the trash is toxic.'")}},
        {"evidence": "Torn Letter", "short": "Torn letter", "item": "letter",
         "fits": {"jobless", "debt"},
         "find": "Torn into pieces is a letter on company letterhead. You can only make out "
                 "'...regret to inform you...' and '...effective immediately.'",
         "say": "I pieced together a letter from the trash. 'Regret to inform you, effective "
                "immediately.' What was that about?",
         "replies": {
            "jobless": ("sad", 3, 0,
                        "Their jaw tightens. 'It's nothing. A restructuring thing. Everybody got "
                        "one. Just leave it, please.'"),
            "debt": ("nervous", 2, 0,
                     "'It's from the bank. They closed my credit card. It's a paperwork mix-up, "
                     "I'll sort it out. Why are you going through the trash?'")}},
        {"evidence": "Coffee Cups", "short": "Coffee cups", "item": "coffee-cups",
         "fits": {"jobless", "none"},
         "find": "Six empty cups from the café downtown, all from this week. Your partner has "
                 "always been a tea person.",
         "say": "Six coffee cups from the café downtown, all this week. You don't even drink "
                "coffee.",
         "replies": {
            "jobless": ("nervous", 2, 0,
                        "'I just... sit there sometimes. It has good wifi. I get work done. Is "
                        "that a crime?'"),
            "none": ("annoyed", 0, 2,
                     "'I'm pulling late nights for the quarterly report. Coffee keeps me awake. "
                     "What's the big deal?'")}},
        {"evidence": "Takeout Menu", "short": "Takeout menu", "item": "takeout-menu",
         "fits": ANY,
         "find": "A takeout menu with curry circled, your partner curry to the guts, who did they eat it with?",
         "say": "Somebody circled the curry on this takeout menu. When did you order curry "
                "without me?",
         "replies": {
            ANY: ("annoyed", 0, 2,
                  "'We ordered that together. Last month. You picked it. Are you okay?'")}}]},

    {"key": "9", "name": "Laptop", "action": "CHECK DESK", "tag": (70, 22), "clues": [
        {"evidence": "Chat Log Snippet", "short": "Chat log", "item": "chat-log",
         "fits": {"affair"},
         "find": "The laptop is sitting open. A messaging app window was hastily minimized, "
                 "revealing a chat where someone calls your partner 'sweetheart' and talks "
                 "about 'booking a motel.'",
         "say": "Your laptop was left open. I saw a minimized messaging app where someone called "
                "you 'sweetheart' and talked about booking a motel.",
         "replies": {
            "affair": ("shocked", 2, 0,
                       "They completely freeze, panic setting in. 'You hacked into my laptop?! "
                       "Look... it was a joke, a friend from college was messing around, it doesn't "
                       "mean anything-!'")}},
        {"evidence": "Jeweller's Website", "short": "Ring website", "item": "ring-tab",
         "fits": {"affair", "surprise"},
         "find": "A browser tab is open on a jeweller's website, with a ring sitting in the "
                 "shopping cart.",
         "say": "Why is there a ring in a shopping cart on your laptop? Who is that for?",
         "replies": {
            "affair": ("nervous", 2, 0,
                       "'It's for my mom's birthday. She likes rings.' Their mom's birthday was "
                       "in March."),
            "surprise": ("shocked", 3, 0,
                         "'Oh no. No no no. Close it! Close the laptop! You weren't supposed to "
                         "see that yet!'")}},
        {"evidence": "Household Budget", "short": "Budget sheet", "item": "budget-sheet",
         "fits": {"debt", "jobless", "none"},
         "find": "The laptop is open to your household budget spreadsheet. Several totals are "
                 "highlighted in red.",
         "say": "Your laptop's open to our budget, and half of it is highlighted in red. What's "
                "going on with our money?",
         "replies": {
            "debt": ("nervous", 2, 0,
                     "They slam the laptop shut. 'It's a rough month. I moved some money around. "
                     "You don't need to look at that.'"),
            "jobless": ("sad", 2, 0,
                        "'I'm just checking how much we have saved. In general. Just in case. "
                        "Can't I plan ahead?'"),
            "none": ("angry", 0, 2,
                     "'The red is the electric bill, it went up again! I'm trying to keep us "
                     "afloat and you're snooping through my spreadsheets?'")}},
        {"evidence": "Cat Videos", "short": "Cat videos", "item": "cat-videos",
         "fits": ANY,
         "find": "A half-written work email and forty open tabs of cat videos.",
         "say": "Forty tabs of cat videos. Is this what 'working late' looks like?",
         "replies": {
            ANY: ("happy", 0, 2,
                  "'They're decompression videos. It's science. Are you seriously jealous of a "
                  "cat?'")}}]},

    {"key": "0", "name": "Shoe rack", "action": "CHECK SHOE RACK", "tag": (13, 31), "clues": [
        {"evidence": "Unknown Thigh-Highs", "short": "Thigh-highs", "item": "thigh-highs",
         "fits": {"affair"},
         "find": "Pushed behind your winter boots is a pair of thigh-highs that clearly don't "
                 "belong to you or your partner.",
         "say": "Pushed behind the winter boots is a pair of thigh-high stockings that belong to "
                "neither of us. Care to explain?",
         "replies": {
            "affair": ("nervous", 2, 0,
                       "They stammer, turning bright red. 'Those were... a costume piece! From a "
                       "party last year! They just got shoved back there!'")}},
        {"evidence": "Muddy Running Shoes", "short": "Muddy shoes", "item": "running-shoes",
         "fits": {"jobless", "none"},
         "find": "Their running shoes are caked in fresh mud and grass.",
         "say": "Why are your running shoes covered in fresh mud? Where have you been?",
         "replies": {
            "jobless": ("nervous", 2, 0,
                        "'I went for a walk at lunch. A long walk. Around the park. A few times. "
                        "It clears my head.'"),
            "none": ("annoyed", 0, 2,
                     "'The team did a hike for the offsite. I told you on Monday. Do you ever "
                     "listen to me?'")}},
        {"evidence": "Lone Flip-Flop", "short": "Flip-flop", "item": "flip-flop",
         "fits": ANY,
         "find": "Your boots, their slippers, and one lone flip-flop from last summer.",
         "say": "Where's the other flip-flop? What happened last summer?",
         "replies": {
            ANY: ("annoyed", 0, 2,
                  "'The ocean took it. You were there. You laughed for ten minutes.'")}}]},
]

#clues without a picture in art/items yet just show the empty spotlight
ITEMS = {}
for area in AREAS:
    for clue in area["clues"]:
        path = f"art/items/{clue['item']}.png"
        if os.path.exists(path):
            ITEMS[clue["item"]] = load_png(path)

CLUE_CHANCE = 0.85           #chance a spot holds a clue to the real secret
RED_HERRING_CHANCE = 0.6     #if they're hiding nothing, chance a spot looks suspicious anyway
MIN_TRACES = 6              #a real secret always leaves at least this many clues
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
    if clue["item"] not in ITEMS:
        return SPOTLIGHT
    return paste(SPOTLIGHT, scale_up(ITEMS[clue["item"]]), 24, 2)

def confront_picture(face, holding=None):
    picture = paste(CONFRONT_ROOM, FACES[face], 28, 6)
    if holding:
        picture = paste(picture, CARD, 5, 11)
        if holding in ITEMS:
            picture = paste(picture, ITEMS[holding], 7, 13)
    return picture

def meter_line(guilt, paranoia):
    g = min(guilt, METER_SIZE)
    p = min(paranoia * METER_SIZE // PARANOIA_MAX, METER_SIZE)
    return [("GUILT ", RED), ("█" * g, RED), ("░" * (METER_SIZE - g), GREY), ("     ", GREY),
            ("PARANOIA ", BLUE), ("█" * p, BLUE), ("░" * (METER_SIZE - p), GREY)]

def pick_secret():
    names = list(SECRETS)
    weights = [SECRETS[name]["weight"] for name in names]
    return random.choices(names, weights)[0]

def hide_clues(secret):
    #decide what is waiting in every spot before the search starts
    chance = RED_HERRING_CHANCE if secret == "none" else CLUE_CHANCE
    hidden = {}
    telling = {}
    for area in AREAS:
        plain = [c for c in area["clues"] if c["fits"] == ANY]
        options = [c for c in area["clues"] if c["fits"] != ANY and secret in c["fits"]]
        if options:
            telling[area["key"]] = options
        if options and random.random() < chance:
            hidden[area["key"]] = random.choice(options)
        else:
            hidden[area["key"]] = random.choice(plain)

    #make sure a real secret always leaves a trail to follow
    if secret != "none":
        found = [key for key in telling if hidden[key]["fits"] != ANY]
        spare = [key for key in telling if key not in found]
        random.shuffle(spare)
        while len(found) < MIN_TRACES and spare:
            key = spare.pop()
            hidden[key] = random.choice(telling[key])
            found.append(key)
    return hidden

#act 1

def act_one(secret):
    hidden = hide_clues(secret)

    press_on(LIVING_ROOM,
             ["It's 9:00 PM. Your phone buzzes. A text from your partner:",
              '"Working late again. Don\'t wait up."',
              "That's the third time this week. Something isn't right."])
    press_on(TITLES["act1"],
             [f"They'll be home at {clock(HOME_MINUTES)}. Each search takes {SEARCH_MINUTES} minutes.",
              "Search the bedroom and work out what they're hiding.",
              [("Another person? Money? Something else? Maybe nothing at all.", GREY)]])

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
                clue = hidden[key]
                found.append(clue)
                press_on(closeup_picture(clue),
                         ["> " + area["action"]] + wrap(clue["find"]) +
                         [[("Evidence gained: ", GREY), ("[" + clue["evidence"] + "]", GOLD)]])

    press_on(TITLES["1030"], ["You hear keys turning in the front door.", "They're home."])
    return found

#act 2

def ending(picture, title, story, truth):
    lines = [[(title, GOLD)]] + wrap(story)[:5] + [[(truth, GREY)]]
    press_on(picture, lines, "Press any key")

def truth_line(secret):
    return "The truth: " + SECRETS[secret]["truth"]

def act_two(secret, found):
    press_on(TITLES["act2"],
             ["Show them what you found. Each clue makes a meter rise:",
              [("GUILT", RED), (" if it hits home, ", TEXT_FG), ("PARANOIA", BLUE),
               (" if it makes you look crazy.", TEXT_FG)],
              f"Guilt {CONFESS_AT}+ and the right accusation makes them crack.",
              "Full paranoia and they walk out."])

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
            accused = choose_accusation(face, guilt, paranoia)
            if accused:
                return accuse(secret, accused, guilt)
            continue
        if key == "t":
            return let_it_go(secret)
        if not key.isdigit() or not 1 <= int(key) <= len(clues):
            continue

        clue = clues.pop(int(key) - 1)
        press_on(confront_picture(face, clue["item"]),
                 [meter_line(guilt, paranoia), [("You:", GOLD)]] + wrap('"' + clue["say"] + '"'))
        #how they react depends on what they are really hiding
        replies = clue["replies"]
        face, add_guilt, add_paranoia, reply = replies.get(secret, replies.get(ANY))
        guilt += add_guilt
        paranoia += add_paranoia
        change = []
        if add_guilt:
            change.append((f"GUILT +{add_guilt}   ", RED))
        if add_paranoia:
            change.append((f"PARANOIA +{add_paranoia}", BLUE))
        press_on(confront_picture(face, clue["item"]),
                 [meter_line(guilt, paranoia)] + wrap(reply)[:5] + [change])
        said = reply

        if paranoia >= PARANOIA_MAX:
            ending(EMPTY_DOORWAY, "ENDING: THE DOOR SLAMS",
                   '"I can\'t do this anymore. You tore the bedroom apart and now you\'re '
                   'interrogating me over nothing." They grab their keys. The front door slams.',
                   truth_line(secret))
            return False

def choose_accusation(face, guilt, paranoia):
    #returns the secret you accuse them of, or None to go back
    options = []
    for i, name in enumerate(ACCUSABLE):
        options += [(f"{i + 1} ", GOLD), (SECRETS[name]["name"] + "    ", TEXT_FG)]
    lines = [meter_line(guilt, paranoia),
             "What are they hiding?",
             options[:4], options[4:],
             [("B ", GOLD), ("Back", TEXT_FG)]]
    while True:
        show(confront_picture(face), lines, "Press a number to accuse")
        key = get_key()
        if key == "b":
            return None
        if key.isdigit() and 1 <= int(key) <= len(ACCUSABLE):
            return ACCUSABLE[int(key) - 1]

def accuse(secret, accused, guilt):
    #you only win if you guessed right AND they confess
    press_on(confront_picture("neutral"),
             [[("You:", GOLD)]] + wrap('"' + SECRETS[accused]["accuse"] + '"'))
    if accused == secret and guilt >= CONFESS_AT:
        title, story = SECRETS[secret]["confess"]
        ending(confront_picture("sad"), title, story, "You saw through every lie.")
        return True
    elif accused == secret:
        title, story = SECRETS[secret]["deny"]
        ending(confront_picture("angry"), title, story, "You guessed right, but they didn't crack.")
        return False
    else:
        title, story = SECRETS[secret]["wrong"]
        ending(confront_picture("sad"), title, story, truth_line(secret))
        return False

def let_it_go(secret):
    press_on(confront_picture("neutral"),
             [[("You:", GOLD)], '"Forget it. I\'m sorry... I\'m just tired."'])
    title, story = SECRETS[secret]["let_go"]
    truth = truth_line(secret)
    if secret in ("none", "surprise"):
        truth += " Best ending!"
    ending(confront_picture("happy"), title, story, truth)
    return secret in ("none", "surprise")

def play():
    #keeps starting new games until the player goes back to the menu
    while True:
        secret = pick_secret()
        try:
            found = act_one(secret)
            won = act_two(secret, found)
        except BackToMenu:
            return

        if won:
            show(TITLES["win"], "Well done, detective.", "Press any key to play again  |  F for menu")
        else:
            show(TITLES["lose"], "Better luck next time.", "Press any key to play again  |  F for menu")
        if get_key() == "f":
            return

def main():
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setraw(fd)   #read keys straight away without waiting for Enter
    try:
        while True:
            show(MENU, [[("GUESS THEIR SECRET", GOLD), ("   -   Press Enter to start", TEXT_FG)]], "Q to quit")
            key = get_key()
            if key == "enter":
                play()
            elif key == "q":
                break
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        sys.stdout.write(RESET + CLEAR)
        print("Thanks for playing!")

if __name__ == "__main__":
    main()