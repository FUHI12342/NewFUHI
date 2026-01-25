# graph.py - LangGraph Workflow

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
import time
from tools import create_remote_session, send_user_invite, check_session_status

class AgentState(TypedDict):
    user_query: str
    target_device: str  # "父のスマホ" → device_id抽出
    session_id: str
    session_url: str
    status: str
    instructions: str
    messages: Annotated[list, operator.add]

def parse_intent(state: AgentState) -> dict:
    """ユーザ意図解析"""
    query = state["user_query"]
    # LLMで抽出（OpenAI/Groq）
    device = "device_001"  # 例: 父のスマホ→固定IDマッピング
    instructions = "このURLを開いて『画面共有許可』をタップしてください"
    return {"target_device": device, "instructions": instructions}

def create_session(state: AgentState) -> dict:
    """セッション生成"""
    result = create_remote_session()
    return {"session_id": result["session_id"], "session_url": result["url"]}

def send_invitation(state: AgentState) -> dict:
    """招待送信"""
    phone = "090-XXXX-XXXX"  # device_idから電話番号取得
    result = send_user_invite(phone, state["session_url"], state["instructions"])
    return {"messages": [f"招待送信完了: {result}"]}

def monitor_connection(state: AgentState) -> dict:
    """接続監視（3回ポーリング）"""
    for _ in range(3):
        status = check_session_status(state["session_id"])
        if status["status"] == "connected":
            return {"status": "connected", "messages": ["接続確立！操作開始"]}
        time.sleep(10)
    return {"status": "timeout", "messages": ["接続待ちタイムアウト"]}

# Graph構築
workflow = StateGraph(AgentState)
workflow.add_node("parse", parse_intent)
workflow.add_node("create", create_session)
workflow.add_node("invite", send_invitation)
workflow.add_node("monitor", monitor_connection)

workflow.set_entry_point("parse")
workflow.add_edge("parse", "create")
workflow.add_edge("create", "invite")
workflow.add_edge("invite", "monitor")
workflow.add_conditional_edges(
    "monitor",
    lambda s: END if s["status"] in ["connected", "timeout"] else "monitor"
)

app = workflow.compile()