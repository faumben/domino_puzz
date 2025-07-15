
from __future__ import annotations
from enum import Enum

DOMINO_NUM: int = 14

WIDTH: int | None = None  # init sets to full-screen
HEIGHT: int | None = None  # init sets to full-screen

# set by init
CELL_SIZE: int | None = None
BOARD_SZ: int | None = None
SIDEBAR_WIDTH: int | None = None
SIDEBAR_PAD: int | None = None
FONT_SIZE: int | None = None
FPS: int | None = None
WINDOW_SIZE: int | None = None
BOARD_PIXELS: int | None = None


def init() -> None:
    import pygame
    global WIDTH, HEIGHT, CELL_SIZE, BOARD_SZ,\
            SIDEBAR_WIDTH, SIDEBAR_PAD, FONT_SIZE, FPS,\
            WINDOW_SIZE, BOARD_PIXELS

    if WIDTH is not None or HEIGHT is not None:
        raise RuntimeError("constants.init() called more than once")

    info = pygame.display.Info()
    width, height = info.current_w, info.current_h

    WIDTH, HEIGHT = width, height
    print(f"[constants] resolution: {WIDTH}×{HEIGHT}")
    # WIDTH /= 2
    # HEIGHT /= 2
    # Grid / display ----------------------------------------------------
    BOARD_SZ = 16  # squares along each board edge
    CELL_SIZE = int(min(HEIGHT, WIDTH ) /16)  # px per square
    SIDEBAR_WIDTH = WIDTH - BOARD_SZ * CELL_SIZE
    SIDEBAR_PAD = (HEIGHT - (DOMINO_NUM * (CELL_SIZE+1))) /(DOMINO_NUM+1)
    FONT_SIZE = int(HEIGHT * .04)
    FPS = 60

    # Derived sizes -----------------------------------------------------
    BOARD_PIXELS = BOARD_SZ * CELL_SIZE
    WINDOW_SIZE = (BOARD_PIXELS + SIDEBAR_WIDTH, BOARD_PIXELS)


# ────────────────────────────────────────────────────────────────────
# Colours
# ────────────────────────────────────────────────────────────────────
BG = (139, 131, 120)
GRID = (205, 192, 176)
DOMINO_FILL = (248, 238, 226)
DOMINO_DRAG = (255, 255, 200)
DOMINO_SPLIT = (219, 164, 164)
DOMINO_OUTLINE = (186, 140, 140)
SIDEBAR_FILL = (205, 192, 176)

# Unique pip colours 0‑6
PIP_COLOURS = [
    (31, 119, 180),  # 0 – blue
    (255, 127, 14),  # 1 – orange
    (44, 160, 44),  # 2 – green
    (214, 39, 40),  # 3 – red
    (148, 103, 189),  # 4 – purple
    (140, 86, 75),  # 5 – brown
    (127, 127, 127),  # 6 – grey
]


# ────────────────────────────────────────────────────────────────────
# Orientation enum
# ────────────────────────────────────────────────────────────────────
class Orientation(Enum):
    HORIZONTAL = 0
    VERTICAL = 1


__all__ = [
    "WIDTH", "HEIGHT", "CELL_SIZE", "BOARD_SZ", "DOMINO_NUM",
    "SIDEBAR_WIDTH", "SIDEBAR_PAD", "FONT_SIZE", "FPS",
    "BOARD_PIXELS", "WINDOW_SIZE",
    "BG", "GRID", "DOMINO_FILL", "DOMINO_DRAG",
    "DOMINO_SPLIT", "DOMINO_OUTLINE", "SIDEBAR_FILL",
    "PIP_COLOURS", "Orientation", "init",
]
