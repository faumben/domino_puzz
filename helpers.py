"""Utility functions that don’t fit cleanly into a class."""
from typing import List
import random

from domino import Domino
from constants import BOARD_PIXELS, SIDEBAR_WIDTH, SIDEBAR_PAD, CELL_SIZE


# generate random dominoes ------------------------------------------

def random_dominoes(n: int) -> List[Domino]:
    l = [[random.randint(0, 6), random.randint(0, 6)] for _ in range(n)]
    l = [(y, x) if x > y else (x, y) for x, y in l]
    l = sorted(l, key=lambda x: (x[0], x[1]))

    ret = [Domino(l[i][0], l[i][1]) for i in range(n)]
    print(f"[helpers] puzzle: {l}")

    return ret


# layout sidebar ----------------------------------------------------

def layout_sidebar(dominoes: List[Domino]) -> None:
    x = BOARD_PIXELS + SIDEBAR_PAD
    y = SIDEBAR_PAD
    for d in dominoes:
        d.rect.topleft = (x, y)
        d.pos = d.rect.topleft
        d.pool_pos = d.rect.topleft
        y += d.rect.height + SIDEBAR_PAD
