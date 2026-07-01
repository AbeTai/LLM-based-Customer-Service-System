"""環境変数の読込とアプリ全体の設定。

`.env` から Neo4j 接続情報と LLM の APIキーを読み込む。
フォールバックは実装しない方針のため、必須の設定が欠けている場合は明示的にエラーにする。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# プロジェクトルート（このファイルから見て 3 つ上）と data ディレクトリ
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

# 回答生成に使う Claude モデル（Claude Sonnet 4.6）
CLAUDE_MODEL = "claude-sonnet-4-6"

# .env を読み込む（既に環境変数がある場合はそちらを優先）
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Neo4jSettings:
    """Neo4j への接続設定。"""

    uri: str
    username: str
    password: str


def get_neo4j_settings() -> Neo4jSettings:
    """`.env` から Neo4j 接続設定を組み立てて返す。"""

    return Neo4jSettings(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        username=os.environ.get("NEO4J_USERNAME", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "password"),
    )


def get_anthropic_api_key() -> str:
    """Anthropic の APIキーを返す。未設定なら明示的にエラー。"""

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY が設定されていません。.env に設定してください。"
        )
    return key
