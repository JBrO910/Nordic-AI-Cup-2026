"""Start agent_server, drive it with a real sim for N ticks over HTTP, check reset on a second game, report latency."""
import subprocess, sys, time, requests, statistics, pygame; pygame.init(); sys.path.insert(0, ".")
from src.core import SimulationCore
from src.utils.DTOs import StepResponse, ObservationResponse, ActionRequest
srv = subprocess.Popen([sys.executable, "agent_server.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            if requests.get("http://127.0.0.1:9052/", timeout=1).status_code == 200: break
        except Exception: time.sleep(0.5)
    def play(seed, ticks):
        sim = SimulationCore(seed=seed); state = sim.step([]); lat = []; pop = []
        for _ in range(ticks):
            status = [ObservationResponse(**{k: o[k] for k in ("agent_id","observations","energy","biome","age","speed","sprint_speed","hearing_radius","vision_angle","vision_range","max_energy")}) for o in state["observations"]]
            step = StepResponse(game_status="ok", score=state["score"], sim_time=state["sim_time"], n_agents=state["num_agents"], agent_status=status)
            t0 = time.perf_counter(); r = requests.post("http://127.0.0.1:9052/predict", json=step.dict(), timeout=10); lat.append(time.perf_counter() - t0)
            acts = [ActionRequest(**a) for a in r.json()["actions"]]
            state = sim.step([(a.agent_id, a) for a in acts]); pop.append(state["num_agents"])
        return lat, pop, state["score"]
    lat1, pop1, s1 = play(1, 600)
    lat2, pop2, s2 = play(2, 300)   # second game on the same server process: sim_time restarts at 0
    print(f"game1 600 ticks: score {s1:.1f}, pop {pop1[-1]}, latency mean {statistics.mean(lat1)*1000:.1f} ms max {max(lat1)*1000:.1f} ms")
    print(f"game2 300 ticks: score {s2:.1f}, pop {pop2[-1]}, latency mean {statistics.mean(lat2)*1000:.1f} ms max {max(lat2)*1000:.1f} ms")
finally:
    srv.terminate()
