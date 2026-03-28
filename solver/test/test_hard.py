import sys, time
sys.path.insert(0, r'c:\Users\faumb\PycharmProjects\domino_puzzle')
from solver.SolverV2 import DominoStageSolver

# Test with anchor_center=False
solver = DominoStageSolver(10, 10, [
    (0,1),(0,3),(0,5),(1,1),(1,4),(1,4),(1,6),
    (1,6),(2,2),(2,3),(2,4),(2,4),(2,6),(3,4),
], anchor_center=False)

# Disable memoization too (empty the check)
solver.failed_stage_configs = set()

t0 = time.time()
sol = solver.solve()
elapsed = time.time() - t0
if sol:
    print("FOUND", f"({elapsed:.2f}s, {solver.nodes} nodes)")
    print(solver.render_solution(sol))
else:
    print("No solution", f"({elapsed:.2f}s, {solver.nodes} nodes)")
