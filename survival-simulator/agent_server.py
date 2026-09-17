from fastapi import FastAPI, Body
from src.utils.DTOs import StepResponse
from src.utils.controllers.simple_policy import Hivemind

HOST = "0.0.0.0"
PORT = 9052

app = FastAPI(title="Survival Simulator Agent Endpoint")
hivemind = Hivemind()  # one instance for the whole process; it resets itself when sim_time goes backwards (new game)

@app.post("/predict")
def predict(step: StepResponse = Body(...)):
    """
    Receives the current simulation state and returns actions for all agents.
    """
    actions = [a.dict() for a in hivemind.decide(step.dict())]

    # Must return {"actions": [...]} format
    return {"actions": actions}

@app.get("/")
def index():
    return {"message": "Agent endpoint running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
