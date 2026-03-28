from __future__ import annotations

import sys
import pygame

import constants

import random
import threading
import time

from buttons import Button
from solver.SolverParallel import DominoParallelSolver

async_state = "idle"
solver_solution = None
generated_dominoes = None
gen_attempts = 0

def solve_worker(domino_list, size):
    global async_state, solver_solution
    tuples = [(d.left, d.right) for d in domino_list]
    s = DominoParallelSolver(size, size, tuples, engine="optimized")
    # Extended timeout so it eventually solves what's on the board
    sol = s.solve_with_restarts(max_restarts=100000, timeout_seconds=60)
    solver_solution = sol
    async_state = "idle"

def generate_worker(size, num_doms):
    global async_state, generated_dominoes, gen_attempts
    while async_state == "generating":
        gen_attempts += 1
        test_doms = random_dominoes(num_doms)
        tuples = [(d.left, d.right) for d in test_doms]
        s = DominoParallelSolver(size, size, tuples, engine="optimized")
        sol = s.solve_with_restarts(max_restarts=100000, timeout_seconds=10)
        if sol is not None:
            generated_dominoes = test_doms
            async_state = "idle"
            break

# ---------------------------------


pygame.init()
constants.init()

from constants import (
    WINDOW_SIZE, BOARD_PIXELS, SIDEBAR_WIDTH, SIDEBAR_FILL,
    FPS, FONT_SIZE, PIP_COLOURS, DOMINO_NUM, CELL_SIZE, WIDTH, HEIGHT,
    BOARD_SZ
)

from board import Board
from helpers import random_dominoes, layout_sidebar, get_solvable_puzzles
solvables = get_solvable_puzzles()


FONT_HINT = pygame.font.SysFont(None, FONT_SIZE)


def run() -> None:
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Domino Puzzle")
    clock = pygame.time.Clock()

    board = Board()
    #dominoes = random_dominoes(DOMINO_NUM)
    dominoes = random.choice(solvables)
    layout_sidebar(dominoes)

    btn_font = pygame.font.SysFont(None, int(FONT_SIZE * 0.8))
    btn_w, btn_h = SIDEBAR_WIDTH - 20, FONT_SIZE * 2
    btn_x = BOARD_PIXELS + 10
    
    btn_gen = Button((btn_x, WINDOW_SIZE[1] - (btn_h * 2 + 30), btn_w, btn_h), "Generate Solvable", btn_font)
    btn_solve = Button((btn_x, WINDOW_SIZE[1] - (btn_h + 10), btn_w, btn_h), "Reveal Solution", btn_font)

    global async_state, solver_solution, generated_dominoes, gen_attempts
    drag_domino = None
    offset_x = offset_y = 0

    while True:
        # Check background results
        if generated_dominoes is not None:
            dominoes = generated_dominoes
            layout_sidebar(dominoes)
            board = Board()  # reset board
            generated_dominoes = None
            gen_attempts = 0
            
        if solver_solution is not None:
            # Print solution to console in same format as solver engines
            print("\n" + "="*30)
            print("   DOMINO SOLVER: SOLUTION")
            print("="*30)
            if hasattr(solver_solution, 'placements'):
                # Optimized Engine Format
                for r in range(BOARD_SZ):
                    row_parts = []
                    for c in range(BOARD_SZ):
                        idx = r * BOARD_SZ + c
                        val = solver_solution.cell_value[idx]
                        row_parts.append(str(val) if val != -1 else ".")
                    print(" ".join(row_parts))
            else:
                # V2 Engine Format
                for r in range(BOARD_SZ):
                    row_parts = []
                    for c in range(BOARD_SZ):
                        val = solver_solution.cell_value.get((r, c), -1)
                        row_parts.append(str(val) if val != -1 else ".")
                    print(" ".join(row_parts))
            print("="*30 + "\n")

            board = Board() # clear current placements
            layout_sidebar(dominoes)
            for d in dominoes:
                d.return_to_pool()
                
            # Compatibility check: SolverOptimized uses a list 'placements' with 1D indices,
            # while SolverV2 uses a dict 'placed' with 2D tuples.
            if hasattr(solver_solution, 'placements'):
                # Handle SolverOptimized (1D)
                for p in solver_solution.placements:
                    d = dominoes[p.domino_id]
                    c0 = (p.c0 // BOARD_SZ, p.c0 % BOARD_SZ)
                    c1 = (p.c1 // BOARD_SZ, p.c1 % BOARD_SZ)
                    
                    if d.orientation.value == 0 and c0[0] != c1[0]:
                        d.rotate()
                    elif d.orientation.value == 1 and c0[0] == c1[0]:
                        d.rotate()
                        
                    top_r, top_c = min(c0[0], c1[0]), min(c0[1], c1[1])
                    target_top_v = p.v0 if (p.c0 // BOARD_SZ, p.c0 % BOARD_SZ) == (top_r, top_c) else p.v1
                    if d.value_at(0) != target_top_v:
                        d.left, d.right = d.right, d.left
                    board.place(d, top_r, top_c)
            else:
                # Handle SolverV2 (2D)
                for p in solver_solution.placed.values():
                    d = dominoes[p.domino_id]
                    if d.orientation.value == 0 and p.c0[0] != p.c1[0]:
                        d.rotate()
                    elif d.orientation.value == 1 and p.c0[0] == p.c1[0]:
                        d.rotate()
                    
                    top_r, top_c = min(p.c0[0], p.c1[0]), min(p.c0[1], p.c1[1])
                    target_top_v = p.v0 if p.c0 == (top_r, top_c) else p.v1
                    if d.value_at(0) != target_top_v:
                        d.left, d.right = d.right, d.left
                    board.place(d, top_r, top_c)
            solver_solution = None

        mouse_pos = pygame.mouse.get_pos()
        btn_gen.check_hover(mouse_pos)
        btn_solve.check_hover(mouse_pos)

        # ── Event loop ───────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Disallow UI interaction while loading
                if async_state != "idle":
                    continue
                    
                if btn_gen.is_clicked(event.pos):
                    async_state = "generating"
                    gen_attempts = 0
                    threading.Thread(target=generate_worker, args=(BOARD_SZ, DOMINO_NUM), daemon=True).start()
                    continue
                    
                if btn_solve.is_clicked(event.pos):
                    async_state = "solving"
                    threading.Thread(target=solve_worker, args=(dominoes, BOARD_SZ), daemon=True).start()
                    continue

                for d in reversed(dominoes):
                    if d.rect.collidepoint(event.pos):
                        drag_domino = d
                        drag_domino.dragging = True
                        mx, my = event.pos
                        offset_x = d.rect.x - mx
                        offset_y = d.rect.y - my
                        if not d.in_pool:
                            board.lift(d)  # remove from board occupancy
                        break

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and drag_domino:
                if async_state != "idle":
                    drag_domino = None
                    continue
                mx, my = event.pos
                r, c = Board.cell_at_pixel(mx, my)
                if not board.place(drag_domino, r, c):
                    drag_domino.return_to_pool()
                drag_domino = None

            if event.type == pygame.KEYDOWN and event.key == pygame.K_r and drag_domino:
                if async_state == "idle":
                    drag_domino.rotate()

        if drag_domino and drag_domino.dragging:
            mx, my = pygame.mouse.get_pos()
            drag_domino.rect.topleft = (mx + offset_x, my + offset_y)

        # ── Render ───────────────────────────────────────────
        board.draw(screen)
        sidebar_rect = pygame.Rect(BOARD_PIXELS, 0, SIDEBAR_WIDTH, WINDOW_SIZE[1])
        pygame.draw.rect(screen, SIDEBAR_FILL, sidebar_rect)

        valid_indicator_rect = pygame.Rect(WINDOW_SIZE[0] - CELL_SIZE - 10, 10, CELL_SIZE, CELL_SIZE)
        if (board.isvalid):
            if board.num_dom == DOMINO_NUM:
                vc = (0,255,0)
            else:
                vc = (255,255,0)
        else:
            vc = (255,0,0)
        pygame.draw.rect(screen, vc, valid_indicator_rect)

        btn_gen.draw(screen)
        btn_solve.draw(screen)

        for d in dominoes:
            d.draw(screen)

        if async_state != "idle":
            s = pygame.Surface((WINDOW_SIZE[0], WINDOW_SIZE[1]))
            s.set_alpha(128)
            s.fill((0,0,0))
            screen.blit(s, (0,0))
            
            msg = f"Generating (Attempt #{gen_attempts})..." if async_state == "generating" else "Solving..."
            txt = FONT_HINT.render(msg, True, (255,255,255))
            tr = txt.get_rect(center=(WINDOW_SIZE[0]//2, WINDOW_SIZE[1]//2))
            screen.blit(txt, tr)


        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    run()