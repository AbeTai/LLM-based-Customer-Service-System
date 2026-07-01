"""Faker を使ってデータ基盤テーブル（CSV）を生成する。

生成するテーブル:
  - dim_user_profile        : ユーザのデモグラフィック
  - static_description_model: 機種スペック・価格（schema.MODELS をそのまま出力）
  - fact_user_product       : 製品所有状況（購入履歴を兼ねる）
  - fact_app_use            : dailyのアプリ利用状況（FG/BG）
  - fact_battery_condition  : 各機種のバッテリー状況（時系列）
  - fact_support_ticket     : サポート問い合わせ履歴（追加テーブル）
  - fact_app_setting        : アプリ設定（追加テーブル）

乱数シードを固定して再現性を持たせる。`uv run python -m customer_service.data_generation.generate` で実行。
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

import pandas as pd
from faker import Faker

from customer_service.config import DATA_DIR
from customer_service.data_generation import schema

SEED = 42
N_USERS = 50
APP_USAGE_DAYS = 30  # アプリ利用ログを作る日数（直近）
N_ACTIVE_USERS = 25  # アプリ利用ログを持つユーザ数
N_TICKETS = 30

fake = Faker("ja_JP")


def _reset_seed() -> None:
    Faker.seed(SEED)
    random.seed(SEED)


def generate_users() -> pd.DataFrame:
    """dim_user_profile: ユーザのデモグラフィック情報。"""

    rows = []
    for i in range(1, N_USERS + 1):
        signup = fake.date_between(start_date="-3y", end_date="-1m")
        rows.append(
            {
                "user_id": f"U{i:04d}",
                "name": fake.name(),
                "age": random.randint(18, 65),
                "gender": random.choice(["男性", "女性", "その他"]),
                "region": fake.prefecture(),
                "segment": random.choice(schema.SEGMENTS),
                "signup_date": signup.isoformat(),
            }
        )
    return pd.DataFrame(rows)


def generate_models() -> pd.DataFrame:
    """static_description_model: 機種マスタ。schema.MODELS をそのまま出力。"""

    return pd.DataFrame(schema.MODELS)


def generate_user_products(users: pd.DataFrame) -> pd.DataFrame:
    """fact_user_product: 誰がどの機種をいつ購入・所有しているか。"""

    model_ids = [m["model_id"] for m in schema.MODELS]
    rows = []
    for _, user in users.iterrows():
        n_owned = random.choices([1, 2, 3], weights=[5, 3, 2])[0]
        owned = random.sample(model_ids, k=n_owned)
        signup = date.fromisoformat(user["signup_date"])
        for model_id in owned:
            # 購入日はサインアップ日以降〜今日まで
            days_range = max((date.today() - signup).days, 1)
            purchased = signup + timedelta(days=random.randint(0, days_range))
            warranty = purchased + timedelta(days=365)
            rows.append(
                {
                    "user_id": user["user_id"],
                    "model_id": model_id,
                    "purchased_at": purchased.isoformat(),
                    "channel": random.choice(schema.CHANNELS),
                    "warranty_until": warranty.isoformat(),
                }
            )
    return pd.DataFrame(rows)


def generate_app_use(user_products: pd.DataFrame) -> pd.DataFrame:
    """fact_app_use: dailyのアプリ利用（FG/BG分数）。一部のアクティブユーザ×直近N日。"""

    active_users = random.sample(
        sorted(user_products["user_id"].unique().tolist()),
        k=min(N_ACTIVE_USERS, user_products["user_id"].nunique()),
    )
    today = date.today()
    rows = []
    for user_id in active_users:
        owned = user_products[user_products["user_id"] == user_id]["model_id"].tolist()
        for day_offset in range(APP_USAGE_DAYS):
            day = today - timedelta(days=day_offset)
            # その日にアプリを使わない日もある
            if random.random() < 0.3:
                continue
            model_id = random.choice(owned)
            fg = random.randint(5, 180)  # フォアグラウンド利用（分）
            bg = random.randint(0, 300)  # バックグラウンド利用（分）
            rows.append(
                {
                    "date": day.isoformat(),
                    "user_id": user_id,
                    "model_id": model_id,
                    "fg_minutes": fg,
                    "bg_minutes": bg,
                }
            )
    return pd.DataFrame(rows)


def generate_battery_condition(user_products: pd.DataFrame) -> pd.DataFrame:
    """fact_battery_condition: 所有機種ごとのバッテリー状況（時系列で数点）。"""

    today = date.today()
    rows = []
    for _, row in user_products.iterrows():
        purchased = date.fromisoformat(row["purchased_at"])
        months_owned = max((today - purchased).days // 30, 1)
        # 経過月数が長いほど劣化が進む（health低下・cycle増加）
        n_readings = min(months_owned, 6)
        for k in range(n_readings):
            reading_day = today - timedelta(days=30 * (n_readings - 1 - k))
            elapsed_months = (reading_day - purchased).days / 30
            # 1か月あたり約1%劣化 + ばらつき、下限70%
            health = max(100 - elapsed_months * random.uniform(0.8, 1.5), 70)
            cycles = int(elapsed_months * random.uniform(8, 20))
            rows.append(
                {
                    "date": reading_day.isoformat(),
                    "user_id": row["user_id"],
                    "model_id": row["model_id"],
                    "battery_health_pct": round(health, 1),
                    "charge_cycles": cycles,
                }
            )
    return pd.DataFrame(rows)


def generate_support_tickets(user_products: pd.DataFrame) -> pd.DataFrame:
    """fact_support_ticket: サポート問い合わせ履歴（追加テーブル）。"""

    categories = list(schema.SUPPORT_CATEGORIES.keys())
    statuses = ["対応中", "解決済み", "保留"]
    rows = []
    pairs = user_products[["user_id", "model_id"]].to_dict("records")
    for i in range(1, N_TICKETS + 1):
        pair = random.choice(pairs)
        category = random.choice(categories)
        summary = random.choice(schema.SUPPORT_CATEGORIES[category])
        created = fake.date_time_between(start_date="-1y", end_date="now")
        rows.append(
            {
                "ticket_id": f"T{i:04d}",
                "user_id": pair["user_id"],
                "model_id": pair["model_id"],
                "created_at": created.replace(microsecond=0).isoformat(),
                "status": random.choice(statuses),
                "category": category,
                "summary": summary,
            }
        )
    return pd.DataFrame(rows)


def generate_app_settings(user_products: pd.DataFrame) -> pd.DataFrame:
    """fact_app_setting: 所有機種ごとのアプリ設定（追加テーブル）。"""

    model_nc = {m["model_id"]: m["noise_cancelling"] for m in schema.MODELS}
    rows = []
    for _, row in user_products.iterrows():
        # ノイキャン非対応機種は常にオフ
        nc_capable = model_nc[row["model_id"]]
        nc_on = random.random() < 0.7 if nc_capable else False
        updated = fake.date_time_between(start_date="-6m", end_date="now")
        rows.append(
            {
                "user_id": row["user_id"],
                "model_id": row["model_id"],
                "noise_cancelling_on": nc_on,
                "eq_preset": random.choice(schema.EQ_PRESETS),
                "updated_at": updated.replace(microsecond=0).isoformat(),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    """全テーブルを生成して data/ に CSV 出力する。"""

    _reset_seed()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    users = generate_users()
    models = generate_models()
    user_products = generate_user_products(users)
    app_use = generate_app_use(user_products)
    battery = generate_battery_condition(user_products)
    tickets = generate_support_tickets(user_products)
    settings = generate_app_settings(user_products)

    tables = {
        "dim_user_profile": users,
        "static_description_model": models,
        "fact_user_product": user_products,
        "fact_app_use": app_use,
        "fact_battery_condition": battery,
        "fact_support_ticket": tickets,
        "fact_app_setting": settings,
    }

    for name, df in tables.items():
        path = DATA_DIR / f"{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8")
        print(f"  {name:28s} {len(df):5d} 行 -> {path}")

    print("データ生成が完了しました。")


if __name__ == "__main__":
    main()
