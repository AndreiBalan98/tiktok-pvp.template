import subprocess
import collections
import random

import pygame  # type: ignore

# ==========================================================
# CONFIGURARE GLOBALĂ
# ==========================================================

CW, CH = 1080, 1920
FPS = 60

BG_COLOR         = (255, 255, 255)
SNAKE_HEAD_COLOR = (20, 90, 20)    # verde închis — cap
SNAKE_TAIL_COLOR = (144, 238, 144) # verde deschis — coadă
APPLE_COLOR      = (210, 40, 40)
SCORE_COLOR      = (20, 20, 20)

GRID_COLS = 10
GRID_ROWS = 15

GRID_MARGIN_TOP    = 160   # px spațiu sus pentru scor
GRID_MARGIN_BOTTOM = 60
GRID_MARGIN_LEFT   = 30
GRID_MARGIN_RIGHT  = 30

CELL_RADIUS_RATIO = 0.5   # raza cerc față de jumătate celulă (0–1)
SNAKE_SPEED       = 25.0   # celule / secundă

SCORE_FONT_SIZE = 120
GAME_OVER_PAUSE = 1.0      # secunde înainte de închidere după game-over

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


def spawn_apple(snake_set, cols, rows):
    free = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in snake_set]
    return random.choice(free) if free else None


def bfs_path(head, apple, obstacles, cols, rows):
    """BFS shortest path de la head la apple, evitând obstacles.
    Returnează lista de pași (dr, dc) sau None dacă nu există drum."""
    queue = collections.deque()
    queue.append((head, []))
    visited = {head}
    while queue:
        (r, c), path = queue.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            npos = (nr, nc)
            if 0 <= nr < rows and 0 <= nc < cols and npos not in visited and npos not in obstacles:
                if npos == apple:
                    return path + [(dr, dc)]
                visited.add(npos)
                queue.append((npos, path + [(dr, dc)]))
    return None


def simulate_path(snake_deque, path, apple):
    """Simulează urmarea unui traseu BFS, returnând (deque_nou, set_nou)."""
    sim = collections.deque(snake_deque)
    sim_set = set(snake_deque)
    for dr, dc in path:
        new_head = (sim[0][0] + dr, sim[0][1] + dc)
        sim.appendleft(new_head)
        sim_set.add(new_head)
        if new_head != apple:
            tail = sim.pop()
            sim_set.discard(tail)
    return sim, sim_set


def get_next_step(snake, snake_set, apple, cols, rows):
    """Returnează (dr, dc) pentru pasul următor folosind safe path + tail chasing."""
    head = snake[0]
    tail = snake[-1]

    # Nivel 1 — Drum sigur spre măr
    obstacles = snake_set - {head}
    path_to_apple = bfs_path(head, apple, obstacles, cols, rows)

    if path_to_apple:
        sim_snake, sim_set = simulate_path(snake, path_to_apple, apple)
        sim_head = sim_snake[0]
        sim_tail = sim_snake[-1]
        sim_obstacles = sim_set - {sim_head} - {sim_tail}
        path_to_sim_tail = bfs_path(sim_head, sim_tail, sim_obstacles, cols, rows)
        if path_to_sim_tail:
            return path_to_apple[0]

    # Nivel 2 — Urmărire coadă
    obstacles_no_tail = snake_set - {head} - {tail}
    path_to_tail = bfs_path(head, tail, obstacles_no_tail, cols, rows)
    if path_to_tail:
        return path_to_tail[0]

    # Nivel 3 — Orice mișcare validă
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = head[0] + dr, head[1] + dc
        if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in obstacles:
            return (dr, dc)

    return None


def main():
    pygame.init()

    info = pygame.display.Info()
    scale = min((info.current_w * 0.92) / CW, (info.current_h * 0.92) / CH)
    win_w = max(320, int(CW * scale))
    win_h = max(568, int(CH * scale))

    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption("Snake")
    clock = pygame.time.Clock()

    canvas = pygame.Surface((CW, CH)).convert()
    font = pygame.font.SysFont("Arial", SCORE_FONT_SIZE, bold=True)

    grid_w = CW - GRID_MARGIN_LEFT - GRID_MARGIN_RIGHT
    grid_h = CH - GRID_MARGIN_TOP - GRID_MARGIN_BOTTOM
    cell_w = grid_w / GRID_COLS
    cell_h = grid_h / GRID_ROWS
    radius = int(min(cell_w, cell_h) * CELL_RADIUS_RATIO)

    def cell_center(r, c):
        x = GRID_MARGIN_LEFT + (c + 0.5) * cell_w
        y = GRID_MARGIN_TOP + (r + 0.5) * cell_h
        return int(x), int(y)

    # Stare joc
    sr, sc = GRID_ROWS // 2, GRID_COLS // 2
    snake = collections.deque([(sr, sc)])
    snake_set = {(sr, sc)}
    score = 0
    move_acc = 0.0

    apple = spawn_apple(snake_set, GRID_COLS, GRID_ROWS)
    game_over = False
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
                move_acc += frame_dt
                step_t = 1.0 / SNAKE_SPEED

                while move_acc >= step_t and not game_over:
                    move_acc -= step_t

                    step = get_next_step(snake, snake_set, apple, GRID_COLS, GRID_ROWS)
                    if step is None:
                        game_over = True
                        break

                    dr, dc = step
                    head = snake[0]
                    new_head = (head[0] + dr, head[1] + dc)
                    ate = (new_head == apple)

                    snake.appendleft(new_head)
                    snake_set.add(new_head)

                    if ate:
                        score += 1
                        apple = spawn_apple(snake_set, GRID_COLS, GRID_ROWS)
                        if apple is None:
                            game_over = True  # grid plin
                    else:
                        snake_set.discard(snake.pop())
            else:
                game_over_timer += frame_dt
                if game_over_timer >= GAME_OVER_PAUSE:
                    running = False

            # ── RENDER ──────────────────────────────────────────
            canvas.fill(BG_COLOR)

            # Scor (sus centru)
            score_surf = font.render(str(score), True, SCORE_COLOR)
            score_rect = score_surf.get_rect(midtop=(CW // 2, 30))
            canvas.blit(score_surf, score_rect)

            # Măr
            if apple:
                pygame.draw.circle(canvas, APPLE_COLOR, cell_center(*apple), radius)

            # Corp șarpe (gradient cap→coadă)
            n = len(snake)
            for i, seg in enumerate(snake):
                t = i / (n - 1) if n > 1 else 0
                color = (
                    int(SNAKE_HEAD_COLOR[0] + t * (SNAKE_TAIL_COLOR[0] - SNAKE_HEAD_COLOR[0])),
                    int(SNAKE_HEAD_COLOR[1] + t * (SNAKE_TAIL_COLOR[1] - SNAKE_HEAD_COLOR[1])),
                    int(SNAKE_HEAD_COLOR[2] + t * (SNAKE_TAIL_COLOR[2] - SNAKE_HEAD_COLOR[2])),
                )
                pygame.draw.circle(canvas, color, cell_center(*seg), radius)

            # Afișare scalată
            scaled = pygame.transform.smoothscale(canvas, screen.get_size())
            screen.blit(scaled, (0, 0))
            pygame.display.flip()

            # Înregistrare
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
