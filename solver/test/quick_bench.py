import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from solver.SolverV2 import DominoStageSolver
from solver.SolverOptimized import DominoOptimizedSolver
from solver.SolverParallel import DominoParallelSolver

from solver.test.test_suite import solvable_samples

def benchmark():
    # Pick a solid multi-restart puzzle
    sample = solvable_samples[1] 
    
    print("="*60)
    print(f"BENCHMARKING DOMINO ENGINES (Puzzle #02)")
    print("="*60)
    print("Running Baseline V2 (Single Core)...")
    
    # 1. Baseline
    t0 = time.time()
    s1 = DominoStageSolver(10, 10, sample, anchor_center=False)
    sol1 = s1.solve_with_restarts(max_restarts=100, initial_max_nodes=5000, absolute_max_nodes=10000)
    t1 = time.time()
    n1 = s1.nodes
    out1 = f"[{'SOLVED' if sol1 else 'FAIL'}] {t1-t0:6.2f}s | {n1:8d} nodes | {int(n1/(t1-t0))} nodes/sec"
    print(" " + out1)
    
    # 2. Optimized
    print("Running Optimized 1D (Single Core)...")
    t0 = time.time()
    s2 = DominoOptimizedSolver(10, 10, sample, anchor_center=False)
    sol2 = s2.solve_with_restarts(max_restarts=100, initial_max_nodes=5000, absolute_max_nodes=10000)
    t1 = time.time()
    n2 = s2.nodes
    out2 = f"[{'SOLVED' if sol2 else 'FAIL'}] {t1-t0:6.2f}s | {n2:8d} nodes | {int(n2/(t1-t0))} nodes/sec"
    print(" " + out2)
    
    # 3. Parallel V2
    print("Running V2 (Multi-Core)...")
    t0 = time.time()
    s3 = DominoParallelSolver(10, 10, sample, anchor_center=False, engine="v2")
    sol3 = s3.solve_with_restarts(max_restarts=100, initial_max_nodes=5000, absolute_max_nodes=10000)
    t1 = time.time()
    n3 = s3.nodes
    out3 = f"[{'SOLVED' if sol3 else 'FAIL'}] {t1-t0:6.2f}s | {n3:8d} nodes | {int(n3/(t1-t0))} nodes/sec"
    print(" " + out3)
    
    # 4. Parallel Optimized
    print("Running Optimized 1D (Multi-Core)...")
    t0 = time.time()
    s4 = DominoParallelSolver(10, 10, sample, anchor_center=False, engine="optimized")
    sol4 = s4.solve_with_restarts(max_restarts=100, initial_max_nodes=5000, absolute_max_nodes=10000)
    t1 = time.time()
    n4 = s4.nodes
    out4 = f"[{'SOLVED' if sol4 else 'FAIL'}] {t1-t0:6.2f}s | {n4:8d} nodes | {int(n4/(t1-t0))} nodes/sec"
    print(" " + out4)
    
    print("\nRESULTS:")
    print("="*60)
    print(f"V2 (Sync):         {out1}")
    print(f"Optimized (Sync):  {out2}")
    print(f"V2 (Parallel):     {out3}")
    print(f"Optimized (Par.):  {out4}")
    print("="*60)

if __name__ == "__main__":
    benchmark()
