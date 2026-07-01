"""LangGraph による Text-to-Cypher 接客エージェント。

3ステップの線形フロー（フォールバックなし）:
  generate_cypher : スキーマ＋user_id＋質問 → Claude が Cypher を生成（read-onlyガード）
  run_cypher      : Neo4j でクエリ実行しレコード取得
  generate_answer : 質問＋レコード → Claude が日本語で回答

`build_agent()` でグラフをコンパイルして返す。`answer_question()` は単発呼び出し用のヘルパー。
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_neo4j import Neo4jGraph
from langgraph.graph import END, StateGraph

from customer_service.config import CLAUDE_MODEL, get_anthropic_api_key, get_neo4j_settings
from customer_service.agent import prompts

# 書き込み系の句を検出する正規表現（read-only ガード用）
_WRITE_CLAUSE = re.compile(
    r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP|DETACH|CALL\s*\{[^}]*\b(CREATE|MERGE|DELETE|SET)\b)",
    re.IGNORECASE,
)


class AgentState(TypedDict, total=False):
    """エージェントの状態。"""

    user_id: str
    question: str
    cypher: str
    records: list[dict[str, Any]]
    answer: str


def _clean_cypher(text: str) -> str:
    """LLM出力から余計なコードブロック記法などを取り除く。"""

    text = text.strip()
    # ```cypher ... ``` のようなフェンスを除去
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _assert_read_only(cypher: str) -> None:
    """書き込み句が含まれていたら明示的にエラーにする（フォールバックしない）。"""

    if _WRITE_CLAUSE.search(cypher):
        raise ValueError(
            f"生成された Cypher に書き込み句が含まれています（実行を拒否）:\n{cypher}"
        )


def build_agent(llm: ChatAnthropic | None = None, graph: Neo4jGraph | None = None):
    """LangGraph エージェントをコンパイルして返す。

    llm / graph を渡さなければ .env の設定から生成する。
    """

    if llm is None:
        llm = ChatAnthropic(
            model=CLAUDE_MODEL,
            api_key=get_anthropic_api_key(),
            max_tokens=2000,
        )
    if graph is None:
        settings = get_neo4j_settings()
        # スキーマはプロンプト側で自前定義するため、APOC依存の自動取得は無効化する
        graph = Neo4jGraph(
            url=settings.uri,
            username=settings.username,
            password=settings.password,
            refresh_schema=False,
        )

    def generate_cypher(state: AgentState) -> AgentState:
        system = prompts.CYPHER_SYSTEM_PROMPT
        user = prompts.CYPHER_USER_PROMPT.format(
            user_id=state["user_id"], question=state["question"]
        )
        response = llm.invoke([SystemMessage(system), HumanMessage(user)])
        cypher = _clean_cypher(response.content)
        _assert_read_only(cypher)
        return {"cypher": cypher}

    def run_cypher(state: AgentState) -> AgentState:
        records = graph.query(state["cypher"])
        return {"records": records}

    def generate_answer(state: AgentState) -> AgentState:
        import json

        user = prompts.ANSWER_USER_PROMPT.format(
            question=state["question"],
            records=json.dumps(state["records"], ensure_ascii=False, indent=2),
        )
        response = llm.invoke(
            [SystemMessage(prompts.ANSWER_SYSTEM_PROMPT), HumanMessage(user)]
        )
        return {"answer": response.content}

    workflow = StateGraph(AgentState)
    workflow.add_node("generate_cypher", generate_cypher)
    workflow.add_node("run_cypher", run_cypher)
    workflow.add_node("generate_answer", generate_answer)

    workflow.set_entry_point("generate_cypher")
    workflow.add_edge("generate_cypher", "run_cypher")
    workflow.add_edge("run_cypher", "generate_answer")
    workflow.add_edge("generate_answer", END)

    return workflow.compile()


def answer_question(user_id: str, question: str) -> AgentState:
    """単発でエージェントを実行し、最終状態を返す（CLI/テスト用）。"""

    agent = build_agent()
    return agent.invoke({"user_id": user_id, "question": question})


if __name__ == "__main__":
    import sys

    uid = sys.argv[1] if len(sys.argv) > 1 else "U0001"
    q = sys.argv[2] if len(sys.argv) > 2 else "次どんな機種を買えばいい？"
    result = answer_question(uid, q)
    print("=== 生成された Cypher ===")
    print(result["cypher"])
    print("\n=== 取得レコード ===")
    print(result["records"])
    print("\n=== 回答 ===")
    print(result["answer"])
