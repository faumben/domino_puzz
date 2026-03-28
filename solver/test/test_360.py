import sys
sys.path.insert(0, r'c:\Users\faumb\PycharmProjects\domino_puzzle')
from solver.SolverV2 import DominoStageSolver

doms = [(0, 0), (0, 1), (0, 6), (1, 5), (1, 6), (2, 3), (2, 5), (4, 5), (4, 6), (5, 5), (5, 5), (5, 6), (5, 6), (5, 6)]

import time
t0 = time.time()
solver = DominoStageSolver(10, 10, doms, anchor_center=False)
sol = solver.solve()
print(f"Time: {time.time()-t0:.2f}s, Nodes: {solver.nodes}, Solved: {sol is not None}")
