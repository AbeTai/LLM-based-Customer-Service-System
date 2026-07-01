# LLMベース接客AIエージェント（グラフDB × LLM）

ユーザの状態（保有製品・アプリ利用・バッテリー状況など）と製品知識を **Neo4j グラフDB** に表現し、
それを参照して **LLM（Claude Sonnet 4.6）** が接客回答を行うデモアプリです。想定事業はヘッドホン/イヤホン事業。

- **グラフDB**: Neo4j（ローカル）
- **参照方式**: Text-to-Cypher（LLMがスキーマを見て動的にCypherを生成）
- **オーケストレーション**: LangGraph（Cypher生成 → 実行 → 回答 の3ステップ）
- **UI**: Streamlit

## セットアップ

### 1. Neo4j をローカルに用意（Homebrew）

```bash
brew install neo4j
# 初回のみ初期パスワードを設定（例: password）
neo4j-admin dbms set-initial-password password
neo4j start
```

ブラウザ `http://localhost:7474` で疎通確認できます（初期ユーザは `neo4j`）。

### 2. 依存パッケージのインストール（uv）

```bash
uv sync
```

### 3. `.env` を用意

```bash
cp .env.example .env
# ANTHROPIC_API_KEY と NEO4J_PASSWORD を設定
```

## 使い方

```bash
# 1) データ基盤テーブル（CSV）を生成
uv run python -m customer_service.data_generation.generate

# 2) CSV から Neo4j にグラフを構築
uv run python -m customer_service.graph.loader

# 3) デモアプリを起動
uv run streamlit run src/customer_service/app.py
```

ブラウザでユーザIDを選び、「次どんな機種を買えばいい？」などの質問を投げると、
エージェントがそのユーザに絞ってグラフDBを参照し、Claude が日本語で回答します。

## ディレクトリ構成

```
src/customer_service/
├─ config.py                # .env読込・Neo4j接続・モデルID
├─ data_generation/         # テーブル定義とFakerによるCSV生成
├─ graph/loader.py          # CSV → Neo4j ロード
├─ agent/                   # LangGraph Text-to-Cypher エージェント
└─ app.py                   # Streamlit UI
```
