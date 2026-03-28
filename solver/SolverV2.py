"""
SolverV2: original staged solver with two targeted optimizations:
  1. Frontier-restricted edge generation (massive branching reduction)
  2. In-place state modification with undo (avoids clone overhead in inner loop)

The stage structure and Rule 3 checking logic are preserved exactly from
SolverBase.py — only active-value Rule 3 is checked during each stage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional, Union
import time

Cell = Tuple[int, int]


@dataclass(frozen=True, order=True)
class Domino:
    a: int
    b: int

    def has_value(self, v: int) -> bool:
        return self.a == v or self.b == v

    def values(self) -> Tuple[int, int]:
        return (self.a, self.b)


DominoInput = Union[Domino, Tuple[int, int]]


@dataclass(frozen=True)
class Placement:
    domino_id: int
    c0: Cell
    c1: Cell
    v0: int
    v1: int

    @property
    def cells(self) -> Tuple[Cell, Cell]:
        return (self.c0, self.c1)

    def has_value(self, v: int) -> bool:
        return self.v0 == v or self.v1 == v


@dataclass
class BoardState:
    cell_value: Dict[Cell, int] = field(default_factory=dict)
    paired_with: Dict[Cell, Cell] = field(default_factory=dict)
    placed: Dict[int, Placement] = field(default_factory=dict)
    unplaced_domino_ids: Set[int] = field(default_factory=set)

    locked_values: Set[int] = field(default_factory=set)
    current_value: Optional[int] = None

    value_cells: Dict[int, Set[Cell]] = field(
        default_factory=lambda: defaultdict(set)
    )
    occupied_cells: Set[Cell] = field(default_factory=set)

    def clone(self) -> BoardState:
        out = BoardState()
        out.cell_value = dict(self.cell_value)
        out.paired_with = dict(self.paired_with)
        out.placed = dict(self.placed)
        out.unplaced_domino_ids = set(self.unplaced_domino_ids)
        out.locked_values = set(self.locked_values)
        out.current_value = self.current_value
        out.value_cells = defaultdict(
            set, {v: set(cells) for v, cells in self.value_cells.items()}
        )
        out.occupied_cells = set(self.occupied_cells)
        return out

    def add_placement(self, p: Placement) -> None:
        self.placed[p.domino_id] = p
        self.unplaced_domino_ids.remove(p.domino_id)
        self.cell_value[p.c0] = p.v0
        self.cell_value[p.c1] = p.v1
        self.paired_with[p.c0] = p.c1
        self.paired_with[p.c1] = p.c0
        self.occupied_cells.add(p.c0)
        self.occupied_cells.add(p.c1)
        self.value_cells[p.v0].add(p.c0)
        self.value_cells[p.v1].add(p.c1)

    def remove_placement(self, p: Placement) -> None:
        del self.placed[p.domino_id]
        self.unplaced_domino_ids.add(p.domino_id)
        del self.cell_value[p.c0]
        del self.cell_value[p.c1]
        del self.paired_with[p.c0]
        del self.paired_with[p.c1]
        self.occupied_cells.remove(p.c0)
        self.occupied_cells.remove(p.c1)
        self.value_cells[p.v0].remove(p.c0)
        self.value_cells[p.v1].remove(p.c1)


@dataclass(frozen=True)
class StageConfigKey:
    active_value: int
    remaining_domino_types: Tuple[Tuple[int, int], ...]
    cell_values: Tuple[Tuple[Cell, int], ...]
    occupied_cells: Tuple[Cell, ...]


class DominoStageSolver:
    def __init__(
        self,
        rows: int,
        cols: int,
        dominoes: List[DominoInput],
        allowed_cells: Optional[Set[Cell]] = None,
        anchor_center: bool = False,
        randomize_tiebreaks: bool = False,
        max_nodes_per_restart: Optional[int] = None,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.dominoes: List[Domino] = []
        for d in dominoes:
            if isinstance(d, Domino):
                a, b = d.a, d.b
            elif isinstance(d, tuple) and len(d) == 2:
                a, b = d
            else:
                raise TypeError(f"Invalid domino: {d!r}")
            if a > b:
                a, b = b, a
            self.dominoes.append(Domino(a, b))

        self.anchor_center = anchor_center
        self.randomize_tiebreaks = randomize_tiebreaks
        self.max_nodes = max_nodes_per_restart

        if allowed_cells is None:
            self.allowed_cells: Set[Cell] = {
                (r, c) for r in range(rows) for c in range(cols)
            }
        else:
            self.allowed_cells = set(allowed_cells)

        self.adj = self._build_adjacency()
        self.domino_by_id = {i: d for i, d in enumerate(self.dominoes)}

        self.domino_ids_by_value: Dict[int, Set[int]] = defaultdict(set)
        for i, d in enumerate(self.dominoes):
            self.domino_ids_by_value[d.a].add(i)
            self.domino_ids_by_value[d.b].add(i)

        self.failed_stage_configs: Set[StageConfigKey] = set()
        self.center = self._choose_center_cell()
        self.nodes = 0

    def _build_adjacency(self) -> Dict[Cell, List[Cell]]:
        adj: Dict[Cell, List[Cell]] = {}
        for r, c in self.allowed_cells:
            nbrs = []
            for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if (nr, nc) in self.allowed_cells:
                    nbrs.append((nr, nc))
            adj[(r, c)] = nbrs
        return adj

    def _choose_center_cell(self) -> Cell:
        r = (self.rows - 1) // 2
        c = (self.cols - 1) // 2
        center = (r, c)
        return center if center in self.allowed_cells else min(self.allowed_cells)

    # ── Core solver ──────────────────────────────────────────────────────

    def solve(self) -> Optional[BoardState]:
        state = self._initial_state()
        self.nodes = 0
        return self._solve_from_stage(state)
        
    def solve_with_restarts(
        self, 
        max_restarts=100, 
        initial_max_nodes=5000,
        restart_multiplier=1.2,
        absolute_max_nodes=10000
    ) -> Optional[BoardState]:
        import time
        orig_randomize = self.randomize_tiebreaks
        orig_max_nodes = self.max_nodes
        
        self.randomize_tiebreaks = True
        current_max_nodes = float(initial_max_nodes)
        
        try:
            for i in range(max_restarts):
                self.max_nodes = int(current_max_nodes)
                self.nodes = 0
                self.failed_stage_configs.clear()
                state = self._initial_state()
                try:
                    sol = self._solve_from_stage(state)
                    if sol is not None:
                        return sol
                except TimeoutError:
                    current_max_nodes = min(current_max_nodes * restart_multiplier, float(absolute_max_nodes))
            return None
        finally:
            self.randomize_tiebreaks = orig_randomize
            self.max_nodes = orig_max_nodes

    def _initial_state(self) -> BoardState:
        s = BoardState()
        s.unplaced_domino_ids = set(range(len(self.dominoes)))
        return s

    def _solve_from_stage(self, state: BoardState) -> Optional[BoardState]:
        if not state.unplaced_domino_ids:
            return state if self._final_rules_hold(state) else None
        active_value = self._choose_next_value(state)
        if active_value is None:
            return state if self._final_rules_hold(state) else None
        return self._run_value_stage(state, active_value)

    def _run_value_stage(self, state, active_value):
        stage_state = state.clone()
        stage_state.current_value = active_value
        remaining_ids = self._remaining_domino_ids_containing_value(stage_state, active_value)
        if not remaining_ids:
            stage_state.locked_values.add(active_value)
            stage_state.current_value = None
            return self._solve_from_stage(stage_state)
        return self._enumerate_stage_configurations(stage_state, active_value, remaining_ids)

    def _enumerate_stage_configurations(self, state, active_value, remaining_stage_domino_ids):
        key = self._make_stage_key(state, active_value)
        if key in self.failed_stage_configs:
            return None

        if not remaining_stage_domino_ids:
            if self._stage_accepts(state, active_value):
                next_state = state.clone()
                next_state.locked_values.add(active_value)
                next_state.current_value = None
                solved = self._solve_from_stage(next_state)
                if solved is not None:
                    return solved
            self.failed_stage_configs.add(key)
            return None

        # Restrict edges to only those touching the existing active_value cells
        edges = self._candidate_empty_edges_for_active_value(state, active_value)
        if not edges and state.occupied_cells:
            self.failed_stage_configs.add(key)
            return None

        domino_id = self._choose_next_domino_for_stage(state, active_value, remaining_stage_domino_ids, edges)
        if domino_id is None:
            self.failed_stage_configs.add(key)
            return None

        candidates = self._generate_stage_placements(state, active_value, domino_id, edges)

        next_remaining = remaining_stage_domino_ids - {domino_id}

        for p in candidates:
            self.nodes += 1
            if self.max_nodes is not None and self.nodes > self.max_nodes:
                raise TimeoutError("Node limit reached")

            # In-place modify + undo instead of clone
            state.add_placement(p)

            if self._stage_prefix_feasible(state, active_value):
                solved = self._enumerate_stage_configurations(state, active_value, next_remaining)
                if solved is not None:
                    return solved

            state.remove_placement(p)

        self.failed_stage_configs.add(key)
        return None

    # ── Value & domino selection ─────────────────────────────────────────

    def _choose_next_value(self, state):
        candidates = []
        board_values = {v for v in range(7) if state.value_cells[v]}
        for v in range(7):
            rem = self._remaining_domino_ids_containing_value(state, v)
            if rem:
                if board_values and v not in board_values:
                    continue  # MUST share value with board to expand connected component
                candidates.append((len(rem), v))
        if not candidates:
            return None
        candidates.sort()
        if self.randomize_tiebreaks:
            import random
            best_count = candidates[0][0]
            best_cands = [c[1] for c in candidates if c[0] == best_count]
            return random.choice(best_cands)
        return candidates[0][1]

    def _choose_next_domino_for_stage(self, state, active_value, remaining, edges):
        """MRV with duplicate dedup: only evaluate one ID per domino type.
        Only considers dominos that HAVE > 0 valid placements on the restricted edges."""
        best_cands = []
        best_count = 10**9
        seen_types = set()
        for domino_id in sorted(remaining):
            dt = self.domino_by_id[domino_id].values()
            if dt in seen_types:
                continue
            seen_types.add(dt)
            count = len(self._generate_stage_placements(state, active_value, domino_id, edges))
            
            if count > 0:
                if count < best_count:
                    best_count = count
                    best_cands = [domino_id]
                elif count == best_count:
                    best_cands.append(domino_id)
        if not best_cands:
            return None
        if self.randomize_tiebreaks:
            import random
            return random.choice(best_cands)
        return best_cands[0]

    def _remaining_domino_ids_containing_value(self, state, v):
        return {d for d in state.unplaced_domino_ids if self.domino_by_id[d].has_value(v)}

    # ── Placement generation ─────────────────────────────────────────────

    def _generate_stage_placements(self, state, active_value, domino_id, edges):
        """Generate only LEGAL placements (Rule 3 checked inline)."""
        domino = self.domino_by_id[domino_id]
        out: List[Placement] = []

        candidate_edges = edges

        if not state.placed and self.anchor_center and domino_id == 0:
            candidate_edges = [
                (c0, c1) for c0, c1 in candidate_edges
                if c0 == self.center or c1 == self.center
            ]

        if domino.a == domino.b:
            orientations = [(domino.a, domino.b)]
        else:
            orientations = [(domino.a, domino.b), (domino.b, domino.a)]

        for c0, c1 in candidate_edges:
            if c0 in state.occupied_cells or c1 in state.occupied_cells:
                continue
            for v0, v1 in orientations:
                if v0 != active_value and v1 != active_value:
                    continue
                # Full Rule 3: check ALL values, not just active.
                # This catches cross-stage conflicts immediately.
                legal = True
                for cell, v_cell, partner in ((c0, v0, c1), (c1, v1, c0)):
                    for nbr in self.adj[cell]:
                        if nbr == partner:
                            continue
                        if nbr in state.occupied_cells:
                            if state.cell_value[nbr] != v_cell:
                                legal = False
                                break
                    if not legal:
                        break
                if legal:
                    out.append(Placement(domino_id, c0, c1, v0, v1))
        
        if self.randomize_tiebreaks:
            import random
            random.shuffle(out)
            
        return out

    def _candidate_empty_edges_for_active_value(self, state, active_value):
        active_cells = state.value_cells[active_value]
        global_edges = self._candidate_empty_edges(state)
        if not active_cells:
            return global_edges
            
        out = []
        for edge in global_edges:
            c0, c1 = edge
            touch = False
            for nbr in self.adj[c0]:
                if nbr in active_cells:
                    touch = True
                    break
            if not touch:
                for nbr in self.adj[c1]:
                    if nbr in active_cells:
                        touch = True
                        break
            if touch:
                out.append(edge)
        return out

    def _candidate_empty_edges(self, state: BoardState) -> List[Tuple[Cell, Cell]]:
        """OPTIMIZATION: frontier-restricted edges. When cells are already placed,
        only generate edges where at least one cell is adjacent to the occupied
        region. This guarantees Rule 1 (connectivity) incrementally."""
        if not state.occupied_cells:
            edges = []
            for c0 in self.allowed_cells:
                for c1 in self.adj[c0]:
                    if c0 < c1:
                        edges.append((c0, c1))
            return edges

        seen: Set[Tuple[Cell, Cell]] = set()
        edges: List[Tuple[Cell, Cell]] = []
        for occ in state.occupied_cells:
            for frontier in self.adj[occ]:
                if frontier in state.occupied_cells:
                    continue
                for partner in self.adj[frontier]:
                    if partner in state.occupied_cells:
                        continue
                    edge = (min(frontier, partner), max(frontier, partner))
                    if edge not in seen:
                        seen.add(edge)
                        edges.append(edge)
        return edges

    # ── Legality & feasibility ───────────────────────────────────────────

    def _placement_is_legal_for_stage(self, state, active_value, p):
        if p.c0 in state.occupied_cells or p.c1 in state.occupied_cells:
            return False
        if not p.has_value(active_value):
            return False
        # Inline Rule 3 check — NO cloning needed.
        # For each cell of the placement, check non-partner occupied neighbors.
        for cell, v_cell, partner in ((p.c0, p.v0, p.c1), (p.c1, p.v1, p.c0)):
            for nbr in self.adj[cell]:
                if nbr == partner:
                    continue
                if nbr not in state.occupied_cells:
                    continue
                v_nbr = state.cell_value[nbr]
                if active_value in (v_cell, v_nbr) and v_cell != v_nbr:
                    return False
        return True

    def _stage_prefix_feasible(self, state, active_value):
        if not self._active_value_bridgeable(state, active_value):
            return False
        return True

    def _stage_accepts(self, state, active_value):
        if self._remaining_domino_ids_containing_value(state, active_value):
            return False
        if not self._rule2_holds_for_value(state, active_value):
            return False
        if not self._rule3_holds_for_value(state, active_value):
            return False
        return True

    def _active_value_bridgeable(self, state, active_value):
        cells = state.value_cells[active_value]
        if len(cells) <= 1:
            return True
        
        # Count connected components
        remaining = set(cells)
        components = 0
        while remaining:
            components += 1
            start = next(iter(remaining))
            stack = [start]
            remaining.remove(start)
            while stack:
                u = stack.pop()
                for w in self.adj[u]:
                    if w in remaining:
                        remaining.remove(w)
                        stack.append(w)
                        
        remaining_dominos = len(self._remaining_domino_ids_containing_value(state, active_value))
        return remaining_dominos >= components - 1

    def _final_rules_hold(self, state):
        if not self._is_connected(state.occupied_cells):
            return False
        for v in range(7):
            if state.value_cells[v] and not self._rule2_holds_for_value(state, v):
                return False
            if not self._rule3_holds_for_value(state, v):
                return False
        return True

    def _rule2_holds_for_value(self, state, v):
        cells = state.value_cells[v]
        return len(cells) <= 1 or self._is_connected(cells)

    def _rule3_holds_for_value(self, state, v):
        for cell in state.value_cells[v]:
            for nbr in self.adj[cell]:
                if nbr not in state.occupied_cells:
                    continue
                if nbr == state.paired_with[cell]:
                    continue
                if state.cell_value[nbr] != v:
                    return False
        return True

    def _is_connected(self, cells):
        if not cells:
            return True
        start = next(iter(cells))
        seen = {start}
        stack = [start]
        while stack:
            u = stack.pop()
            for w in self.adj[u]:
                if w in cells and w not in seen:
                    seen.add(w)
                    stack.append(w)
        return len(seen) == len(cells)

    def _make_stage_key(self, state, active_value):
        # Use remaining domino types (multiset) instead of placed IDs.
        # This merges states that differ only by which duplicate ID was placed.
        remaining_types = tuple(sorted(
            self.domino_by_id[d].values()
            for d in state.unplaced_domino_ids
        ))
        return StageConfigKey(
            active_value=active_value,
            remaining_domino_types=remaining_types,
            cell_values=tuple(sorted(state.cell_value.items())),
            occupied_cells=tuple(sorted(state.occupied_cells)),
        )

    # ── Display ──────────────────────────────────────────────────────────

    def render_solution(self, solution):
        lines = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                cell = (r, c)
                if cell not in self.allowed_cells:
                    row.append("#")
                elif cell in solution.cell_value:
                    row.append(str(solution.cell_value[cell]))
                else:
                    row.append(".")
            lines.append(" ".join(row))
        return "\n".join(lines)

    def describe_solution(self, solution):
        out = []
        for domino_id, p in sorted(solution.placed.items()):
            out.append((p.c0, p.c1, p.v0, p.v1))
        return out


if __name__ == "__main__":
    import time
    def run_test(label, dominoes, rows=10, cols=10):
        print(f"\n=== {label} ===")
        solver = DominoStageSolver(rows, cols, dominoes, anchor_center=False)
        t0 = time.time()
        sol = solver.solve_with_restarts(
            max_restarts=100, 
            initial_max_nodes=5000, 
            restart_multiplier=1.2,
            absolute_max_nodes=10000
        )
        elapsed = time.time() - t0
        if sol is None:
            print(f"No solution  ({elapsed:.2f}s, {solver.nodes} nodes final run)")
        else:
            print(solver.render_solution(sol))
            print(f"({elapsed:.2f}s, {solver.nodes} nodes final run)")

    run_test("Easy", [
        (0,1),(0,1),(1,1),(1,2),(2,2),(2,3),(3,3),
        (3,4),(4,4),(4,5),(5,5),(5,6),(6,6),(0,6),
    ])

    solvable_samples = [
        [(0, 1), (0, 1), (0, 2), (0, 6), (1, 1), (1, 4), (2, 2), (2, 2), (2, 4), (2, 6), (3, 4), (3, 5), (3, 5), (4, 5)],
        [(0, 0), (0, 1), (0, 1), (0, 1), (0, 6), (1, 3), (1, 4), (1, 5), (1, 5), (1, 6), (2, 5), (3, 3), (4, 6), (6, 6)],
        [(0, 1), (0, 2), (0, 6), (1, 6), (2, 5), (2, 6), (2, 6), (3, 3), (3, 3), (3, 4), (3, 6), (4, 6), (4, 6), (6, 6)],
        [(0, 0), (0, 1), (0, 6), (1, 5), (1, 6), (2, 3), (2, 5), (4, 5), (4, 6), (5, 5), (5, 5), (5, 6), (5, 6), (5, 6)],
        [(0, 0), (0, 2), (0, 4), (0, 6), (1, 1), (1, 2), (1, 3), (1, 3), (1, 6), (3, 5), (3, 6), (4, 4), (4, 5), (4, 5)],
        [(0, 0), (0, 5), (1, 3), (1, 6), (2, 4), (2, 5), (2, 5), (2, 6), (3, 6), (3, 6), (4, 5), (5, 5), (5, 5), (5, 6)],
        [(0, 1), (0, 1), (1, 2), (1, 2), (1, 5), (1, 5), (2, 3), (2, 3), (2, 3), (2, 5), (3, 4), (3, 5), (3, 5), (4, 6)],
        [(0, 0), (0, 1), (1, 4), (2, 6), (3, 4), (3, 5), (3, 5), (3, 5), (3, 6), (3, 6), (3, 6), (4, 6), (4, 6), (4, 6)],
        [(0, 0), (0, 1), (0, 4), (1, 2), (1, 2), (1, 2), (1, 3), (1, 3), (1, 4), (1, 6), (2, 4), (2, 6), (3, 5), (4, 4)],
        [(0, 0), (0, 3), (1, 3), (1, 5), (1, 6), (1, 6), (2, 3), (2, 4), (2, 4), (3, 4), (4, 4), (4, 5), (4, 5), (5, 6)],
        [(0, 0), (0, 3), (0, 4), (0, 4), (0, 6), (1, 1), (1, 4), (2, 2), (2, 4), (2, 5), (2, 6), (4, 5), (4, 6), (5, 5)],
        [(0, 1), (0, 2), (0, 3), (0, 4), (0, 4), (0, 5), (0, 5), (0, 6), (1, 2), (1, 5), (2, 2), (3, 6), (4, 5), (5, 5)],
        [(0, 4), (0, 6), (0, 6), (1, 4), (1, 5), (2, 2), (2, 3), (2, 4), (2, 4), (2, 5), (2, 5), (2, 6), (2, 6), (5, 5)],
        [(0, 1), (0, 4), (0, 5), (0, 6), (0, 6), (0, 6), (0, 6), (1, 2), (1, 3), (1, 5), (1, 6), (2, 2), (4, 5), (5, 5)]
    ]
    for i, doms in enumerate(solvable_samples):
        run_test(f"solvable.txt #{i+1}", doms)