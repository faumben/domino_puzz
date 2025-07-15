
from __future__ import annotations

from typing import Dict, List, Tuple
import pygame

from constants import (
    BOARD_SZ, CELL_SIZE, BOARD_PIXELS, BG, GRID,
    Orientation,
)
from domino import Domino

Cell    = Tuple[int, int]
Mapping = Dict[Cell, Tuple[Domino, int]]  # (domino, half‑idx)


class Board:

    def __init__(self, size: int = BOARD_SZ) -> None:
        self.size: int = size
        # grid[r][c] == -1 ➜ empty; otherwise stores the pip value (0‑12 etc.)
        self.grid: List[List[int]] = [[-1] * size for _ in range(size)]
        # Auxiliary map so we can quickly remove a placed domino
        self.map:  Mapping = {}
        self.bg_color = BG
        self.isvalid = True
        self.num_dom = 0

    # ── Coordinate helpers ──────────────────────────────────
    @staticmethod
    def cell_at_pixel(x: int, y: int) -> Cell:
        return y // CELL_SIZE, x // CELL_SIZE

    @staticmethod
    def pixel_at_cell(row: int, col: int) -> Tuple[int, int]:
        return col * CELL_SIZE, row * CELL_SIZE

    def _cells_for(self, d: Domino, row: int, col: int) -> Tuple[Cell, Cell]:
        return ((row, col), (row, col + 1)) if d.orientation is Orientation.HORIZONTAL else ((row, col), (row + 1, col))

    # ── Validation helpers ──────────────────────────────────
    def _bounds_ok(self, cells) -> bool:
        return all(0 <= r < self.size and 0 <= c < self.size for r, c in cells)

    def _free(self, cells) -> bool:
        return all(self.grid[r][c] == -1 for r, c in cells)

    def _neighbors(self, r: int, c: int):
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.size and 0 <= nc < self.size:
                yield nr, nc

    def _adjacency_ok(self, d: Domino, row: int, col: int) -> bool:
        cells = self._cells_for(d, row, col)
        for idx, (r, c) in enumerate(cells):
            v = d.value_at(idx)
            other = cells[1 - idx]
            for nr, nc in self._neighbors(r, c):
                if (nr, nc) == other:
                    continue  # skip partner half of the same domino
                nb_val = self.grid[nr][nc]
                if nb_val != -1 and nb_val != v:
                    return False  # mismatched adjacent pip value
        return True

    def can_place(self, d: Domino, row: int, col: int) -> bool:
        cells = self._cells_for(d, row, col)
        return (
            self._bounds_ok(cells)
            and self._free(cells)
            and self._adjacency_ok(d, row, col)
        )

    # ── Mutations ───────────────────────────────────────────
    def place(self, d: Domino, row: int, col: int) -> bool:
        if not self.can_place(d, row, col):
            return False
        cells = self._cells_for(d, row, col)
        for idx, (r, c) in enumerate(cells):
            self.grid[r][c] = d.value_at(idx)
            self.map[(r, c)] = (d, idx)
        d.rect.topleft = self.pixel_at_cell(row, col)
        d.dragging = False
        d.in_pool = False
        d.pos = d.rect.topleft
        self.update_valid()
        self.num_dom += 1
        return True

    def lift(self, d: Domino) -> None:
        for (r, c), (od, _i) in list(self.map.items()):
            if od is d:
                self.grid[r][c] = -1
                del self.map[(r, c)]
        self.update_valid()
        self.num_dom -= 1

    # ── Global board validation ────────────────────────────
    def valid_position(self) -> bool:
        """Return *True* if the current grid configuration is globally valid.
        Conditions:
        1. Global connectivity: All occupied cells (grid[r][c] > -1)
           form a single orthogonally‑connected component.
        2. Per‑value connectivity: For every pip value *v*, the subset of
           cells whose value equals *v* is itself connected.
        """
        # Collect coordinates of all occupied cells
        occ: List[Cell] = [
            (r, c)
            for r in range(self.size)
            for c in range(self.size)
            if self.grid[r][c] != -1
        ]

        # An empty board is considered valid
        if not occ:
            return True

        # ── 1. Global connectivity ──
        seen: set[Cell] = set()
        stack: List[Cell] = [occ[0]]
        seen.add(occ[0])

        while stack:
            r, c = stack.pop()
            for nr, nc in self._neighbors(r, c):
                if self.grid[nr][nc] != -1 and (nr, nc) not in seen:
                    seen.add((nr, nc))
                    stack.append((nr, nc))

        if len(seen) != len(occ):
            return False  # More than one global component

        # ── 2. Per‑value connectivity ──
        values = {self.grid[r][c] for r, c in occ}
        for v in values:
            # Skip singletons — a lone cell is trivially connected
            cells_v = [(r, c) for (r, c) in occ if self.grid[r][c] == v]
            if len(cells_v) <= 1:
                continue

            seen_v: set[Cell] = set()
            stack = [cells_v[0]]
            seen_v.add(cells_v[0])
            while stack:
                r, c = stack.pop()
                for nr, nc in self._neighbors(r, c):
                    if self.grid[nr][nc] == v and (nr, nc) not in seen_v:
                        seen_v.add((nr, nc))
                        stack.append((nr, nc))
            if len(seen_v) != len(cells_v):
                return False  # Value *v* is split into multiple islands

        return True

    def update_valid(self) -> None:
            self.isvalid = self.valid_position()
    # ── Rendering ───────────────────────────────────────────
    def draw(self, surf: pygame.Surface) -> None:
        pygame.draw.rect(surf, self.bg_color, (0, 0, BOARD_PIXELS, BOARD_PIXELS))
        for i in range(self.size + 1):
            pygame.draw.line(
                surf, GRID, (i * CELL_SIZE, 0), (i * CELL_SIZE, BOARD_PIXELS), 1
            )
            pygame.draw.line(
                surf, GRID, (0, i * CELL_SIZE), (BOARD_PIXELS, i * CELL_SIZE), 1
            )
        # NOTE: Domino sprites themselves are drawn elsewhere; this method only paints the board grid and background.
