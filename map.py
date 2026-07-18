import pygame
import random
import sys
import heapq

# --- การตั้งค่าพื้นฐาน ---
CELL_SIZE = 20
COLS, ROWS = 30, 30
MAZE_WIDTH = COLS * CELL_SIZE
HEIGHT = ROWS * CELL_SIZE
SIDEBAR_WIDTH = 250
UI_HEIGHT = 100
SCREEN_WIDTH = MAZE_WIDTH + SIDEBAR_WIDTH
SCREEN_HEIGHT = HEIGHT + UI_HEIGHT
FPS = 120 
STEPS_PER_FRAME = 5 

BG_COLOR = (15, 15, 30)         
UI_BG_COLOR = (25, 25, 45)      
LOG_BG_COLOR = (20, 20, 35)     
WALL_COLOR = (0, 255, 200)      
CHEESE_COLOR = (255, 200, 0)    
PATH_COLOR = (100, 70, 150)     
PLAN_COLOR = (255, 150, 0)      
TEXT_WHITE = (230, 230, 240)
TEXT_HIGHLIGHT = (0, 255, 200)
PRUNED_COLOR = (60, 20, 30)     

# สีของตัวหนู
MOUSE_BODY = (220, 220, 230)
MOUSE_PARTS = (255, 50, 150)

# ทิศทาง (N, E, S, W)
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
DIR_NAMES = ['North', 'East', 'South', 'West']
OPPOSITE = [2, 3, 0, 1]

action_log = []
MAX_LOGS = (HEIGHT - 40) // 20

def add_log(text):
    print(text)
    action_log.append(text)
    if len(action_log) > MAX_LOGS:
        action_log.pop(0)

class Cell:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.walls = [True, True, True, True]
        self.visited = False

def generate_maze():
    grid = [[Cell(x, y) for y in range(ROWS)] for x in range(COLS)]
    start_x, start_y = 0, 0
    grid[start_x][start_y].visited = True
    
    walls = []
    for i, (dx, dy) in enumerate(DIRS):
        nx, ny = start_x + dx, start_y + dy
        if 0 <= nx < COLS and 0 <= ny < ROWS:
            walls.append((start_x, start_y, i, nx, ny, OPPOSITE[i]))
            
    while walls:
        idx = random.randint(0, len(walls) - 1)
        cx, cy, dir_idx, nx, ny, opp_dir = walls.pop(idx)
        
        next_cell = grid[nx][ny]
        if not next_cell.visited:
            grid[cx][cy].walls[dir_idx] = False
            next_cell.walls[opp_dir] = False
            next_cell.visited = True
            
            for i, (dx, dy) in enumerate(DIRS):
                nnx, nny = nx + dx, ny + dy
                if 0 <= nnx < COLS and 0 <= nny < ROWS and not grid[nnx][nny].visited:
                    walls.append((nx, ny, i, nnx, nny, OPPOSITE[i]))
                    
    for x in range(COLS):
        for y in range(ROWS):
            grid[x][y].visited = False
            
    return grid

class Mouse:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.facing = 1 
        self.path = [(0, 0)] 
        self.planned_path = []
        self.pruned_cells = set() 
        
        self.known_walls = [[[False]*4 for _ in range(ROWS)] for _ in range(COLS)]
        for x in range(COLS):
            for y in range(ROWS):
                if y == 0: self.known_walls[x][y][0] = True
                if x == COLS-1: self.known_walls[x][y][1] = True
                if y == ROWS-1: self.known_walls[x][y][2] = True
                if x == 0: self.known_walls[x][y][3] = True
                
        self.target = (COLS-1, ROWS-1)
        self.calculate_smart_a_star()
        self.next_dir = None

    def look_ahead(self, real_maze):
        cx, cy = self.x, self.y
        changed = False
        path_blocked = False 
        
        for step in range(5): # ระยะการมองเห็น
            has_wall = real_maze[cx][cy].walls[self.facing]
            if self.known_walls[cx][cy][self.facing] != has_wall:
                self.known_walls[cx][cy][self.facing] = has_wall
                nx, ny = cx + DIRS[self.facing][0], cy + DIRS[self.facing][1]
                if 0 <= nx < COLS and 0 <= ny < ROWS:
                    self.known_walls[nx][ny][OPPOSITE[self.facing]] = has_wall
                changed = True
                
                # ถ้ากำแพงที่เจอใหม่ ขวางทางที่วางแผนไว้พอดี ให้คำนวณใหม่
                if self.planned_path and (nx, ny) in self.planned_path:
                    path_blocked = True
            
            if has_wall:
                break
                
            cx += DIRS[self.facing][0]
            cy += DIRS[self.facing][1]
            if not (0 <= cx < COLS and 0 <= cy < ROWS):
                break
                
        if changed:
            self.prune_dead_ends() 

            if path_blocked or not self.planned_path:
                self.calculate_smart_a_star()

    def prune_dead_ends(self):
        changed = True
        while changed:
            changed = False
            for x in range(COLS):
                for y in range(ROWS):
                    if (x, y) == (self.x, self.y) or (x, y) == self.target or (x, y) == (0, 0):
                        continue
                    if (x, y) in self.pruned_cells:
                        continue
                        
                    wall_count = sum(self.known_walls[x][y])
                    if wall_count >= 3:
                        self.pruned_cells.add((x, y))
                        changed = True
                        
                        for i in range(4):
                            if not self.known_walls[x][y][i]:
                                self.known_walls[x][y][i] = True
                                nx, ny = x + DIRS[i][0], y + DIRS[i][1]
                                if 0 <= nx < COLS and 0 <= ny < ROWS:
                                    self.known_walls[nx][ny][OPPOSITE[i]] = True

    def calculate_smart_a_star(self):
        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])
            
        start_state = (self.x, self.y, self.facing)
        goal_pos = self.target
        
        open_set = []
        heapq.heappush(open_set, (0, start_state))
        
        came_from = {}
        g_score = { start_state: 0 }
        
        while open_set:
            current_f, current_state = heapq.heappop(open_set)
            cx, cy, cfacing = current_state
            
            if (cx, cy) == goal_pos:
                path = []
                curr = current_state
                while curr in came_from:
                    path.append((curr[0], curr[1]))
                    curr = came_from[curr]
                path.reverse()
                self.planned_path = path
                return
                
            for i in range(4):
                if not self.known_walls[cx][cy][i]:
                    nx, ny = cx + DIRS[i][0], cy + DIRS[i][1]
                    if 0 <= nx < COLS and 0 <= ny < ROWS and (nx, ny) not in self.pruned_cells:
                        turn_cost = 0 if i == cfacing else 1.5 
                        tentative_g_score = g_score[current_state] + 1 + turn_cost
                        
                        next_state = (nx, ny, i)
                        if tentative_g_score < g_score.get(next_state, float('inf')):
                            came_from[next_state] = current_state
                            g_score[next_state] = tentative_g_score
                            f = tentative_g_score + heuristic((nx, ny), goal_pos)
                            heapq.heappush(open_set, (f, next_state))
                            
        self.planned_path = []

    def decide_next_move(self):
        if not self.planned_path:
            self.calculate_smart_a_star()

        if self.planned_path:
            next_pos = self.planned_path.pop(0)
            dx = next_pos[0] - self.x
            dy = next_pos[1] - self.y
            
            for i, d in enumerate(DIRS):
                if d == (dx, dy):
                    return i
        
        for i in range(4):
            if not self.known_walls[self.x][self.y][i]:
                nx, ny = self.x + DIRS[i][0], self.y + DIRS[i][1]
                if (nx, ny) not in self.pruned_cells:
                    return i
        return self.facing

    def draw(self, screen):
        for px, py in self.pruned_cells:
            cx, cy = px * CELL_SIZE, py * CELL_SIZE
            pygame.draw.line(screen, PRUNED_COLOR, (cx+4, cy+4), (cx+CELL_SIZE-4, cy+CELL_SIZE-4), 2)
            pygame.draw.line(screen, PRUNED_COLOR, (cx+CELL_SIZE-4, cy+4), (cx+4, cy+CELL_SIZE-4), 2)

        for px, py in self.planned_path:
            pygame.draw.rect(screen, PLAN_COLOR, (px*CELL_SIZE + 8, py*CELL_SIZE + 8, 4, 4))

        if len(self.path) > 1:
            points = [(x*CELL_SIZE + CELL_SIZE//2, y*CELL_SIZE + CELL_SIZE//2) for x, y in self.path]
            pygame.draw.lines(screen, PATH_COLOR, False, points, 2)

        cx = self.x * CELL_SIZE + CELL_SIZE // 2
        cy = self.y * CELL_SIZE + CELL_SIZE // 2
        
        fx, fy = DIRS[self.facing]
        sx, sy = DIRS[(self.facing + 1) % 4] 
        
        tail_x = cx - fx * 9
        tail_y = cy - fy * 9
        pygame.draw.line(screen, MOUSE_PARTS, (cx, cy), (tail_x, tail_y), 2)
        pygame.draw.circle(screen, MOUSE_BODY, (cx, cy), 6)
        
        ear_offset_f = 2 
        ear_offset_s = 4 
        
        e1_x = cx + (fx * ear_offset_f) + (sx * ear_offset_s)
        e1_y = cy + (fy * ear_offset_f) + (sy * ear_offset_s)
        e2_x = cx + (fx * ear_offset_f) - (sx * ear_offset_s)
        e2_y = cy + (fy * ear_offset_f) - (sy * ear_offset_s)
        
        pygame.draw.circle(screen, MOUSE_PARTS, (int(e1_x), int(e1_y)), 3)
        pygame.draw.circle(screen, MOUSE_PARTS, (int(e2_x), int(e2_y)), 3)
        
        nose_x = cx + fx * 7
        nose_y = cy + fy * 7
        pygame.draw.circle(screen, MOUSE_PARTS, (nose_x, nose_y), 2)

def draw_maze(screen, maze):
    for x in range(COLS):
        for y in range(ROWS):
            px, py = x * CELL_SIZE, y * CELL_SIZE
            cell = maze[x][y]
            w_thick = 2
            if cell.walls[0]: pygame.draw.line(screen, WALL_COLOR, (px, py), (px + CELL_SIZE, py), w_thick)
            if cell.walls[1]: pygame.draw.line(screen, WALL_COLOR, (px + CELL_SIZE, py), (px + CELL_SIZE, py + CELL_SIZE), w_thick)
            if cell.walls[2]: pygame.draw.line(screen, WALL_COLOR, (px, py + CELL_SIZE), (px + CELL_SIZE, py + CELL_SIZE), w_thick)
            if cell.walls[3]: pygame.draw.line(screen, WALL_COLOR, (px, py), (px, py + CELL_SIZE), w_thick)

def draw_text(screen, text, x, y, size=24, color=TEXT_WHITE, bold=False):
    font = pygame.font.SysFont('segoeui', size, bold)
    img = font.render(text, True, color)
    screen.blit(img, (x, y))

def reset_game():
    global action_log
    action_log.clear()
    add_log("=== SYSTEM REBOOT ===")
    return generate_maze(), Mouse(), False, 0, 0, False, False

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("MICROMOUSE GOD MODE (Hyper-Dash AI)")
    clock = pygame.time.Clock()
    
    maze, mouse, first_move, start_ticks, end_ticks, game_over, hide_ui = reset_game()
    mode = 2 
    
    while True:
        current_time = pygame.time.get_ticks()
        screen.fill(BG_COLOR) 
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
                
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r: 
                    maze, mouse, first_move, start_ticks, end_ticks, game_over, hide_ui = reset_game()
                    continue
                elif event.key == pygame.K_q:
                    pygame.quit()
                    sys.exit()
                elif event.key == pygame.K_SPACE and not game_over:
                    mode = 2 if mode == 1 else 1
                    add_log(f"Switched to {'GOD MODE AI' if mode == 2 else 'MANUAL'}")
                elif event.key == pygame.K_h and game_over:
                    hide_ui = not hide_ui

                if mode == 1 and not game_over:
                    want_dir = -1
                    if event.key == pygame.K_w: want_dir = 0
                    elif event.key == pygame.K_d: want_dir = 1
                    elif event.key == pygame.K_s: want_dir = 2
                    elif event.key == pygame.K_a: want_dir = 3
                    
                    if want_dir != -1:
                        if not first_move:
                            first_move = True
                            start_ticks = current_time
                            add_log("Timer Started!")
                            
                        if mouse.facing != want_dir:
                            mouse.facing = want_dir
                            
                        if not maze[mouse.x][mouse.y].walls[want_dir]:
                            mouse.x += DIRS[want_dir][0]
                            mouse.y += DIRS[want_dir][1]
                            mouse.path.append((mouse.x, mouse.y))
                        else:
                            add_log("Hit wall!")

        # --- ส่วนของ AI ที่อัปเกรดความเร็วแบบ GOD MODE ---
        if mode == 2 and not game_over:
            # เดินลูปซ้อนเฟรม เพื่อให้วิ่งด้วยความเร็วสูงมากทะลวงแมพ
            for _ in range(STEPS_PER_FRAME):
                if game_over:
                    break
                    
                mouse.look_ahead(maze)
                
                if mouse.next_dir is None:
                    mouse.next_dir = mouse.decide_next_move()
                
                if not first_move:
                    first_move = True
                    start_ticks = pygame.time.get_ticks()
                    add_log("Timer Started! (GOD MODE)")
                
                if mouse.facing != mouse.next_dir:
                    mouse.facing = mouse.next_dir
                    mouse.look_ahead(maze)
                else:
                    if not maze[mouse.x][mouse.y].walls[mouse.facing]:
                        mouse.x += DIRS[mouse.facing][0]
                        mouse.y += DIRS[mouse.facing][1]
                        mouse.path.append((mouse.x, mouse.y))
                    else:
                        mouse.prune_dead_ends()
                        mouse.calculate_smart_a_star()
                    mouse.next_dir = None
                    
                # เช็คจบเกมทันทีในลูปความเร็วสูง
                if mouse.x == COLS - 1 and mouse.y == ROWS - 1:
                    game_over = True
                    end_ticks = pygame.time.get_ticks()
                    elapsed = (end_ticks - start_ticks) / 1000
                    add_log(f"SYSTEM OVERRIDE! Time: {elapsed:.2f} s")
                    break

        if first_move:
            if game_over: elapsed_time = (end_ticks - start_ticks) / 1000
            else: elapsed_time = (current_time - start_ticks) / 1000
        else:
            elapsed_time = 0.0

        draw_maze(screen, maze)
        
        cx = (COLS-1)*CELL_SIZE + CELL_SIZE//2
        cy = (ROWS-1)*CELL_SIZE + CELL_SIZE//2
        s = CELL_SIZE//2 - 3
        cheese_poly = [(cx, cy-s), (cx+s, cy), (cx, cy+s), (cx-s, cy)]
        pygame.draw.polygon(screen, CHEESE_COLOR, cheese_poly)
        
        mouse.draw(screen)
        
        pygame.draw.rect(screen, LOG_BG_COLOR, (MAZE_WIDTH, 0, SIDEBAR_WIDTH, HEIGHT))
        pygame.draw.line(screen, WALL_COLOR, (MAZE_WIDTH, 0), (MAZE_WIDTH, HEIGHT), 2)
        draw_text(screen, "--- SYSTEM LOG ---", MAZE_WIDTH + 20, 15, 22, CHEESE_COLOR, True)
        
        for i, log_text in enumerate(action_log):
            draw_text(screen, log_text, MAZE_WIDTH + 15, 50 + (i * 22), 18, TEXT_WHITE)

        pygame.draw.rect(screen, UI_BG_COLOR, (0, HEIGHT, SCREEN_WIDTH, UI_HEIGHT))
        pygame.draw.line(screen, WALL_COLOR, (0, HEIGHT), (SCREEN_WIDTH, HEIGHT), 2)
        
        mode_text = "MANUAL (WASD)" if mode == 1 else "GOD MODE AI (Hyper-Dash)"
        mode_color = MOUSE_PARTS if mode == 1 else TEXT_HIGHLIGHT
        
        draw_text(screen, f"MODE: {mode_text}", 30, HEIGHT + 25, 26, mode_color, True)
        draw_text(screen, f"TIME: {elapsed_time:.2f} s", 30, HEIGHT + 60, 26, CHEESE_COLOR, True)
        
        draw_text(screen, "[SPACE] Toggle Mode", 350, HEIGHT + 20, 20, TEXT_WHITE)
        draw_text(screen, "[R] Generate New Maze", 350, HEIGHT + 45, 20, TEXT_WHITE)
        draw_text(screen, "[Q] Quit System", 350, HEIGHT + 70, 20, TEXT_WHITE)

        if game_over:
            if not hide_ui:
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                overlay.set_alpha(170)
                overlay.fill((5, 0, 15)) 
                screen.blit(overlay, (0, 0))
                
                banner_h = 240
                banner_y = (SCREEN_HEIGHT // 2) - (banner_h // 2) - 20 
                
                pygame.draw.rect(screen, (20, 15, 35), (0, banner_y, SCREEN_WIDTH, banner_h))
                
                pygame.draw.line(screen, MOUSE_PARTS, (0, banner_y), (SCREEN_WIDTH, banner_y), 4)
                pygame.draw.line(screen, MOUSE_PARTS, (0, banner_y + banner_h), (SCREEN_WIDTH, banner_y + banner_h), 4)
                
                draw_text(screen, "///", 50, banner_y + 90, 50, WALL_COLOR, True)
                draw_text(screen, "\\\\\\", SCREEN_WIDTH - 100, banner_y + 90, 50, WALL_COLOR, True)
                
                font_title = pygame.font.SysFont('segoeui', 55, True)
                font_time = pygame.font.SysFont('segoeui', 35, True)
                font_hint = pygame.font.SysFont('segoeui', 22, False)
                
                title_surf = font_title.render("SYSTEM OVERRIDE COMPLETE", True, CHEESE_COLOR)
                time_surf = font_time.render(f"EXECUTION TIME : {elapsed_time:.3f} SEC", True, WALL_COLOR)
                hint_surf = font_hint.render("[R] REBOOT SYSTEM   |   [H] TOGGLE VISIBILITY", True, TEXT_WHITE)
                
                screen.blit(title_surf, (SCREEN_WIDTH//2 - title_surf.get_width()//2, banner_y + 40))
                screen.blit(time_surf, (SCREEN_WIDTH//2 - time_surf.get_width()//2, banner_y + 115))
                screen.blit(hint_surf, (SCREEN_WIDTH//2 - hint_surf.get_width()//2, banner_y + 185))
                
            else:
                draw_text(screen, "Press [H] to Show End Screen", 10, 10, 20, CHEESE_COLOR)

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    main()
