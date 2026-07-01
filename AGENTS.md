# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

（`CLAUDE.md` は本ファイル `AGENTS.md` へのシンボリックリンクです。）

## プロジェクト概要

ユーザの状態（保有製品・アプリ利用・バッテリー状況など）と製品知識を **Neo4j グラフDB** に表現し、
**Text-to-Cypher** で参照して **Claude Sonnet 4.6** が接客回答を行うデモ。想定事業はヘッドホン/イヤホン事業。

## 主要コマンド

```bash
uv sync                                                   # 依存インストール
cp .env.example .env                                      # 環境変数を用意（ANTHROPIC_API_KEY, NEO4J_PASSWORD）

# Neo4j（Homebrew, ローカル）
brew services start neo4j                                 # 起動（初回: neo4j-admin dbms set-initial-password password）

uv run python -m customer_service.data_generation.generate  # 1) CSV生成 → data/
uv run python -m customer_service.graph.loader              # 2) CSV → Neo4j へロード（毎回作り直す）
uv run python -m customer_service.agent.cypher_agent U0001 "質問"  # エージェント単体実行（デバッグ用）
uv run streamlit run src/customer_service/app.py            # 3) デモUI起動
```

処理は必ず「生成 → ロード → UI」の順。ローダーは実行のたびに `MATCH (n) DETACH DELETE n` で全消去してから入れ直す。

## アーキテクチャ

データフロー: `Faker生成CSV(data/)` → `loader.py で Neo4j 構築` → `Streamlit UI` → `LangGraphエージェント` → `回答`

- **`config.py`** — `.env` 読込・Neo4j接続設定・モデルID（`CLAUDE_MODEL = "claude-sonnet-4-6"`）を一元管理。`PROJECT_ROOT` / `DATA_DIR` もここ。
- **`data_generation/`** — `schema.py` に機種マスタ（12機種）と各種候補値を**固定データ**で定義し、`generate.py` が Faker(ja_JP)＋固定シード(42) で7テーブルの CSV を生成。
- **`graph/loader.py`** — CSV を `neo4j` 公式ドライバの `UNWIND` バッチで投入。numpy型/NaN対策で `df.to_json()` 経由で素の型に正規化してから渡す。
- **`agent/`** — LangGraph の3ノード線形フロー（`generate_cypher` → `run_cypher` → `generate_answer`）。**フォールバックやリトライは持たない**。
- **`app.py`** — Streamlit UI。回答に加え生成Cypherと取得レコードも表示する。

## 重要な設計上の約束（変更時に守ること）

- **フォールバックは実装しない**。Cypher生成失敗時の自動修正・RDB/ベクトルへの切替・LLM切替は入れない。エラーは握りつぶさず表面化させる。
- **read-only ガード**: `cypher_agent._assert_read_only` が書き込み句（CREATE/MERGE/DELETE/SET等）を検出したら実行拒否。グラフスキーマを変えても参照専用は維持する。
- **スキーマの二重管理に注意**: グラフ構造を変えたら **`graph/loader.py`（投入クエリ）と `agent/graph_schema.py`（プロンプト用スキーマ文）の両方**を必ず一致させる。プロンプトのスキーマが実体とズレると Cypher が壊れる。
- **`Neo4jGraph` は `refresh_schema=False` で生成**する。自動スキーマ取得は APOC プラグイン依存で、未導入だと初期化時に失敗する。スキーマは `graph_schema.py` で自前定義しているため不要。
- **プロンプトとスキーマ文字列に `{...}` を含む**ため、`prompts.CYPHER_SYSTEM_PROMPT` は `str.format()` しない（スキーマ中の波括弧が書式指定子として誤解釈される）。user_id は user プロンプト側でのみ渡す。
- **APIキーは `.env`**（gitignore済み）。`data/*.csv` もコミットしない（`generate.py` で再生成可能）。
