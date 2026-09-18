import json, os
from fastapi import FastAPI, Body, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from src.utils.DTOs import StepResponse
from src.utils.controllers.hivemind_policy import Hivemind

HOST = "0.0.0.0"
PORT = 9052

app = FastAPI(title="Survival Simulator Agent Endpoint")


@app.exception_handler(RequestValidationError)
async def dump_422(request: Request, exc: RequestValidationError):
    """A rejected /predict body is the one thing we cannot see from the platform side: keep it."""
    body = (await request.body()).decode("utf-8", "replace")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "predict_422.json"), "w", encoding="utf-8") as f:
        json.dump({"errors": exc.errors(), "body": body[:200000]}, f, indent=1, default=str)
    print("422 on", request.url.path, "->", [(e.get("loc"), e.get("msg")) for e in exc.errors()][:10], flush=True)
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
_ticks = 0
hivemind = Hivemind()  # one instance for the whole process; it resets itself when sim_time goes backwards (new game)

@app.post("/predict")
def predict(step: StepResponse = Body(...)):
    """
    Receives the current simulation state and returns actions for all agents.
    """
    global _ticks
    d = step.dict()
    if d["sim_time"] is None:            # verify sample has no clock: count ticks (0.1 s each) ourselves
        _ticks += 1
        d["sim_time"] = _ticks * 0.1
    for a in d["agent_status"]:          # the verify sample uses lowercase types ("tree"); the simulator uses "Tree"
        for o in a["observations"]:
            t = o.get("type")
            if isinstance(t, str) and t[:1].islower():
                o["type"] = t[:1].upper() + t[1:]
    actions = [a.dict() for a in hivemind.decide(d)]

    # Must return {"actions": [...]} format
    return {"actions": actions}

@app.get("/")
def index():
    return {"message": "Agent endpoint running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
