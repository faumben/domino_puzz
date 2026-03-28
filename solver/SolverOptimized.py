import time
import random
from collections import defaultdict
from typing import Set, Tuple, List, Optional, Dict
from dataclasses import dataclass

Cell = Tuple[int, int]
DominoInput = Tuple[int, int]

@dataclass(frozen=True)
class Placement:
    domino_id: int
    c0: int
    c1: int
    v0: int
    v1: int

class Domino:
    def __init__(self, a: int, b: int):
        self.a = min(a, b)
        self.b = max(a, b)
    def __repr__(self):
        return f"({self.a},{self.b})"
    def has_value(self, v: int) -> bool:
        return self.a == v or self.b == v
    def values(self):
        return (self.a, self.b)

class BoardState1D:
    def __init__(self, size: int):
        self.size = size
        self.placements: List[Placement] = []
        
        # 1D array of integers [0..6, or -1 if empty]
        self.cell_value = [-1] * size
        
        # 1D array of partnered cell indices [-1 if empty]
        self.paired_with = [-1] * size
        
        # Bitmasks for blazing fast arbitrary-precision integer sets
        self.occupied_mask = 0
        self.value_masks = [0] * 7
        
        self.unplaced_domino_ids = set()
        self.locked_values = set()
        self.current_value = None

    def add_placement(self, p: Placement):
        self.placements.append(p)
        self.unplaced_domino_ids.remove(p.domino_id)
        
        idx0, idx1 = p.c0, p.c1
        v0, v1 = p.v0, p.v1
        
        self.cell_value[idx0] = v0
        self.cell_value[idx1] = v1
        
        self.paired_with[idx0] = idx1
        self.paired_with[idx1] = idx0
        
        self.occupied_mask |= (1 << idx0) | (1 << idx1)
        self.value_masks[v0] |= (1 << idx0)
        self.value_masks[v1] |= (1 << idx1)

    def remove_placement(self, p: Placement):
        self.placements.pop()
        self.unplaced_domino_ids.add(p.domino_id)
        
        idx0, idx1 = p.c0, p.c1
        v0, v1 = p.v0, p.v1
        
        self.cell_value[idx0] = -1
        self.cell_value[idx1] = -1
        
        self.paired_with[idx0] = -1
        self.paired_with[idx1] = -1
        
        self.occupied_mask &= ~((1 << idx0) | (1 << idx1))
        self.value_masks[v0] &= ~(1 << idx0)
        self.value_masks[v1] &= ~(1 << idx1)

    def clone(self) -> 'BoardState1D':
        s = BoardState1D(self.size)
        s.placements = list(self.placements)
        s.cell_value = list(self.cell_value)
        s.paired_with = list(self.paired_with)
        s.occupied_mask = self.occupied_mask
        s.value_masks = list(self.value_masks)
        s.unplaced_domino_ids = set(self.unplaced_domino_ids)
        s.locked_values = set(self.locked_values)
        s.current_value = self.current_value
        return s

@dataclass(frozen=True)
class StageConfigKey1D:
    active_value: int
    remaining_domino_types: Tuple[Tuple[int, int], ...]
    cell_values: Tuple[int, ...]
    occupied_mask: int


def iter_bits(mask: int):
    """Yields the set bit indices from a bitmask efficiently in pure Python."""
    while mask:
        lsb = mask & -mask
        yield lsb.bit_length() - 1
        mask ^= lsb


class DominoOptimizedSolver:
    """
    A blisteringly fast 1D-flattened, pure Bitwise rewrite of the DominoStageSolver.
    Uses arbitrary-precision integers natively calculated in C-space to completely 
    bypass Python Dictionary, Tupple, and Set hashing overhead. 
    """
    def __init__(
        self,
        rows: int = 10,
        cols: int = 10,
        dominoes: List[DominoInput] = None,
        allowed_cells: Optional[Set[Cell]] = None,
        anchor_center: bool = False,
        randomize_tiebreaks: bool = False,
        max_nodes_per_restart: Optional[int] = None,
    ):
        self.rows = rows
        self.cols = cols
        self.size = rows * cols
        
        if dominoes is None:
            dominoes = []
        self.dominoes = [Domino(a, b) for a, b in dominoes]
        self.domino_by_id = {i: d for i, d in enumerate(self.dominoes)}
        self.domino_ids_by_value = defaultdict(set)
        for i, d in enumerate(self.dominoes):
            self.domino_ids_by_value[d.a].add(i)
            self.domino_ids_by_value[d.b].add(i)
            
        self.anchor_center = anchor_center
        self.randomize_tiebreaks = randomize_tiebreaks
        self.max_nodes = max_nodes_per_restart
        
        # Build allowed_mask
        if allowed_cells is None:
            self.allowed_mask = (1 << self.size) - 1
        else:
            self.allowed_mask = 0
            for r, c in allowed_cells:
                self.allowed_mask |= (1 << (r * self.cols + c))
                
        self.adj_list, self.adj_mask = self._build_adjacency()
        self.failed_stage_configs = set()
        self.nodes = 0
        
    def _build_adjacency(self):
        adj_list = [[] for _ in range(self.size)]
        adj_mask = [0] * self.size
        for r in range(self.rows):
            for c in range(self.cols):
                idx = r * self.cols + c
                if not (self.allowed_mask & (1 << idx)):
                    continue
                # check neighbors
                for nr, nc in ((r-1, c), (r+1, c), (r, c-1), (r, c+1)):
                    if 0 <= nr < self.rows and 0 <= nc < self.cols:
                        nidx = nr * self.cols + nc
                        if self.allowed_mask & (1 << nidx):
                            adj_list[idx].append(nidx)
                            adj_mask[idx] |= (1 << nidx)
        return adj_list, adj_mask
        
    def _initial_state(self) -> BoardState1D:
        s = BoardState1D(self.size)
        s.unplaced_domino_ids = set(range(len(self.dominoes)))
        return s
        
    def solve(self) -> Optional[BoardState1D]:
        state = self._initial_state()
        self.nodes = 0
        return self._solve_from_stage(state)
        
    def solve_with_restarts(
        self, 
        max_restarts=100, 
        initial_max_nodes=5000,
        restart_multiplier=1.2,
        absolute_max_nodes=10000
    ) -> Optional[BoardState1D]:
        import time
        orig_randomize = self.randomize_tiebreaks
        orig_max_nodes = self.max_nodes
        
        self.randomize_tiebreaks = True
        current_max_nodes = float(initial_max_nodes)
        
        try:
            for i in range(max_restarts):
                self.max_nodes = min(int(current_max_nodes), absolute_max_nodes)
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
            
    def _solve_from_stage(self, state: BoardState1D) -> Optional[BoardState1D]:
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
            
        edges = self._candidate_empty_edges_for_active_value(state, active_value)
        if not edges and state.occupied_mask:
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

            state.add_placement(p)
            if self._stage_prefix_feasible(state, active_value):
                solved = self._enumerate_stage_configurations(state, active_value, next_remaining)
                if solved is not None:
                    return solved
            state.remove_placement(p)
            
        self.failed_stage_configs.add(key)
        return None
        
    def _choose_next_value(self, state):
        candidates = []
        board_values = {v for v in range(7) if state.value_masks[v]}
        for v in range(7):
            rem = self._remaining_domino_ids_containing_value(state, v)
            if rem:
                if board_values and v not in board_values:
                    continue 
                candidates.append((len(rem), v))
        if not candidates:
            return None
            
        candidates.sort()
        if self.randomize_tiebreaks:
            best_count = candidates[0][0]
            best_cands = [c[1] for c in candidates if c[0] == best_count]
            return random.choice(best_cands)
        return candidates[0][1]
        
    def _choose_next_domino_for_stage(self, state, active_value, remaining, edges):
        best_cands = []
        best_count = 10**9
        seen_types = set()
        
        for domino_id in sorted(remaining):
            dt = self.domino_by_id[domino_id].values()
            if dt in seen_types:
                continue
            seen_types.add(dt)
            count = len(self._generate_stage_placements(state, active_value, domino_id, edges))
            
            if count < best_count:
                best_count = count
                best_cands = [domino_id]
            elif count == best_count:
                best_cands.append(domino_id)
                    
        if not best_cands:
            return None
            
        if self.randomize_tiebreaks:
            return random.choice(best_cands)
        return best_cands[0]
        
    def _remaining_domino_ids_containing_value(self, state, v):
        return {d for d in state.unplaced_domino_ids if self.domino_by_id[d].has_value(v)}
        
    def _generate_stage_placements(self, state, active_value, domino_id, candidate_edges):
        out = []
        d = self.domino_by_id[domino_id]
        
        for c0, c1 in candidate_edges:
            orientations = [(d.a, d.b)]
            if d.a != d.b:
                orientations.append((d.b, d.a))
                
            for v0, v1 in orientations:
                if v0 != active_value and v1 != active_value:
                    continue
                    
                legal = True
                
                # Rule 3: Mismatched adjacent pip values are not allowed (Same color touching)
                # Check c0's neighbors
                if (self.adj_mask[c0] & state.occupied_mask) & ~(1 << c1):
                    if (self.adj_mask[c0] & state.occupied_mask) & ~(1 << c1) & ~state.value_masks[v0]:
                        legal = False
                if not legal: continue

                # Check c1's neighbors
                if (self.adj_mask[c1] & state.occupied_mask) & ~(1 << c0):
                    if (self.adj_mask[c1] & state.occupied_mask) & ~(1 << c0) & ~state.value_masks[v1]:
                        legal = False
                        
                if legal:
                    out.append(Placement(domino_id, c0, c1, v0, v1))
                    
        if self.randomize_tiebreaks:
            random.shuffle(out)
        return out

    def _candidate_empty_edges_for_active_value(self, state: BoardState1D, active_value: int):
        active_mask = state.value_masks[active_value]
        global_edges = self._candidate_empty_edges(state)
        if not active_mask: return global_edges
        
        out = []
        for c0, c1 in global_edges:
            # 1 bitwise operation checks all neighbors simultaneously!
            if (self.adj_mask[c0] & active_mask) or (self.adj_mask[c1] & active_mask):
                out.append((c0, c1))
        return out
        
    def _candidate_empty_edges(self, state: BoardState1D):
        out = []
        occupied = state.occupied_mask
        empty_mask = self.allowed_mask & ~occupied
        if not empty_mask:
            return out
            
        seen_edges = set()
        
        if not occupied:
            for idx in iter_bits(empty_mask):
                for nbr in self.adj_list[idx]:
                    if empty_mask & (1 << nbr):
                        edge = (min(idx, nbr), max(idx, nbr))
                        if edge not in seen_edges:
                            seen_edges.add(edge)
                            out.append(edge)
            return out
            
        for idx in iter_bits(occupied):
            for nbr in self.adj_list[idx]:
                if empty_mask & (1 << nbr):
                    for partner in self.adj_list[nbr]:
                        if empty_mask & (1 << partner):
                            edge = (min(nbr, partner), max(nbr, partner))
                            if edge not in seen_edges:
                                seen_edges.add(edge)
                                out.append(edge)
        return out
        
    def _stage_prefix_feasible(self, state, active_value) -> bool:
        return self._active_value_bridgeable(state, active_value)
        
    def _active_value_bridgeable(self, state, active_value) -> bool:
        value_mask = state.value_masks[active_value]
        if not value_mask:
            return True
            
        components = 0
        rem_mask = value_mask
        
        while rem_mask:
            components += 1
            lsb = rem_mask & -rem_mask
            
            seen = lsb
            stack = [lsb.bit_length() - 1]
            while stack:
                u = stack.pop()
                unseen = (self.adj_mask[u] & value_mask) & ~seen
                while unseen:
                    lsr = unseen & -unseen
                    seen |= lsr
                    stack.append(lsr.bit_length() - 1)
                    unseen ^= lsr
                    
            rem_mask &= ~seen
            
        rem_count = len(self._remaining_domino_ids_containing_value(state, active_value))
        return (components - 1) <= rem_count
        
    def _is_connected(self, mask: int) -> bool:
        if not mask: return True
        lsb = mask & -mask
        
        seen = lsb
        stack = [lsb.bit_length() - 1]
        while stack:
            u = stack.pop()
            unseen = (self.adj_mask[u] & mask) & ~seen
            while unseen:
                lsr = unseen & -unseen
                seen |= lsr
                stack.append(lsr.bit_length() - 1)
                unseen ^= lsr
                
        return seen == mask
        
    def _rule2_holds_for_value(self, state, value) -> bool:
        return self._is_connected(state.value_masks[value])

    def _stage_accepts(self, state, active_value) -> bool:
        return self._rule2_holds_for_value(state, active_value)

    def _final_rules_hold(self, state) -> bool:
        if not state.unplaced_domino_ids:
            # Check connectedness of all 7 values
            for v in range(7):
                if not self._rule2_holds_for_value(state, v):
                    return False
            return True
        return False

    def _make_stage_key(self, state, active_value):
        remaining_types = tuple(sorted(
            self.domino_by_id[d].values()
            for d in state.unplaced_domino_ids
        ))
        
        return StageConfigKey1D(
            active_value=active_value,
            remaining_domino_types=remaining_types,
            cell_values=tuple(state.cell_value),
            occupied_mask=state.occupied_mask
        )
        
    def render_solution(self, solution: BoardState1D) -> str:
        lines = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                idx = r * self.cols + c
                if not (self.allowed_mask & (1 << idx)):
                    row.append("#")
                elif solution.cell_value[idx] != -1:
                    row.append(str(solution.cell_value[idx]))
                else:
                    row.append(".")
            lines.append(" ".join(row))
        return "\n".join(lines)


#----#


if __name__ == "__main__":
    import time
    def run_test(label, dominoes, rows=10, cols=10):
        print(f"\n=== {label} ===")
        
        solver = DominoOptimizedSolver(rows, cols, dominoes, anchor_center=False)
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



#TODO THIS DOES NOT RESPECT THE 3RD RULE THAT ONLY PIP VALUES OF SAME COLOR CAN TOUCH