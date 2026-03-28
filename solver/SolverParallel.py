import sys
import os
import random
import time
import concurrent.futures
import multiprocessing
from typing import Optional, List, Tuple, Set

# Ensure we can import solver modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solver.SolverV2 import DominoStageSolver, DominoInput, Cell, BoardState, Placement
from solver.SolverOptimized import DominoOptimizedSolver

def _worker_task(worker_id: int, rows: int, cols: int, dominoes: List[DominoInput], 
                 allowed_cells: Optional[Set[Cell]], max_nodes: int, engine: str, seed: int) -> Tuple[Optional[BoardState], int]:
    if engine == "optimized":
        solver = DominoOptimizedSolver(
            rows=rows, cols=cols, dominoes=dominoes, allowed_cells=allowed_cells, 
            anchor_center=False, randomize_tiebreaks=True, max_nodes_per_restart=max_nodes
        )
    else:
        solver = DominoStageSolver(
            rows=rows, cols=cols, dominoes=dominoes, allowed_cells=allowed_cells, 
            anchor_center=False
        )
        solver.randomize_tiebreaks = True
        solver.max_nodes = max_nodes
        solver.nodes = 0
        solver.failed_stage_configs.clear()
    
    import random
    random.seed(seed)
    
    try:
        if engine == "optimized":
            sol = solver.solve()
            return sol, solver.nodes
        else:
            state = solver._initial_state()
            sol = solver._solve_from_stage(state)
            return sol, solver.nodes
    except Exception:
        return None, getattr(solver, 'nodes', getattr(solver, 'nodes_explored', 0))

class DominoParallelSolver:
    def __init__(self, rows: int, cols: int, dominoes: List[DominoInput], allowed_cells=None, anchor_center: bool = False, engine: str = 'v2'):
        self.rows = rows
        self.cols = cols
        self.dominoes = dominoes
        self.allowed_cells = allowed_cells
        self.anchor_center = anchor_center
        self.nodes = 0
        self.engine = engine
        
    def solve_with_restarts(
        self, 
        max_restarts=100, 
        initial_max_nodes=5000, 
        restart_multiplier=1.2, 
        absolute_max_nodes=10000, 
        timeout_seconds=None,
        workers: Optional[int] = None
    ) -> Optional[BoardState]:
        
        if workers is None:
            workers = multiprocessing.cpu_count()
            
        nodes_explored = 0
        current_max_nodes = float(initial_max_nodes)
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            active_futures = set()
            iteration = 0
            start_time = time.time()
            
            while iteration < max_restarts or active_futures:
                if timeout_seconds and time.time() - start_time > timeout_seconds:
                    for f in active_futures:
                        f.cancel()
                    self.nodes = nodes_explored
                    return None
                    
                # Keep the queue filled with just enough tasks to keep workers busy
                while len(active_futures) < workers * 2 and iteration < max_restarts:
                    args = (
                        iteration, self.rows, self.cols, self.dominoes, self.allowed_cells,
                        int(min(current_max_nodes, absolute_max_nodes)),
                        self.engine,
                        random.randint(0, 1000000000)
                    )
                    active_futures.add(executor.submit(_worker_task, *args))
                    current_max_nodes = min(current_max_nodes * restart_multiplier, float(absolute_max_nodes))
                    iteration += 1
                
                # Wait for at least one task to finish
                done, active_futures = concurrent.futures.wait(
                    active_futures, return_when=concurrent.futures.FIRST_COMPLETED
                )
                
                for future in done:
                    sol, nodes = future.result()
                    nodes_explored += nodes
                    if sol is not None:
                        # Cancel remaining
                        for f in active_futures:
                            f.cancel()
                        self.nodes = nodes_explored
                        return sol
                        
        self.nodes = nodes_explored
        return None

if __name__ == "__main__":
    def run_test(label, dominoes, rows=10, cols=10):
        print(f"\n=== {label} ===")
        solver = DominoParallelSolver(rows, cols, dominoes, anchor_center=False)
        t0 = time.time()
        sol = solver.solve_with_restarts(
            max_restarts=100, 
            initial_max_nodes=5000, 
            restart_multiplier=1.2,
            absolute_max_nodes=10000
        )
        elapsed = time.time() - t0
        
        # Borrow the renderer from V2 for printing
        v2dummy = DominoStageSolver(rows, cols, dominoes)
        if sol is None:
            print(f"No solution  ({elapsed:.2f}s, {solver.nodes} nodes across workers)")
        else:
            print(v2dummy.render_solution(sol))
            print(f"FOUND ({elapsed:.2f}s, {solver.nodes} nodes across workers)")

    run_test("Parallel Hard Test", [
        (0, 1), (0, 1), (0, 2), (0, 6), (1, 1), (1, 4), (2, 2), (2, 2), (2, 4), (2, 6), (3, 4), (3, 5), (3, 5), (4, 5)
    ])
