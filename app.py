from __future__ import annotations

import sys
import pygame

import constants

# ---------------------------------


pygame.init()
constants.init()

from constants import (
    WINDOW_SIZE, BOARD_PIXELS, SIDEBAR_WIDTH, SIDEBAR_FILL,
    FPS, FONT_SIZE, PIP_COLOURS, DOMINO_NUM, CELL_SIZE, WIDTH, HEIGHT
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
    dominoes = random_dominoes(DOMINO_NUM)
    layout_sidebar(dominoes)

    drag_domino = None
    offset_x = offset_y = 0

    while True:
        # ── Event loop ───────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
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
                mx, my = event.pos
                r, c = Board.cell_at_pixel(mx, my)
                if not board.place(drag_domino, r, c):
                    drag_domino.return_to_pool()
                drag_domino = None

            if event.type == pygame.KEYDOWN and event.key == pygame.K_r and drag_domino:
                drag_domino.rotate()

        if drag_domino and drag_domino.dragging:
            mx, my = pygame.mouse.get_pos()
            drag_domino.rect.topleft = (mx + offset_x, my + offset_y)

        # ── Render ───────────────────────────────────────────
        board.draw(screen)
        sidebar_rect = pygame.Rect(BOARD_PIXELS, 0, SIDEBAR_WIDTH, WINDOW_SIZE[1])
        pygame.draw.rect(screen, SIDEBAR_FILL, sidebar_rect)

        valid_indicator_rect = pygame.Rect(0, 0, CELL_SIZE, CELL_SIZE)
        if (board.isvalid):
            if board.num_dom == DOMINO_NUM:
                vc = (0,255,0)
            else:
                vc = (255,255,0)
        else:
            vc = (255,0,0)
        pygame.draw.rect(screen, vc, valid_indicator_rect)

        for d in dominoes:
            d.draw(screen)


        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    run()