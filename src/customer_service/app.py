"""Streamlit デモアプリ。

ユーザを選び質問を入力すると、Text-to-Cypher エージェントがグラフDBを参照して
Claude が接客回答を返す。回答に加え、生成された Cypher と取得レコードも表示する。

起動: `uv run streamlit run src/customer_service/app.py`
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from langchain_neo4j import Neo4jGraph

from customer_service.agent.cypher_agent import build_agent
from customer_service.config import get_neo4j_settings

SAMPLE_QUESTIONS = [
    "次どんな機種を買えばいい？",
    "私のバッテリーは大丈夫？",
    "ノイズキャンセリング付きのおすすめは？",
    "私が持っている製品を教えて",
    "最近のアプリの使い方はどう？",
]


@st.cache_resource(show_spinner=False)
def _get_agent():
    """エージェントを一度だけ構築してキャッシュする。"""

    return build_agent()


@st.cache_resource(show_spinner=False)
def _get_graph() -> Neo4jGraph:
    settings = get_neo4j_settings()
    return Neo4jGraph(
        url=settings.uri,
        username=settings.username,
        password=settings.password,
        refresh_schema=False,
    )


@st.cache_data(show_spinner=False)
def _load_users() -> pd.DataFrame:
    """Neo4j からユーザ一覧を取得する。"""

    graph = _get_graph()
    rows = graph.query(
        """
        MATCH (u:User)
        OPTIONAL MATCH (u)-[:OWNS]->(m:Model)
        RETURN u.user_id AS user_id, u.name AS name, u.age AS age,
               u.gender AS gender, u.region AS region, u.segment AS segment,
               collect(m.name) AS owned_models
        ORDER BY u.user_id
        """
    )
    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="接客AIエージェント デモ", page_icon="🎧", layout="wide")
    st.title("🎧 グラフDB × LLM 接客AIエージェント")
    st.caption(
        "ユーザ状態と製品知識を Neo4j グラフDBに表現し、Text-to-Cypher で参照して "
        "Claude が接客回答します（ヘッドホン/イヤホン事業のデモ）。"
    )

    users = _load_users()

    # --- サイドバー: ユーザ選択 ---
    with st.sidebar:
        st.header("ユーザ選択")
        labels = {
            row.user_id: f"{row.user_id} / {row.name}（{row.segment}）"
            for row in users.itertuples()
        }
        user_id = st.selectbox(
            "対象ユーザ",
            options=list(labels.keys()),
            format_func=lambda uid: labels[uid],
        )
        profile = users[users["user_id"] == user_id].iloc[0]
        st.markdown("**プロフィール**")
        st.write(
            {
                "氏名": profile["name"],
                "年齢": int(profile["age"]),
                "性別": profile["gender"],
                "地域": profile["region"],
                "セグメント": profile["segment"],
            }
        )
        owned = [m for m in profile["owned_models"] if m]
        st.markdown("**保有製品**")
        st.write(owned if owned else "（なし）")

    # --- メイン: 質問入力 ---
    st.subheader("質問")
    st.write("サンプル質問:")
    cols = st.columns(len(SAMPLE_QUESTIONS))
    for col, q in zip(cols, SAMPLE_QUESTIONS):
        if col.button(q, use_container_width=True):
            st.session_state["question"] = q

    question = st.text_input(
        "質問を入力してください",
        key="question",
        placeholder="例: 次どんな機種を買えばいい？",
    )

    if st.button("回答を生成", type="primary") and question:
        with st.spinner("グラフDBを参照して回答を生成中..."):
            try:
                result = _get_agent().invoke(
                    {"user_id": user_id, "question": question}
                )
            except Exception as exc:  # デモ用に例外内容を画面に出す
                st.error(f"エラーが発生しました: {exc}")
                return

        st.subheader("回答")
        st.markdown(result["answer"])

        with st.expander("🔎 生成された Cypher クエリ"):
            st.code(result["cypher"], language="cypher")

        with st.expander("📊 グラフDBから取得したデータ"):
            records = result.get("records", [])
            if records:
                st.dataframe(pd.DataFrame(records), use_container_width=True)
            else:
                st.write("該当データはありませんでした。")


if __name__ == "__main__":
    main()
