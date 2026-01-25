# main.py - FastAPIエンドポイント

from fastapi import FastAPI
from graph import app as workflow_app
from pydantic import BaseModel

class QueryRequest(BaseModel):
    query: str

fastapi_app = FastAPI()

@fastapi_app.post("/remote-control")
async def remote_control(request: QueryRequest):
    """自然言語で呼び出し"""
    result = workflow_app.invoke({"user_query": request.query})
    return {
        "status": result["status"],
        "session_url": result.get("session_url"),
        "message": result["messages"][-1] if result["messages"] else ""
    }

# 実行: uvicorn main:fastapi_app --reload