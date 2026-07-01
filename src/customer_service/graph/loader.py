"""生成済み CSV を読み込み、Neo4j にグラフとして投入する。

グラフスキーマ:
  ノード:
    (:User   {user_id, name, age, gender, region, segment, signup_date})
    (:Model  {model_id, name, category, price, release_date, driver_type,
              noise_cancelling, battery_life_hours, weight_g, water_resistance, color})
    (:BatteryReading {reading_id, date, battery_health_pct, charge_cycles})
    (:SupportTicket  {ticket_id, created_at, status, category, summary})
  リレーション:
    (User)-[:OWNS {purchased_at, channel, warranty_until}]->(Model)
    (User)-[:APP_USAGE {date, fg_minutes, bg_minutes}]->(Model)
    (User)-[:HAS_SETTING {noise_cancelling_on, eq_preset, updated_at}]->(Model)
    (User)-[:HAS_READING]->(BatteryReading)-[:FOR_MODEL]->(Model)
    (User)-[:RAISED]->(SupportTicket)-[:ABOUT]->(Model)

`uv run python -m customer_service.graph.loader` で実行。実行のたびにグラフを作り直す。
"""

from __future__ import annotations

import json

import pandas as pd
from neo4j import Driver, GraphDatabase

from customer_service.config import DATA_DIR, get_neo4j_settings


def _records(name: str) -> list[dict]:
    """CSV を読み込み、Neo4j に渡せる素の Python 型の辞書リストにする。

    to_json 経由にすることで numpy 型や NaN を JSON 互換（int/float/bool/null）に正規化する。
    """

    df = pd.read_csv(DATA_DIR / f"{name}.csv")
    return json.loads(df.to_json(orient="records"))


def _create_constraints(driver: Driver) -> None:
    """一意制約（＋暗黙のインデックス）を作成する。"""

    statements = [
        "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
        "CREATE CONSTRAINT model_id IF NOT EXISTS FOR (m:Model) REQUIRE m.model_id IS UNIQUE",
        "CREATE CONSTRAINT ticket_id IF NOT EXISTS FOR (t:SupportTicket) REQUIRE t.ticket_id IS UNIQUE",
    ]
    with driver.session() as session:
        for stmt in statements:
            session.run(stmt)


def _clear(driver: Driver) -> None:
    """既存のノード・リレーションを全削除する（デモ用に毎回作り直す）。"""

    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


def _load_users(driver: Driver) -> None:
    rows = _records("dim_user_profile")
    query = """
    UNWIND $rows AS row
    MERGE (u:User {user_id: row.user_id})
    SET u.name = row.name, u.age = row.age, u.gender = row.gender,
        u.region = row.region, u.segment = row.segment, u.signup_date = row.signup_date
    """
    with driver.session() as session:
        session.run(query, rows=rows)


def _load_models(driver: Driver) -> None:
    rows = _records("static_description_model")
    query = """
    UNWIND $rows AS row
    MERGE (m:Model {model_id: row.model_id})
    SET m.name = row.name, m.category = row.category, m.price = row.price,
        m.release_date = row.release_date, m.driver_type = row.driver_type,
        m.noise_cancelling = row.noise_cancelling,
        m.battery_life_hours = row.battery_life_hours, m.weight_g = row.weight_g,
        m.water_resistance = row.water_resistance, m.color = row.color
    """
    with driver.session() as session:
        session.run(query, rows=rows)


def _load_ownership(driver: Driver) -> None:
    rows = _records("fact_user_product")
    query = """
    UNWIND $rows AS row
    MATCH (u:User {user_id: row.user_id})
    MATCH (m:Model {model_id: row.model_id})
    MERGE (u)-[r:OWNS]->(m)
    SET r.purchased_at = row.purchased_at, r.channel = row.channel,
        r.warranty_until = row.warranty_until
    """
    with driver.session() as session:
        session.run(query, rows=rows)


def _load_app_use(driver: Driver) -> None:
    rows = _records("fact_app_use")
    query = """
    UNWIND $rows AS row
    MATCH (u:User {user_id: row.user_id})
    MATCH (m:Model {model_id: row.model_id})
    CREATE (u)-[:APP_USAGE {date: row.date, fg_minutes: row.fg_minutes,
                            bg_minutes: row.bg_minutes}]->(m)
    """
    with driver.session() as session:
        session.run(query, rows=rows)


def _load_battery(driver: Driver) -> None:
    rows = _records("fact_battery_condition")
    query = """
    UNWIND $rows AS row
    MATCH (u:User {user_id: row.user_id})
    MATCH (m:Model {model_id: row.model_id})
    CREATE (b:BatteryReading {date: row.date,
                             battery_health_pct: row.battery_health_pct,
                             charge_cycles: row.charge_cycles})
    CREATE (u)-[:HAS_READING]->(b)
    CREATE (b)-[:FOR_MODEL]->(m)
    """
    with driver.session() as session:
        session.run(query, rows=rows)


def _load_settings(driver: Driver) -> None:
    rows = _records("fact_app_setting")
    query = """
    UNWIND $rows AS row
    MATCH (u:User {user_id: row.user_id})
    MATCH (m:Model {model_id: row.model_id})
    MERGE (u)-[r:HAS_SETTING]->(m)
    SET r.noise_cancelling_on = row.noise_cancelling_on,
        r.eq_preset = row.eq_preset, r.updated_at = row.updated_at
    """
    with driver.session() as session:
        session.run(query, rows=rows)


def _load_tickets(driver: Driver) -> None:
    rows = _records("fact_support_ticket")
    query = """
    UNWIND $rows AS row
    MATCH (u:User {user_id: row.user_id})
    MATCH (m:Model {model_id: row.model_id})
    MERGE (t:SupportTicket {ticket_id: row.ticket_id})
    SET t.created_at = row.created_at, t.status = row.status,
        t.category = row.category, t.summary = row.summary
    MERGE (u)-[:RAISED]->(t)
    MERGE (t)-[:ABOUT]->(m)
    """
    with driver.session() as session:
        session.run(query, rows=rows)


def main() -> None:
    """CSV から Neo4j にグラフを構築する。"""

    settings = get_neo4j_settings()
    driver = GraphDatabase.driver(
        settings.uri, auth=(settings.username, settings.password)
    )
    try:
        driver.verify_connectivity()
        print(f"Neo4j に接続しました: {settings.uri}")

        _create_constraints(driver)
        _clear(driver)

        print("ノード・リレーションを投入中...")
        _load_users(driver)
        _load_models(driver)
        _load_ownership(driver)
        _load_app_use(driver)
        _load_battery(driver)
        _load_settings(driver)
        _load_tickets(driver)

        # 件数サマリを表示
        with driver.session() as session:
            counts = session.run(
                "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c ORDER BY label"
            ).data()
            rels = session.run(
                "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS c ORDER BY type"
            ).data()
        print("ノード:")
        for row in counts:
            print(f"  {row['label']:16s} {row['c']:5d}")
        print("リレーション:")
        for row in rels:
            print(f"  {row['type']:16s} {row['c']:5d}")
        print("グラフ構築が完了しました。")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
