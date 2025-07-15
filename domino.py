"""Domino data object – logic‑free except for size/rotation helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing      import Tuple
import pygame
import random

from constants import CELL_SIZE, Orientation, PIP_COLOURS, DOMINO_FILL, DOMINO_SPLIT, DOMINO_DRAG, DOMINO_OUTLINE, FONT_SIZE

pygame.font.init()
_FONT = pygame.font.SysFont(None, FONT_SIZE, bold=True)

Position = Tuple[int, int]  # alias for readability

@dataclass(slots=True)
class Domino:
    left: int
    right: int
    orientation: Orientation = Orientation.HORIZONTAL
    # runtime‑only attrs ------------------
    pos:      Position = (0, 0)
    pool_pos: Position = (0, 0)
    in_pool:  bool      = True            # True → still unplaced
    dragging: bool      = False           # currently under cursor
    rect:     pygame.Rect = field(init=False, repr=False)
    color: tuple = DOMINO_FILL

    # ───────────────────────────────────────────────────────────
    def __post_init__(self) -> None:
        self.rect = pygame.Rect(self.pos, self._size())
        #r = random.randint(200,255)
        #self.color = (r, r, r)

    # Properties ------------------------------------------------
    def _size(self) -> Tuple[int, int]:
        return ((CELL_SIZE * 2+1, CELL_SIZE+1) if self.orientation is Orientation.HORIZONTAL
                else (CELL_SIZE+1, CELL_SIZE * 2+1))

    def rotate(self) -> None:
        """Toggle orientation – keeps the domino centred around its middle."""
        if (self.orientation == Orientation.VERTICAL):
            self.orientation = Orientation.HORIZONTAL
            temp = self.left
            self.left = self.right
            self.right = temp
        else:
            self.orientation = Orientation.VERTICAL
        centre           = self.rect.center
        self.rect.size   = self._size()
        self.rect.center = centre

    def return_to_pool(self) -> None:
        self.in_pool = True
        self.orientation = Orientation.HORIZONTAL
        self.pos = self.pool_pos
        self.dragging = False
        self.rect = pygame.Rect(self.pos, self._size())
    # Drawing ---------------------------------------------------
    def _draw_number(self, surface: pygame.Surface, value: int, target: pygame.Rect) -> None:
        glyph   = _FONT.render(str(value), True, PIP_COLOURS[value])
        glyph_r = glyph.get_rect(center=target.center)
        surface.blit(glyph, glyph_r)

    def draw(self, surface: pygame.Surface) -> None:
        fill = DOMINO_DRAG if self.dragging else self.color
        pygame.draw.rect(surface, fill,           self.rect)

        # divider + half rectangles
        if self.orientation is Orientation.HORIZONTAL:
            mid_x   = self.rect.left + CELL_SIZE
            pygame.draw.line(surface, DOMINO_SPLIT, (mid_x, self.rect.top), (mid_x, self.rect.bottom - 1), 1)
            halves = (
                pygame.Rect(self.rect.left, self.rect.top, CELL_SIZE, CELL_SIZE),
                pygame.Rect(mid_x,          self.rect.top, CELL_SIZE, CELL_SIZE),
            )
        else:
            mid_y   = self.rect.top + CELL_SIZE
            pygame.draw.line(surface, DOMINO_SPLIT, (self.rect.left, mid_y), (self.rect.right - 1, mid_y), 1)
            halves = (
                pygame.Rect(self.rect.left, self.rect.top, CELL_SIZE, CELL_SIZE),
                pygame.Rect(self.rect.left, mid_y,          CELL_SIZE, CELL_SIZE),
            )
        pygame.draw.rect(surface, DOMINO_OUTLINE, self.rect, 1)
        self._draw_number(surface, self.left,  halves[0])
        self._draw_number(surface, self.right, halves[1])

    # Game helpers ----------------------------------------------
    def value_at(self, half_idx: int) -> int:
        return self.left if half_idx == 0 else self.right
