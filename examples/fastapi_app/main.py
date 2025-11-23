import asyncio
import logging

import logcost
from fastapi import FastAPI

app = FastAPI()
logger = logging.getLogger("logcost.examples.fastapi")
logger.setLevel(logging.INFO)


@app.get("/")
async def read_root():
    logger.info("Homepage accessed")
    await asyncio.sleep(0.01)
    return {"message": "Hello from FastAPI + LogCost"}


@app.get("/users/{user_id}")
async def read_user(user_id: str):
    logger.info("User profile accessed: %s", user_id)
    return {"user": user_id}


@app.get("/expensive")
async def expensive():
    for i in range(20):
        logger.info("Expensive log line %s", i)
    return {"status": "done"}


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting FastAPI app with LogCost tracking")
    uvicorn.run(app, host="0.0.0.0", port=8000)
