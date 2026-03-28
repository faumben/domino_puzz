import sys, time
sys.path.insert(0, r'c:\Users\faumb\PycharmProjects\domino_puzzle')
from solver.SolverV2 import DominoStageSolver

solver = DominoStageSolver(10, 10, [
    (0,1),(0,1),(1,1),(1,2),(2,2),(2,3),(3,3),
    (3,4),(4,4),(4,5),(5,5),(5,6),(6,6),(0,6),
])
t0 = time.time()
sol = solver.solve()
elapsed = time.time() - t0
if sol:
    print("FOUND", f"({elapsed:.2f}s, {solver.nodes} nodes)")
    print(solver.render_solution(sol))
else:
    print("No solution", f"({elapsed:.2f}s, {solver.nodes} nodes)")
