import os
import sys
from fastapi import FastAPI
from roo_orchestrator.api import router as api_router

app = FastAPI()

app.include_router(api_router)
