"""Utility functions that don’t fit cleanly into a class."""
from typing import List
import random

from domino import Domino
from constants import BOARD_PIXELS, SIDEBAR_WIDTH, SIDEBAR_PAD, CELL_SIZE

import ast

def random_dominoes(n: int) -> List[Domino]:
    l = [[random.randint(0, 6), random.randint(0, 6)] for _ in range(n)]
    l = [(y, x) if x > y else (x, y) for x, y in l]
    l = sorted(l, key=lambda x: (x[0], x[1]))

    ret = [Domino(l[i][0], l[i][1]) for i in range(n)]
    print(f"[helpers] puzzle: {l}")

    return ret



def layout_sidebar(dominoes: List[Domino]) -> None:
    x = BOARD_PIXELS + SIDEBAR_PAD
    y = SIDEBAR_PAD
    for d in dominoes:
        d.rect.topleft = (x, y)
        d.pos = d.rect.topleft
        d.pool_pos = d.rect.topleft
        y += d.rect.height + SIDEBAR_PAD

def get_solvable_puzzles():
    raw_puzzles = []
    puzzles = []
    with open("solvable.txt", "r", encoding="utf‑8") as fh:
        for line in fh:
            line = line.strip()  # drop leading/trailing spaces and the newline
            if not line:  # skip blank lines, if any
                continue
            raw_puzzles.append(ast.literal_eval(line))
    for raw_doms in raw_puzzles:
        puzzle = []
        for raw_dom in raw_doms:
            puzzle.append(Domino(raw_dom[0], raw_dom[1]))
        puzzles.append(puzzle)
    return puzzles
