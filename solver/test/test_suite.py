import os
import sys

# Ensure the project root is in sys.path so "from solver.X" works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import cProfile
import pstats

# Ensure solver package is reachable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solver.SolverV2 import DominoStageSolver
from solver.SolverParallel import DominoParallelSolver
from solver.SolverOptimized import DominoOptimizedSolver

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

def run_suite(SolverClass, label: str):
    print(f"\n==========================================")
    print(f"Running Test Suite for: {label}")
    print(f"==========================================")
    
    pr = cProfile.Profile()
    pr.enable()
    
    total_time = 0
    total_nodes = 0
    successes = 0
    
    for i, doms in enumerate(solvable_samples):
        solver = SolverClass(10, 10, doms, anchor_center=False)
        t0 = time.time()
        
        # Parallel solver requires different instantiation/method if different
        if hasattr(solver, 'solve_with_restarts'):
            sol = solver.solve_with_restarts(
                max_restarts=100000, 
                initial_max_nodes=5000, 
                restart_multiplier=1.2, 
                absolute_max_nodes=10000
            )
        else:
            sol = solver.solve()
            
        elapsed = time.time() - t0
        total_time += elapsed
        total_nodes += solver.nodes
        
        if sol is None:
            print(f"Puzzle #{i+1:02d}: NO SOLUTION ({elapsed:5.2f}s, {solver.nodes:6d} nodes across all workers)")
        else:
            print(f"Puzzle #{i+1:02d}: FOUND       ({elapsed:5.2f}s, {solver.nodes:6d} nodes across all workers)")
            successes += 1
            
    pr.disable()
    
    # Save profile out to solver/profiling directory
    output_filename = f"profile_{label.replace(' ', '_')}.txt"
    profiling_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'profiling')
    os.makedirs(profiling_dir, exist_ok=True)
    output_path = os.path.join(profiling_dir, output_filename)
    
    with open(output_path, 'w') as f:
        f.write(f"--- {label} Performance ---\n")
        f.write(f"Success Rate: {successes} / {len(solvable_samples)}\n")
        f.write(f"Total Time: {total_time:.2f}s\n")
        f.write(f"Total Nodes Processed: {total_nodes}\n")
        f.write(f"Average Global Speed: {total_nodes/max(total_time, 0.001):.0f} nodes/sec\n")
        f.write("(Note: Profile times below for Parallel workers only show main-thread wait times, not worker processing times)\n\n")
        
        ps = pstats.Stats(pr, stream=f).sort_stats('tottime')
        ps.print_stats(30)
        
    print(f"\nSuite complete! {successes}/{len(solvable_samples)} solved.")
    print(f"Profile safely saved to: solver/profiling/{output_filename}")

if __name__ == "__main__":
    print("\n\n" + "="*50)
    print("STARTING FULL BENCHMARK SUITE")
    print("="*50)

    # 1. Sync V2
    # run_suite(DominoStageSolver, "SolverV2_Sync_Baseline")
    
    # 2. Sync Optimized
    # run_suite(DominoOptimizedSolver, "SolverOptimized_Sync")
    
    # 3. Parallel V2
    # run_suite(lambda r,c,d,**kwargs: DominoParallelSolver(r, c, d, engine="v2", **kwargs), "SolverParallel_V2")

    # 4. Parallel Optimized
    run_suite(lambda r,c,d,**kwargs: DominoParallelSolver(r, c, d, engine="optimized", **kwargs), "SolverParallel_Optimized")
