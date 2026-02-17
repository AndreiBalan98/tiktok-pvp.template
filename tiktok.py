import subprocess
import random
import math

import pygame  # type: ignore

# ==========================================================
# CONFIGURARE GLOBALĂ
# ==========================================================

CW, CH = 1080, 1920
FPS = 60

BG_COLOR   = (255, 255, 255)
BLUE_COLOR = (30, 100, 220)
RED_COLOR  = (220, 40, 40)
DOT_COLOR  = (50, 190, 70)

PLAYER_RADIUS = 30
DOT_RADIUS    = 15
EAT_DIST      = PLAYER_RADIUS + DOT_RADIUS  # distanță la care se mănâncă
DOT_MIN_DIST  = DOT_RADIUS * 2 + 10        # distanță minimă între centrele bilelor verzi

NUM_DOTS     = 501
PLAYER_SPEED = 750.0  # px / secundă

SCORE_AREA_H    = 160   # px rezervați sus pentru scor
PLAY_MARGIN     = 60    # margine față de borduri în zona de joc

SCORE_FONT_SIZE = 110

OUTRO_MOVE_SPEED  = 760.0  # px/s — viteza cu care câștigătorul merge la centru
OUTRO_GROW_DUR    = 1.5    # secunde pentru creștere 1x → 10x
OUTRO_HOLD_DUR    = 1.0    # secunde de așteptare la 10x

RECORD_VIDEO = False
OUTPUT_MP4   = "output.mp4"
FFMPEG_PATH  = "ffmpeg"

# ==========================================================


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

    canvas     = pygame.Surface((CW, CH)).convert()
    font_score = pygame.font.SysFont("Arial", SCORE_FONT_SIZE, bold=True)

    # ── Zona de joc ────────────────────────────────────────
    play_left   = PLAY_MARGIN
    play_top    = SCORE_AREA_H + PLAY_MARGIN
    play_right  = CW - PLAY_MARGIN
    play_bottom = CH - PLAY_MARGIN

    # ── Poziții inițiale jucători ──────────────────────────
    # Albastru: colț sus-stânga   |   Roșu: colț jos-dreapta
    blue_pos = [float(play_left  + PLAYER_RADIUS + 10),
                float(play_top   + PLAYER_RADIUS + 10)]
    red_pos  = [float(play_right - PLAYER_RADIUS - 10),
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

    blue_score = 0
    red_score  = 0

    # Faze: "intro" → "game" → "outro"
    phase       = "intro"
    intro_timer = 0.0
    INTRO_DUR   = 1.0   # secunde pentru apariția bilelor verzi

    game_over = False

    # Outro
    outro_phase   = None   # None | "move" | "grow" | "hold"
    winner_color  = None
    winner_pos    = [0.0, 0.0]
    outro_radius  = float(PLAYER_RADIUS)
    outro_grow_t  = 0.0
    outro_hold_t  = 0.0
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
                    # Albastru se mișcă
                    bi = find_nearest(blue_pos, dots)
                    bt = dots[bi]
                    blue_pos = list(move_toward(blue_pos, bt, PLAYER_SPEED, frame_dt))
                    if math.hypot(blue_pos[0] - bt[0], blue_pos[1] - bt[1]) <= EAT_DIST:
                        dots.pop(bi)
                        blue_score += 1

                    # Roșu se mișcă (pe lista actualizată)
                    if dots:
                        ri = find_nearest(red_pos, dots)
                        rt = dots[ri]
                        red_pos = list(move_toward(red_pos, rt, PLAYER_SPEED, frame_dt))
                        if math.hypot(red_pos[0] - rt[0], red_pos[1] - rt[1]) <= EAT_DIST:
                            dots.pop(ri)
                            red_score += 1
                else:
                    game_over = True
                    # Stabilim câștigătorul
                    if blue_score >= red_score:
                        winner_color = BLUE_COLOR
                        winner_pos   = list(blue_pos)
                    else:
                        winner_color = RED_COLOR
                        winner_pos   = list(red_pos)
                    outro_phase  = "move"
                    outro_radius = float(PLAYER_RADIUS)

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

            # ── Scor tip fotbal: 🔴 scor_rosu - scor_albastru 🔵 ──
            ICON_R = 32
            ICON_Y = SCORE_AREA_H // 2
            GAP    = 24

            red_num_surf  = font_score.render(str(red_score),  True, RED_COLOR)
            blue_num_surf = font_score.render(str(blue_score), True, BLUE_COLOR)
            dash_surf     = font_score.render("-", True, (120, 120, 120))

            total_w = (ICON_R * 2 + GAP
                       + red_num_surf.get_width()  + GAP
                       + dash_surf.get_width()      + GAP
                       + blue_num_surf.get_width()  + GAP
                       + ICON_R * 2)
            x = CW // 2 - total_w // 2

            pygame.draw.circle(canvas, RED_COLOR,  (x + ICON_R, ICON_Y), ICON_R)
            x += ICON_R * 2 + GAP
            canvas.blit(red_num_surf,  red_num_surf.get_rect(midleft=(x, ICON_Y)))
            x += red_num_surf.get_width() + GAP
            canvas.blit(dash_surf,     dash_surf.get_rect(midleft=(x, ICON_Y)))
            x += dash_surf.get_width() + GAP
            canvas.blit(blue_num_surf, blue_num_surf.get_rect(midleft=(x, ICON_Y)))
            x += blue_num_surf.get_width() + GAP
            pygame.draw.circle(canvas, BLUE_COLOR, (x + ICON_R, ICON_Y), ICON_R)

            # ── Bile verzi ──────────────────────────────────────
            if phase == "intro":
                visible = int(min(intro_timer / INTRO_DUR, 1.0) * len(dots))
                draw_dots = dots[:visible]
            else:
                draw_dots = dots
            for dot in draw_dots:
                pygame.draw.circle(canvas, DOT_COLOR, (int(dot[0]), int(dot[1])), DOT_RADIUS)

            # ── Jucători ────────────────────────────────────────
            if not game_over:
                pygame.draw.circle(canvas, BLUE_COLOR,
                                   (int(blue_pos[0]), int(blue_pos[1])), PLAYER_RADIUS)
                pygame.draw.circle(canvas, RED_COLOR,
                                   (int(red_pos[0]),  int(red_pos[1])),  PLAYER_RADIUS)
            else:
                # Outro: pierzătorul rămâne pe loc, câștigătorul animat
                loser_color = BLUE_COLOR if winner_color == RED_COLOR else RED_COLOR
                loser_pos   = blue_pos   if winner_color == RED_COLOR else red_pos
                pygame.draw.circle(canvas, loser_color,
                                   (int(loser_pos[0]), int(loser_pos[1])), PLAYER_RADIUS)
                pygame.draw.circle(canvas, winner_color,
                                   (int(winner_pos[0]), int(winner_pos[1])),
                                   int(outro_radius))

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
