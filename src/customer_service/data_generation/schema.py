"""テーブルの列定義と、機種マスタ（現実的なスペック・価格）の固定データ。

機種マスタ（static_description_model）だけは Faker で乱数生成せず、
現実的で一貫性のある値を人手で定義する。ユーザや利用ログはこれを参照して生成する。
"""

from __future__ import annotations

# --- 機種マスタ（static_description_model 相当） ---
# category: earphone（イヤホン） / headphone（ヘッドホン）
# price: 円, battery_life_hours: 連続再生時間, weight_g: 重量
MODELS: list[dict] = [
    # イヤホン（完全ワイヤレス）
    {
        "model_id": "EP-A100",
        "name": "AeroBuds A100",
        "category": "earphone",
        "price": 9800,
        "release_date": "2022-06-15",
        "driver_type": "ダイナミック",
        "noise_cancelling": False,
        "battery_life_hours": 6,
        "weight_g": 5,
        "water_resistance": "IPX4",
        "color": "ブラック",
    },
    {
        "model_id": "EP-A200",
        "name": "AeroBuds A200 NC",
        "category": "earphone",
        "price": 16800,
        "release_date": "2023-03-20",
        "driver_type": "ダイナミック",
        "noise_cancelling": True,
        "battery_life_hours": 8,
        "weight_g": 5,
        "water_resistance": "IPX4",
        "color": "ホワイト",
    },
    {
        "model_id": "EP-A300",
        "name": "AeroBuds A300 Pro",
        "category": "earphone",
        "price": 24800,
        "release_date": "2024-05-10",
        "driver_type": "ハイブリッド",
        "noise_cancelling": True,
        "battery_life_hours": 9,
        "weight_g": 6,
        "water_resistance": "IPX5",
        "color": "ミッドナイトブルー",
    },
    {
        "model_id": "EP-S100",
        "name": "SportBuds S100",
        "category": "earphone",
        "price": 12800,
        "release_date": "2023-07-01",
        "driver_type": "ダイナミック",
        "noise_cancelling": False,
        "battery_life_hours": 10,
        "weight_g": 7,
        "water_resistance": "IPX7",
        "color": "レッド",
    },
    {
        "model_id": "EP-S200",
        "name": "SportBuds S200",
        "category": "earphone",
        "price": 18800,
        "release_date": "2024-09-05",
        "driver_type": "ダイナミック",
        "noise_cancelling": True,
        "battery_life_hours": 11,
        "weight_g": 7,
        "water_resistance": "IPX7",
        "color": "ライム",
    },
    {
        "model_id": "EP-C100",
        "name": "ClearTalk C100",
        "category": "earphone",
        "price": 14800,
        "release_date": "2023-11-15",
        "driver_type": "ダイナミック",
        "noise_cancelling": True,
        "battery_life_hours": 7,
        "weight_g": 5,
        "water_resistance": "IPX4",
        "color": "ベージュ",
    },
    # ヘッドホン（オーバーイヤー）
    {
        "model_id": "HP-H100",
        "name": "StudioOne H100",
        "category": "headphone",
        "price": 19800,
        "release_date": "2022-10-01",
        "driver_type": "ダイナミック",
        "noise_cancelling": False,
        "battery_life_hours": 30,
        "weight_g": 250,
        "water_resistance": "なし",
        "color": "ブラック",
    },
    {
        "model_id": "HP-H200",
        "name": "StudioOne H200 NC",
        "category": "headphone",
        "price": 32800,
        "release_date": "2023-04-12",
        "driver_type": "ダイナミック",
        "noise_cancelling": True,
        "battery_life_hours": 35,
        "weight_g": 260,
        "water_resistance": "なし",
        "color": "シルバー",
    },
    {
        "model_id": "HP-H300",
        "name": "StudioOne H300 Pro",
        "category": "headphone",
        "price": 49800,
        "release_date": "2024-06-28",
        "driver_type": "平面磁界",
        "noise_cancelling": True,
        "battery_life_hours": 40,
        "weight_g": 300,
        "water_resistance": "なし",
        "color": "グラファイト",
    },
    {
        "model_id": "HP-L100",
        "name": "LiteWear L100",
        "category": "headphone",
        "price": 14800,
        "release_date": "2023-02-08",
        "driver_type": "ダイナミック",
        "noise_cancelling": False,
        "battery_life_hours": 25,
        "weight_g": 180,
        "water_resistance": "なし",
        "color": "ネイビー",
    },
    {
        "model_id": "HP-L200",
        "name": "LiteWear L200 NC",
        "category": "headphone",
        "price": 22800,
        "release_date": "2024-01-30",
        "driver_type": "ダイナミック",
        "noise_cancelling": True,
        "battery_life_hours": 28,
        "weight_g": 190,
        "water_resistance": "なし",
        "color": "ローズ",
    },
    {
        "model_id": "HP-G100",
        "name": "GamerEdge G100",
        "category": "headphone",
        "price": 27800,
        "release_date": "2024-03-15",
        "driver_type": "ダイナミック",
        "noise_cancelling": False,
        "battery_life_hours": 20,
        "weight_g": 320,
        "water_resistance": "なし",
        "color": "ブラック/レッド",
    },
]

# アプリの機能設定で使う EQ プリセットの候補
EQ_PRESETS = ["フラット", "低音強調", "ボーカル強調", "ライブ", "ゲーム"]

# サポート問い合わせのカテゴリと典型的な要約
SUPPORT_CATEGORIES: dict[str, list[str]] = {
    "接続不良": [
        "Bluetooth接続が頻繁に切れる",
        "片方のイヤホンから音が出ない",
        "アプリとペアリングできない",
    ],
    "バッテリー": [
        "以前より充電の持ちが悪くなった",
        "ケースで充電できない",
        "急に電源が落ちる",
    ],
    "音質": [
        "低音が弱く感じる",
        "ノイズキャンセリングの効きが弱い",
        "特定の音域でノイズが入る",
    ],
    "使い方": [
        "タッチ操作の割り当てを変更したい",
        "ファームウェアの更新方法を知りたい",
        "イコライザの設定方法を知りたい",
    ],
}

# 販売チャネル
CHANNELS = ["公式オンラインストア", "家電量販店", "Amazon", "楽天市場"]

# ユーザセグメント
SEGMENTS = ["新規", "リピーター", "ロイヤル", "休眠"]
