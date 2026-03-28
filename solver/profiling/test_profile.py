import sys, time, cProfile, pstats
sys.path.insert(0, r'c:\Users\faumb\PycharmProjects\domino_puzzle')
from solver.SolverV2 import DominoStageSolver

solver = DominoStageSolver(10, 10, [
    (0,1),(0,3),(0,5),(1,1),(1,4),(1,4),(1,6),
    (1,6),(2,2),(2,3),(2,4),(2,4),(2,6),(3,4),
])

solver._deadline = time.time() + 10
orig = solver._enumerate_stage_configurations

class TimeoutError(Exception):
    pass

def patched(ss, av, rem):
    if time.time() > solver._deadline:
        raise TimeoutError()
    return orig(ss, av, rem)

solver._enumerate_stage_configurations = patched

pr = cProfile.Profile()
pr.enable()
t0 = time.time()
try:
    sol = solver.solve()
except TimeoutError:
    pass
pr.disable()
elapsed = time.time() - t0

with open(r'c:\Users\faumb\PycharmProjects\domino_puzzle\solver\profiling\profile_out.txt', 'w') as f:
    f.write(f"Ran for {elapsed:.1f}s, {solver.nodes} nodes ({solver.nodes/max(elapsed,0.001):.0f} nodes/sec)\n")
    f.write(f"Cache: {len(solver.failed_stage_configs)} entries\n\n")
    ps = pstats.Stats(pr, stream=f).sort_stats('tottime')
    ps.print_stats(20)

print("Profile written to profile_out.txt")
