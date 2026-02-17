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

PLAYER_RADIUS = 38
DOT_RADIUS    = 14
EAT_DIST      = PLAYER_RADIUS + DOT_RADIUS  # distanță la care se mănâncă

NUM_DOTS     = 101
PLAYER_SPEED = 500.0  # px / secundă

SCORE_AREA_H    = 160   # px rezervați sus pentru scor
PLAY_MARGIN     = 60    # margine față de borduri în zona de joc

SCORE_FONT_SIZE = 110
LABEL_FONT_SIZE = 58

GAME_OVER_PAUSE = 1.0   # secunde pauză după terminare

RECORD_VIDEO = True
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

    canvas      = pygame.Surface((CW, CH)).convert()
    font_score  = pygame.font.SysFont("Arial", SCORE_FONT_SIZE, bold=True)
    font_label  = pygame.font.SysFont("Arial", LABEL_FONT_SIZE, bold=True)

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

    # ── Bile verzi (aleator în zona de joc) ────────────────
    random.seed()
    dots = []
    while len(dots) < NUM_DOTS:
        x = random.randint(play_left + DOT_RADIUS + 5, play_right  - DOT_RADIUS - 5)
        y = random.randint(play_top  + DOT_RADIUS + 5, play_bottom - DOT_RADIUS - 5)
        dots.append([float(x), float(y)])

    blue_score = 0
    red_score  = 0

    game_over       = False
    game_over_timer = 0.0

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
            if not game_over:
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
            else:
                game_over_timer += frame_dt
                if game_over_timer >= GAME_OVER_PAUSE:
                    running = False

            # ── RENDER ──────────────────────────────────────────
            canvas.fill(BG_COLOR)

            # Linie separatoare sub zona de scor
            pygame.draw.line(canvas, (200, 200, 200), (0, SCORE_AREA_H), (CW, SCORE_AREA_H), 3)

            # ── Scor sus (stânga = albastru, dreapta = roșu) ──
            ICON_R  = 22
            ICON_Y  = SCORE_AREA_H // 2

            # Albastru: icon + scor pe stânga
            pygame.draw.circle(canvas, BLUE_COLOR, (50, ICON_Y), ICON_R)
            blue_lbl  = font_label.render("BLUE", True, BLUE_COLOR)
            blue_lbl_rect = blue_lbl.get_rect(midleft=(82, ICON_Y - 22))
            canvas.blit(blue_lbl, blue_lbl_rect)
            blue_num  = font_score.render(str(blue_score), True, BLUE_COLOR)
            blue_num_rect = blue_num.get_rect(midleft=(82, ICON_Y + 22))
            canvas.blit(blue_num, blue_num_rect)

            # Roșu: scor + icon pe dreapta
            red_lbl  = font_label.render("RED", True, RED_COLOR)
            red_lbl_rect = red_lbl.get_rect(midright=(CW - 82, ICON_Y - 22))
            canvas.blit(red_lbl, red_lbl_rect)
            red_num  = font_score.render(str(red_score), True, RED_COLOR)
            red_num_rect = red_num.get_rect(midright=(CW - 82, ICON_Y + 22))
            canvas.blit(red_num, red_num_rect)
            pygame.draw.circle(canvas, RED_COLOR, (CW - 50, ICON_Y), ICON_R)

            # ── Bile verzi ──────────────────────────────────────
            for dot in dots:
                pygame.draw.circle(canvas, DOT_COLOR, (int(dot[0]), int(dot[1])), DOT_RADIUS)

            # ── Jucători ────────────────────────────────────────
            pygame.draw.circle(canvas, BLUE_COLOR,
                               (int(blue_pos[0]), int(blue_pos[1])), PLAYER_RADIUS)
            pygame.draw.circle(canvas, RED_COLOR,
                               (int(red_pos[0]),  int(red_pos[1])),  PLAYER_RADIUS)

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
