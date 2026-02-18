import subprocess
import random
import math

import pygame  # type: ignore

# ==========================================================
# CONFIGURARE GLOBALĂ
# ==========================================================

CW, CH = 1080, 1920
FPS = 60

BG_COLOR = (255, 255, 255)

PLAYER_RADIUS = 30
DOT_RADIUS    = 15
EAT_DIST      = PLAYER_RADIUS + DOT_RADIUS  # distanță la care se mănâncă
DOT_MIN_DIST  = DOT_RADIUS * 2 + 10        # distanță minimă între centrele bilelor verzi

NUM_DOTS     = 501
PLAYER_SPEED = 750.0  # px / secundă

SCORE_AREA_H    = 160   # px rezervați sus pentru scor
PLAY_MARGIN     = 60    # margine față de borduri în zona de joc

SCORE_FONT_SIZE = 110
ICON_R          = 32    # raza iconiței din zona de scor

OUTRO_MOVE_SPEED  = 1000.0  # px/s — viteza cu care câștigătorul merge la centru
OUTRO_GROW_DUR    = 0.5    # secunde pentru creștere 1x → 10x
OUTRO_HOLD_DUR    = 1.0    # secunde de așteptare la 10x

RECORD_VIDEO = False
OUTPUT_MP4   = "output.mp4"
FFMPEG_PATH  = "ffmpeg"

# ==========================================================
# PERSONAJE ȘI IMAGINI
# ==========================================================
# Adaugă căile către imaginile PNG (fără fundal) ale celor 3 personaje.
# Imaginile pentru jucători sunt fețe de oameni; imaginea pentru bile e mâncare.

CHARACTERS = [
    {"name": "Personaj 1", "image": "images/char1.png"},
    {"name": "Personaj 2", "image": "images/char2.png"},
    {"name": "Personaj 3", "image": "images/char3.png"},
]

DOT_IMAGE_PATH = "images/food.png"

# ── Alege care 2 personaje concurează (indici 0, 1 sau 2) ─────────────────
# PLAYER_LEFT_IDX  → colț sus-stânga  (fostul Albastru)
# PLAYER_RIGHT_IDX → colț jos-dreapta (fostul Roșu)
PLAYER_LEFT_IDX  = 0
PLAYER_RIGHT_IDX = 1

# Culori text scor (rămân pentru cifre)
LEFT_SCORE_COLOR  = (30, 100, 220)
RIGHT_SCORE_COLOR = (220, 40, 40)

# ==========================================================


def load_square_img(path, size):
    """Încarcă un PNG cu canal alpha și îl scalează la size x size."""
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(img, (size, size))


def blit_centered(surface, img, cx, cy):
    """Blitează img centrat la coordonatele (cx, cy)."""
    half = img.get_width() // 2
    surface.blit(img, (cx - half, cy - half))


def start_ffmpeg():
    cmd = [
        FFMPEG_PATH, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{CW}x{CH}",
        "-r", str(FPS),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "veryfast",
        OUTPUT_MP4,
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def find_nearest(pos, dots):
    """Returnează indexul bilei verzi celei mai apropiate de pos."""
    best_idx = None
    best_d2  = float("inf")
    for i, dot in enumerate(dots):
        d2 = (pos[0] - dot[0]) ** 2 + (pos[1] - dot[1]) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_idx = i
    return best_idx


def move_toward(pos, target, speed, dt):
    """Mișcă pos spre target cu viteza dată; nu depășește target."""
    dx = target[0] - pos[0]
    dy = target[1] - pos[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return pos
    step = min(speed * dt, dist)
    return (pos[0] + dx / dist * step, pos[1] + dy / dist * step)


def main():
    pygame.init()

    info  = pygame.display.Info()
    scale = min((info.current_w * 0.92) / CW, (info.current_h * 0.92) / CH)
    win_w = max(320, int(CW * scale))
    win_h = max(568, int(CH * scale))

    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption("PvP Dots")
    clock = pygame.time.Clock()

    # ── Încărcare imagini (după set_mode, necesar pentru convert_alpha) ──
    D_PLAYER = PLAYER_RADIUS * 2
    D_DOT    = DOT_RADIUS * 2
    D_ICON   = ICON_R * 2

    left_img_player  = load_square_img(CHARACTERS[PLAYER_LEFT_IDX]["image"],  D_PLAYER)
    right_img_player = load_square_img(CHARACTERS[PLAYER_RIGHT_IDX]["image"], D_PLAYER)
    left_img_icon    = load_square_img(CHARACTERS[PLAYER_LEFT_IDX]["image"],  D_ICON)
    right_img_icon   = load_square_img(CHARACTERS[PLAYER_RIGHT_IDX]["image"], D_ICON)
    dot_img          = load_square_img(DOT_IMAGE_PATH, D_DOT)

    canvas     = pygame.Surface((CW, CH)).convert()
    font_score = pygame.font.SysFont("Arial", SCORE_FONT_SIZE, bold=True)

    # ── Zona de joc ────────────────────────────────────────
    play_left   = PLAY_MARGIN
    play_top    = SCORE_AREA_H + PLAY_MARGIN
    play_right  = CW - PLAY_MARGIN
    play_bottom = CH - PLAY_MARGIN

    # ── Poziții inițiale jucători ──────────────────────────
    # Stânga: colț sus-stânga   |   Dreapta: colț jos-dreapta
    left_pos  = [float(play_left  + PLAYER_RADIUS + 10),
                 float(play_top   + PLAYER_RADIUS + 10)]
    right_pos = [float(play_right - PLAYER_RADIUS - 10),
                 float(play_bottom - PLAYER_RADIUS - 10)]

    # ── Bile verzi (aleator în zona de joc, fără suprapunere) ─
    random.seed()
    dots = []
    min_dist_sq = DOT_MIN_DIST ** 2
    MAX_TRIES   = 2000   # dacă zona e prea aglomerată, plasăm fără constrângere
    while len(dots) < NUM_DOTS:
        for _ in range(MAX_TRIES):
            x = random.randint(play_left  + DOT_RADIUS + 5, play_right  - DOT_RADIUS - 5)
            y = random.randint(play_top   + DOT_RADIUS + 5, play_bottom - DOT_RADIUS - 5)
            if all((x - d[0]) ** 2 + (y - d[1]) ** 2 >= min_dist_sq for d in dots):
                dots.append([float(x), float(y)])
                break
        else:
            # Fallback: plasăm fără constrângere de distanță (zona saturată)
            x = random.randint(play_left  + DOT_RADIUS + 5, play_right  - DOT_RADIUS - 5)
            y = random.randint(play_top   + DOT_RADIUS + 5, play_bottom - DOT_RADIUS - 5)
            dots.append([float(x), float(y)])

    left_score  = 0
    right_score = 0

    # Faze: "intro" → "game" → "outro"
    phase       = "intro"
    intro_timer = 0.0
    INTRO_DUR   = 1.0   # secunde pentru apariția bilelor verzi

    game_over = False

    # Outro
    outro_phase    = None   # None | "move" | "grow" | "hold"
    winner_is_left = True
    winner_pos     = [0.0, 0.0]
    outro_radius   = float(PLAYER_RADIUS)
    outro_grow_t   = 0.0
    outro_hold_t   = 0.0
    SCREEN_CX, SCREEN_CY = CW // 2, CH // 2

    ff = start_ffmpeg() if RECORD_VIDEO else None

    running = True
    try:
        while running:
            frame_dt = clock.tick(FPS) / 1000.0

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    running = False

            # ── LOGICĂ JOC ───────────────────────────────────────
            if phase == "intro":
                intro_timer += frame_dt
                if intro_timer >= INTRO_DUR:
                    phase = "game"

            elif phase == "game" and not game_over:
                if dots:
                    # Stânga se mișcă
                    bi = find_nearest(left_pos, dots)
                    bt = dots[bi]
                    left_pos = list(move_toward(left_pos, bt, PLAYER_SPEED, frame_dt))
                    if math.hypot(left_pos[0] - bt[0], left_pos[1] - bt[1]) <= EAT_DIST:
                        dots.pop(bi)
                        left_score += 1

                    # Dreapta se mișcă (pe lista actualizată)
                    if dots:
                        ri = find_nearest(right_pos, dots)
                        rt = dots[ri]
                        right_pos = list(move_toward(right_pos, rt, PLAYER_SPEED, frame_dt))
                        if math.hypot(right_pos[0] - rt[0], right_pos[1] - rt[1]) <= EAT_DIST:
                            dots.pop(ri)
                            right_score += 1
                else:
                    game_over = True
                    # Stabilim câștigătorul
                    winner_is_left = (left_score >= right_score)
                    winner_pos     = list(left_pos if winner_is_left else right_pos)
                    outro_phase    = "move"
                    outro_radius   = float(PLAYER_RADIUS)

            elif outro_phase == "move":
                winner_pos = list(move_toward(winner_pos,
                                              (SCREEN_CX, SCREEN_CY),
                                              OUTRO_MOVE_SPEED, frame_dt))
                if math.hypot(winner_pos[0] - SCREEN_CX,
                              winner_pos[1] - SCREEN_CY) < 2.0:
                    winner_pos = [float(SCREEN_CX), float(SCREEN_CY)]
                    outro_phase = "grow"

            elif outro_phase == "grow":
                outro_grow_t += frame_dt
                t = min(outro_grow_t / OUTRO_GROW_DUR, 1.0)
                outro_radius = PLAYER_RADIUS * (1.0 + t * 9.0)   # 1x → 10x
                if t >= 1.0:
                    outro_phase = "hold"

            elif outro_phase == "hold":
                outro_hold_t += frame_dt
                if outro_hold_t >= OUTRO_HOLD_DUR:
                    running = False

            # ── RENDER ──────────────────────────────────────────
            canvas.fill(BG_COLOR)

            # Linie separatoare sub zona de scor
            pygame.draw.line(canvas, (200, 200, 200), (0, SCORE_AREA_H), (CW, SCORE_AREA_H), 3)

            # ── Scor: [img_dreapta] scor_dr - scor_st [img_stânga] ──
            ICON_Y = SCORE_AREA_H // 2
            GAP    = 24

            right_num_surf = font_score.render(str(right_score), True, RIGHT_SCORE_COLOR)
            left_num_surf  = font_score.render(str(left_score),  True, LEFT_SCORE_COLOR)
            dash_surf      = font_score.render("-", True, (120, 120, 120))

            total_w = (D_ICON + GAP
                       + right_num_surf.get_width()  + GAP
                       + dash_surf.get_width()        + GAP
                       + left_num_surf.get_width()    + GAP
                       + D_ICON)
            x = CW // 2 - total_w // 2

            blit_centered(canvas, right_img_icon, x + ICON_R, ICON_Y)
            x += D_ICON + GAP
            canvas.blit(right_num_surf, right_num_surf.get_rect(midleft=(x, ICON_Y)))
            x += right_num_surf.get_width() + GAP
            canvas.blit(dash_surf,      dash_surf.get_rect(midleft=(x, ICON_Y)))
            x += dash_surf.get_width() + GAP
            canvas.blit(left_num_surf,  left_num_surf.get_rect(midleft=(x, ICON_Y)))
            x += left_num_surf.get_width() + GAP
            blit_centered(canvas, left_img_icon, x + ICON_R, ICON_Y)

            # ── Bile de mâncare ──────────────────────────────────
            if phase == "intro":
                visible = int(min(intro_timer / INTRO_DUR, 1.0) * len(dots))
                draw_dots = dots[:visible]
            else:
                draw_dots = dots
            for dot in draw_dots:
                blit_centered(canvas, dot_img, int(dot[0]), int(dot[1]))

            # ── Jucători ────────────────────────────────────────
            if not game_over:
                blit_centered(canvas, left_img_player,
                              int(left_pos[0]),  int(left_pos[1]))
                blit_centered(canvas, right_img_player,
                              int(right_pos[0]), int(right_pos[1]))
            else:
                # Outro: pierzătorul rămâne pe loc, câștigătorul animat
                winner_img = left_img_player  if winner_is_left else right_img_player
                loser_img  = right_img_player if winner_is_left else left_img_player
                loser_pos  = right_pos        if winner_is_left else left_pos

                blit_centered(canvas, loser_img,
                              int(loser_pos[0]), int(loser_pos[1]))

                diam = max(1, int(outro_radius) * 2)
                scaled_winner = pygame.transform.smoothscale(winner_img, (diam, diam))
                blit_centered(canvas, scaled_winner,
                              int(winner_pos[0]), int(winner_pos[1]))

            # ── Afișare scalată pe ecran ─────────────────────────
            scaled = pygame.transform.smoothscale(canvas, screen.get_size())
            screen.blit(scaled, (0, 0))
            pygame.display.flip()

            # ── Înregistrare ffmpeg ─────────────────────────────
            if ff and ff.stdin:
                ff.stdin.write(pygame.image.tostring(canvas, "RGB"))

    finally:
        pygame.quit()
        if ff and ff.stdin:
            try:
                ff.stdin.close()
            except Exception:
                pass
            ff.wait()


if __name__ == "__main__":
    main()
