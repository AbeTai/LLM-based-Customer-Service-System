"""プロンプトに渡すグラフスキーマの説明文。

Text-to-Cypher で LLM に「どんなノード・リレーション・プロパティがあるか」を
正確に伝えるための固定テキスト。loader.py のスキーマと一致させること。
"""

GRAPH_SCHEMA = """\
# ノード
(:User {user_id: STRING, name: STRING, age: INTEGER, gender: STRING,
        region: STRING, segment: STRING, signup_date: STRING(YYYY-MM-DD)})
(:Model {model_id: STRING, name: STRING, category: STRING('earphone'|'headphone'),
         price: INTEGER(円), release_date: STRING, driver_type: STRING,
         noise_cancelling: BOOLEAN, battery_life_hours: INTEGER,
         weight_g: INTEGER, water_resistance: STRING, color: STRING})
(:BatteryReading {date: STRING(YYYY-MM-DD), battery_health_pct: FLOAT(0-100),
                  charge_cycles: INTEGER})
(:SupportTicket {ticket_id: STRING, created_at: STRING, status: STRING,
                 category: STRING, summary: STRING})

# リレーション
(:User)-[:OWNS {purchased_at: STRING, channel: STRING, warranty_until: STRING}]->(:Model)
(:User)-[:APP_USAGE {date: STRING, fg_minutes: INTEGER, bg_minutes: INTEGER}]->(:Model)
(:User)-[:HAS_SETTING {noise_cancelling_on: BOOLEAN, eq_preset: STRING, updated_at: STRING}]->(:Model)
(:User)-[:HAS_READING]->(:BatteryReading)-[:FOR_MODEL]->(:Model)
(:User)-[:RAISED]->(:SupportTicket)-[:ABOUT]->(:Model)

# 補足
- APP_USAGE は日次の行が複数ある（同じ User→Model 間に複数リレーション）。fg_minutes はフォアグラウンド、bg_minutes はバックグラウンド利用（分）。
- BatteryReading は時系列。最新の状態を見るには date が最大のものを使う。
- price は円、battery_life_hours はカタログ上の連続再生時間。
- category は 'earphone'（イヤホン）か 'headphone'（ヘッドホン）。
"""
