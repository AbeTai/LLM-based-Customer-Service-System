# グラフDB×LLMエージェントによる高速・高精度カスタマーサポートの実現可能性調査

## TL;DR
- **グラフDB＋LLMエージェントは、顧客状態（保有製品・デバイス使用状況・視聴履歴）のように「関係性が複雑に絡む」接客に対して、ベクトルRAGやRDB単独より高精度・高速になる実証が複数ある**。LinkedInは過去issueのナレッジグラフ＋RAGで顧客対応の解決時間中央値を7時間→5時間（28.6%短縮）、検索精度MRRを0.522→0.927（+77.6%）に改善（SIGIR 2024, arXiv:2404.17723）。data.worldはナレッジグラフ経由でLLMの業務質問正答率を3倍（16.7%→54.2%）に高めた（arXiv:2311.07509）。
- **推奨アプローチは「ルーティング型ハイブリッド構成」**：顧客状態の構造データはグラフDB（Neo4j/Neptune）、FAQ・マニュアル等の非構造テキストはベクトル検索に置き、両者をLLMエージェント（LangGraph）が状況に応じて使い分ける。Text-to-Cypherで自然言語→グラフクエリ変換を行い、IoT/バッテリー状態のリアルタイムデータはKafka経由でグラフに取り込む。
- **ただし「とりあえずGraphRAG」は禁物**。グラフ構築時のLLMコスト、エンティティ解決の難しさ、グラフ鮮度の維持、運用負荷が主なリスク。単純なFAQ検索にはオーバースペックで、関係性をたどる多段推論が必要な領域でのみ投資対効果が出る。PoC→限定本番→全面展開という段階的導入を強く推奨する。

## Key Findings

1. **実運用で定量効果が出た事例が存在する。** LinkedInのカスタマーサポートでは過去issueトラッキングチケットからナレッジグラフを構築し、RAGと統合。ベースライン比でMRRを0.522→0.927（+77.6%）、BLEUを+0.32改善し、約6か月の本番運用で1件あたり解決時間の中央値を7時間→5時間（28.6%短縮）にした（Xu et al., SIGIR 2024, arXiv:2404.17723）。Microchip TechnologyはMemgraph＋プライベートLLMで「Workspace Assistant」を構築し、受注遅延理由などを注文・サプライヤ・工程ログをたどって回答できるようにした。

2. **ナレッジグラフはLLMの精度を構造的に底上げする。** data.worldのベンチマーク（Sequeda/Allemang/Jacob、保険ドメインSQL、GPT-4ゼロショット、arXiv:2311.07509）では、SQLデータベースに直接質問した場合の正答率（AOEA）16.7%が、同じデータのナレッジグラフ（SPARQL）表現を介すと54.2%（約3倍）に向上。特にスキーマ集約的な質問（KPI・指標系）ではSQL単独が0%だった領域でグラフが35.7%/38.7%を達成した。

3. **グラフDBは「多段の関係探索」でRDBに対し桁違いの速度優位を持つ。** 『Neo4j in Action』（Manning, 2014）の100万ユーザーのソーシャルグラフ「友達の友達」検索ベンチ（査読論文 arXiv:1706.06654 に再掲）では、深さ2でNeo4j 0.010秒 vs MySQL 0.016秒（約60%高速）、深さ3で0.168秒 vs 30.267秒（約180倍）、深さ4で1.359秒 vs 1,543.505秒（約1,135倍）、深さ5でMySQLは完了せず。これは「インデックスフリー隣接性（index-free adjacency）」により、グラフ走査のコストがデータ総量ではなく実際にたどる関係数に依存するため。ただしこの優位は多段JOIN・パターンマッチに特有で、集約・GROUP BY系ではRDBが勝つこともある（ワークロード依存）。

4. **顧客状態管理は典型的なグラフ向きユースケース（Customer 360）。** 顧客・アカウント・デバイス・製品・コンテンツ・サポート履歴をノード、購入・視聴・問い合わせ・所有を関係として表現すると、サイロ化したデータを横断する「次のベストアクション」やchurn予測が容易になる。Neo4j、TigerGraph、Amazon Neptune、ArangoDB、NebulaGraph、Memgraph、FalkorDBが主要な選択肢。

5. **エージェントの「記憶」をグラフで持つ新潮流。** Zep/Graphiti は時間認識型（bi-temporal）ナレッジグラフでエージェント記憶を実装し、DMRベンチマークでMemGPT（93.4%）を上回る94.8%（GPT-4o-mini時98.2%）、LongMemEvalで最大18.5%精度向上・応答あたり115kトークン→1.6kトークンでレイテンシ90%削減を報告（Rasmussen et al., arXiv:2501.13956）。顧客の状態変化（契約更新、バッテリー劣化進行）を時系列で正確に扱える点が接客向き。

6. **主要クラウド／ベンダーがGraphRAGを製品化済み。** AWSはAmazon Bedrock Knowledge Bases GraphRAG（Amazon Neptune Analytics）を2025年3月7日にGA。Microsoftは2024年にGraphRAGをOSS公開し、2024年11月にインデックスコストをフルGraphRAGの0.1%（ベクトルRAG同等）に抑え、グローバルクエリのコストを700分の1以下にするLazyGraphRAGを発表。Neo4jはLangChain/LangGraph統合、Text2Cypherデータセット・モデルを公開している。

## Details

### 1. 過去事例・ケーススタディ

**カスタマーサポート／QAでの直接事例**
- **LinkedIn（SIGIR 2024, arXiv:2404.17723）**：過去のissueトラッキングチケットを単なるテキストではなく、issue内部構造（intra-issue）とissue間関係（inter-issue）を保持したKGとして構築。ユーザー質問をパースしサブグラフを検索して回答。MRR 0.522→0.927（+77.6%）、BLEU +0.32、本番で解決時間中央値7時間→5時間（-28.6%）。「テキスト分割で失われる構造情報を保持する」ことの効果を示す最重要事例。
- **Microchip Technology（Memgraph）**：顧客サポート担当が受注状況や生産関連の問い合わせに自力で答えられず、エンジニアリング部門に依存していた課題を、リアルタイム運用グラフから構造化インサイトを取得するGraphRAGチャットボットで解決。ロールベースアクセス制御、複数事業部対応のスケーラブル構成、エージェントベースのモジュラー設計が特徴。
- **eBay「ShopBot」（Neo4j）**：会話型コマースのチャットボット。RDBMSを試したが、クエリ速度・スキーマ柔軟性・本番運用能力の観点からNeo4jプロパティグラフに移行。約1.6億のアクティブバイヤー、10億超のライブ出品をスケールで扱う。定量的な成果指標は非公開（アーキテクチャ事例として参照）。
- **インポート貿易業のKG-RAGチャットボット（MDPI Software誌 2025, doi:10.3390/software5020015）**：社内文書・ワークフロー・異常事例・根本原因・製品属性をNeo4jで意味的に連結。RAG単独より、異常報告書の根本原因（封止機の加熱不足など）まで踏み込んだ回答を生成。NDAにより業界横断検証は未実施という限界も明記している。

**Customer 360／CRM／churn事例**
- **Comcast（Neo4j）**：xFiスマートホームで「人＝ID」ではなく「人＝個人情報・場所・人・デバイスへの関係の集合」として顧客プロファイルをグラフ化しパーソナライズ（定性的事例）。
- **テクノロジーメディア企業（Neo4j, AWS Cloud）**：解約シグナル（利用減・支払い問題・サポート苦情・コンテンツ消費）を1つの顧客グラフに統合し、分析速度10倍・手作業92%削減・churn兆候の早期検知を達成。
- **Jaguar Land Rover（TigerGraph）**：サプライチェーン（顧客サポートではない）だが、複雑なクエリ時間を3週間→45分に短縮。グラフのスケール性能の証左。
- **金融・KYC/AML（arXiv:2512.06240）**：Customer・Account・Transaction・Sanction・PEP・AlertをノードとするRAGグラフをNeo4jで構築し、コンプライアンス調査をLLMエージェントで支援。

**課題・失敗の知見**
- **エンティティ解決（entity resolution）の破綻が最大の失敗モード。** 同一人物が「Sagar S」「Sagar Shankaran」など複数エンティティに分裂（entity drift）すると、多段推論が誤った経路をたどり誤りが指数的に増幅する。Tiloresは「グラフDBでのERは本質的に二次（quadratic）問題でスケールしない」と指摘する。
- **グラフの陳腐化（staleness）。** 自動更新のない本番グラフは四半期で15〜20%真値からドリフトするとの指摘（Atlan）。「昨日のニュースが今日のハルシネーション」になる。
- **「ガバナンスなきGraphRAG」は無意味。** Atlanは「ガバナンスされたメタデータなしにGraphRAGを導入したチームは、保守負荷が2倍になり、ベクトルRAG比で測定可能な精度改善が得られなかった」と報告。
- **3インデックス同期地獄。** 本番GraphRAGはテキスト／ベクトル／グラフの3インデックスをリアルタイム同期する必要があり、文書の追加・更新・削除のたびに全ストアへ伝播＋エンティティ再解決が必要。
- 加えてGradient Flowは2024年時点で「本番で真のビジネス価値を出している例をほとんど知らない」と慎重姿勢を示しており、過度な期待は禁物。

### 2. 要素技術

**グラフDB比較（顧客状態管理の適性）**

| DB | 特徴 | 顧客状態管理での適性 |
|---|---|---|
| **Neo4j** | ネイティブプロパティグラフ、Cypher、成熟エコシステム、GDSライブラリ、AuraDBマネージド。インデックスフリー隣接性で多段走査が高速。オープンコア（Community=GPLv3／Enterprise=商用） | 最有力。開発者体験・ツール・LLM統合（LangChain/LangGraph/Text2Cypher/LLM Knowledge Graph Builder）が突出。OLAP寄り |
| **Amazon Neptune** | フルマネージド、Property Graph＋RDF両対応、Gremlin/SPARQL/openCypher、ストレージ128TiBまで自動スケール、Neptune Serverless、Neptune Analytics（インメモリ分析＋ベクトル） | AWS中心のクラウドファースト組織向き。Bedrock GraphRAGでグラフ知識不要で開始可。OLTP寄り |
| **TigerGraph** | ネイティブ並列・分散MPP、超大規模・深いマルチホップ分析に強い。2-hopで他DB比最大377倍を主張（自社ベンチ） | テラバイト級・リアルタイム大規模分析向き |
| **NebulaGraph** | オープンソース、大規模データで高スループット（小規模ではNeo4jがやや優位との第三者テスト） | Web規模・低レイテンシ運用向き |
| **ArangoDB** | マルチモデル（graph＋document＋key-value）、AQL、ACID | リッチな顧客プロファイル文書＋関係を1エンジンで扱いたい場合 |
| **Memgraph/FalkorDB** | インメモリ高速、リアルタイム。FalkorDBはGraphRAG SDK提供 | 低レイテンシ・ストリーミング・エージェント記憶向き |

**GraphRAGの技術概要と最新動向**
- 基本は「文書からエンティティ・関係を抽出→KG構築→グラフ走査＋ベクトル検索を組み合わせて回答」。Microsoft Research が2024年に提唱。コミュニティ検出で階層要約を作り、全体俯瞰質問に強い。Microsoft GraphRAGは複雑な多エンティティ質問でcomprehensiveness 86%（ベクトルRAG 57%）と報告。
- **設計パターン（Gradient Flow / Neo4j分類）**：(a) ベクトル検索→KGで事実補強（下流補強）、(b) KGで先にエンティティ特定→ベクトル検索（クエリ拡張）、(c) ベクトル＋キーワード＋グラフのハイブリッド検索＋リランク。顧客サポート・パーソナライズには(a)型が適合とされる。
- **コスト最適化が主戦場**：フルGraphRAGは100万トークンのインデックス化にGPT-4oで$20〜40。LightRAGは約$0.50、Microsoft LazyGraphRAG（2024年11月発表）はインデックスコストをフルGraphRAGの0.1%（ベクトルRAG同等）に削減し、グローバルクエリコストを700分の1以下にする。
- エージェント構成では、各リトリーバを「ツール」としてLLMが反復選択する形が主流。

**LLMエージェント×グラフDB連携**
- **LangGraph＋Neo4j**：`langchain_neo4j`の`@tool`デコレータでCypherクエリをツール化、`Neo4jVector`でベクトル検索、`langgraph-checkpoint-neo4j`（Neo4jSaver/AsyncNeo4jSaver）で会話状態・エージェント状態をグラフに永続化。Supervisor型マルチエージェントでグラフDB＋ベクトルDB＋メタデータを役割分担する事例（法務文書解析等）が報告されている。
- **Graphiti/Zep**：時間認識型KGをNeo4j/Neptune/FalkorDB/Kuzu上に構築。bi-temporalモデルで「事象発生時刻」と「取り込み時刻」を両方追跡し、矛盾する新知識は破棄せず無効化（t_valid/t_invalid）。顧客の状態履歴の正確な再現に適する。
- AutoGen/CrewAIもマルチエージェント協調に使われるが、本ユースケースではLangGraphのグラフ型オーケストレーション＋Neo4j公式統合が最も実装情報が豊富。

**顧客ナレッジグラフ構築手法**
- **スキーマ設計が成否を分ける（ontology first, extraction second）。** 抽出前に①エンティティ型②関係型（方向・カーディナリティ）③プロパティ（必須/任意）④ドメインオントロジー（統制語彙）を定義する。TigerGraphは「あるバイオテックチームがこの工程を飛ばし、『Phase III trial』が17種の別エンティティ型に分裂しクロス試験クエリ不能になった」例を挙げる。
- **LLMによる抽出**：専門家設計オントロジー／Competency Questions（CQ）でスキーマを与えガイドする「スキーマベース」と、LLMが自律的にエンティティ・関係を発見する「スキーマフリー」がある。LLMベース抽出はエンティティ抽出でprecision 98.82%/recall 93.18%/F1 95.92%、関係抽出precision 75%超の報告も。
- **検証層が必須**：抽出結果をスキーマ照合し低信頼抽出を人手レビューに回す。エンティティ解決を第一級ステップとして扱う。

**リアルタイムデータ（IoT・バッテリー・使用状況）の取り込み**
- **Kafka＋Neo4j**が定番。Neo4j Streams／Kafka Connect Neo4j Sink（Confluent Hub）でCDC・ストリーミング取り込み。Kafkaをバッファにしてデータソースとグラフを疎結合化し、取り込みスパイクを平準化する。Kafkaは元々LinkedInで開発され1日1兆メッセージ、Netflixは1日5000億メッセージ規模の実績。
- ベストプラクティス：グラフに書く前にKSQL等でストリームを整形、トピックは一貫したフォーマットに保つ、並列ロード時はグラフの素な部分にトピックを分割しロック競合を回避。
- **バッテリー/デバイス状態**は「デジタルツイン」パターンと親和。AWS IoT Device Shadowでデバイスの現在状態（SoH/SoC/充電サイクル）をオフライン時も含め仮想表現できる。これをグラフのデバイスノード属性として同期すれば、接客時に「お客様のデバイスXはバッテリー劣化が進行している」といった状態依存の回答が可能になる。デジタルツイングラフ（arXiv:2304.10018）はIoT世界をグラフで自動構築する研究。

**自然言語→グラフクエリ変換（Text-to-Cypher等）**
- **Neo4j Text2Cypher（2024）データセット**：44,387インスタンス（訓練39,554/テスト4,833）をHuggingFaceで公開。GPT-4oおよびファインチューン済みモデル（tomasonjo_text2cypher）でExactMatch約30%（ExactMatchは改行・空白に過敏な厳しい指標）。
- **最新動向（VLDB 2025ワークショップ）**：Neo4jはText-to-Cypher、Schema Filtering（推論トークン削減）、GDS Agent（アルゴリズム自律選択）を発表。CypherBench（Wikidata由来）、Auto-Cypher/SynthCypher（自動合成訓練データ）等のベンチマークも登場。Multi-Agent GraphRAG（arXiv:2511.08274）等の研究も進行中。
- **data.worldのOBQC（arXiv:2405.11706）**：オントロジーベースのクエリ検査＋LLM修復で、SPARQL正答率を54%→72%に改善。Text-to-クエリの誤りをオントロジーで検証する有効性を示す。

### 3. 実現方法・アーキテクチャ

**全体アーキテクチャ（推奨：ルーティング型ハイブリッド）**
```
[ユーザー発話]
   ↓
[LLMエージェント / LangGraph オーケストレータ]
   ├─ Intent Router（軽量分類器 or 小型LLM）でクエリ種別判定
   ├─ 構造的・状態依存クエリ → Text-to-Cypher → グラフDB（顧客状態KG）
   │      例：「私のデバイスのバッテリー状態は？」「契約中のプラン一覧」
   ├─ 意味的・FAQ系クエリ → ベクトル検索（マニュアル/FAQ）
   │      例：「初期化の方法は？」
   └─ 複合 → グラフ＋ベクトルのハイブリッド検索＋リランク
   ↓
[コンテキスト統合 → LLM生成 → 出典付き回答]

[リアルタイム取り込み] IoT/利用ログ → Kafka → グラフDB（状態エッジ更新）
[エージェント記憶] Graphiti/Zep（bi-temporal KG）で会話・顧客状態履歴
```
AWSフルマネージド版なら：API Gateway→Lambda/Fargate（オーケストレータ）→ベクトル検索（OpenSearch kNN）→Neptune多段走査（1〜3 hop、ロール/関係型でフィルタ）→Bedrock LLM生成（Neptuneノード/チャンクIDの出典付き）。Bedrock Knowledge Bases GraphRAG（Neptune Analytics）ならグラフモデリング知識なしで数クリックで構築でき、エンティティ抽出はClaude 3 Haikuが担当する。

**技術スタック候補（Python前提）**
- グラフDB：Neo4j（AuraDB）or Amazon Neptune
- ベクトル：Neo4jネイティブベクトルインデックス（単一DBでベクトル＋キーワード＋グラフの3検索が可能）、pgvector、OpenSearch、Weaviate、Pinecone
- オーケストレーション：LangGraph＋LangChain（`langchain-neo4j`）、LlamaIndex（`KnowledgeGraphRAGRetriever`、`with_nl2graphquery`、`graph_traversal_depth`）
- エージェント記憶：Graphiti（OpenAI/Anthropic/Gemini対応、構造化出力必須）
- ストリーミング：Apache Kafka＋Neo4j Connector／Kafka Connect、Spark
- LLM：GPT-4o（抽出品質）/ GPT-4o-mini（約10倍安価、抽出品質はやや低下）、Claude、ローカルモデル
- KG構築：Neo4j LLM Knowledge Graph Builder、FalkorDB GraphRAG SDK、エンティティ解決にSenzing等専用ツール

**スキーマ設計例（顧客状態管理）**
```
ノード:
  (:Customer {id, name, segment, signup_date})
  (:Product {sku, name, category})
  (:Device {serial, model, soh, soc, charge_cycles, last_seen})  ← IoT同期
  (:Content {id, title, genre})
  (:SupportTicket {id, status, created_at})
  (:Issue {id, symptom, root_cause})  ← 過去事例KG（LinkedIn型）

関係（状態エッジ）:
  (Customer)-[:OWNS {purchased_at}]->(Product)
  (Customer)-[:USES]->(Device)
  (Customer)-[:WATCHED {timestamp, duration}]->(Content)
  (Customer)-[:RAISED]->(SupportTicket)
  (SupportTicket)-[:ABOUT]->(Product|Device)
  (Issue)-[:SIMILAR_TO]->(Issue)  ← inter-issue関係
  (Device)-[:HAS_STATE {t_valid, t_invalid}]->(BatteryState)  ← bi-temporal
```
バッテリー劣化のような時系列状態はbi-temporalエッジ（Graphiti流）で履歴を破棄せず保持し、「いつ時点の状態か」を再現可能にする。

**スケーラビリティ・パフォーマンス考慮点**
- **インデックスフリー隣接性**で多段走査はデータ総量に依存せず線形。RDBのJOINは深さに対し指数的に劣化（InterSystems：深さ4超で指数的増、各JOINで1.5〜2倍）。
- サブグラフは小さく保つ（<500トリプル目安）：プロンプト肥大とトークンコストを抑制。
- 密なグラフでの「近傍爆発（neighborhood explosion）」、多hop先の正解ノード特定はNeo4jも課題と認識（VLDB 2025）。
- 3インデックス同期、グラフ鮮度の自動更新（インクリメンタル更新／日次リフレッシュ）。
- Neptune Analyticsはオートスケール非対応・S3データソースのみ・1データソース1000ファイル上限・約$0.48/時のメモリ最適化課金等の制約あり。

**RDB/ベクトルDB単独との優劣**

優位点：
- 多段関係探索が桁違いに高速（友達の友達深さ4でNeo4j 1.359秒 vs MySQL 1,543秒＝約1,135倍）。
- 関係・文脈を保持するため、複数文書/エンティティ横断の質問でベクトルRAGを上回る（Microsoft GraphRAG：複雑な多エンティティ質問でcomprehensiveness 86% vs ベクトルRAG 57%）。
- 出典・推論経路が辿れる説明可能性。スキーマ変更が容易（ノード/エッジ追加のみ）。

劣位点：
- 構築・運用コスト（LLM抽出コスト、エンティティ解決、グラフ鮮度維持）。
- 単純な1-hop/点ルックアップ・集約・GROUP BYではRDBやベクトルRAGが勝つことがある（arXiv:2401.07483で単純ルックアップはPostgreSQL 15ms がNeo4j 23ms に優位な例）。
- グラフ思考・Cypher学習コスト。チームにグラフ専門性がないと「負債」化。

**実装上の課題・リスクと対策**
- **データ整備**：エンティティ解決を最初に設計（embeddings＋エイリアスルール、または専用ER製品）。スキーマ・命名規約をデータカタログでガバナンス。
- **メンテナンスコスト**：自動メタデータパイプラインでソース変更をグラフに継続伝播。LazyGraphRAG/LightRAGで構築コストを削減。
- **クエリ最適化**：Schema Filteringで推論トークン削減、Intent Routerで全インデックスを毎回叩くのを回避。
- **評価CI**：Golden SetでベクトルRAGと定量比較し「複雑にしたが効果なし」を防ぐ。

### 実現可能性評価（技術成熟度・コスト・ROI）
- **技術成熟度**：GraphRAGはまだ発展途上（Gradient Flowは「本番で真のビジネス価値を出す例はほとんど知らない」と2024年時点で指摘）だが、AWS Bedrock GraphRAG GA（2025年3月）、Neo4j/LangChain統合、Zep商用化など2025〜2026年で急速に実用化が進む。市場はグラフDBがCAGR約24%、ナレッジグラフがCAGR約36.6%で成長しているとの市場調査もある（renueによる二次まとめ。一次出典の検証レベルは要確認）。
- **コスト**：PoCはNeo4j Community Edition（無料）やLazyGraphRAGで数百〜数千円から検証可能。本番はNeo4j Enterprise（年間数百万〜数千万円規模）やNeptune（従量課金）。最大のコスト要因はデータモデル設計とドメイン人材の確保。
- **ROI**：適用領域を選べば高い。LinkedIn解決時間-28.6%、data.world正答率3倍が代表的指標。一方、コーパス1万文書未満・関係が単純ならベクトルRAGの方がコスト・速度・保守で勝つ。

## Recommendations

1. **段階的に導入する（最重要）。**
   - **Stage 1（PoC, 1〜2か月）**：Neo4j Community/AuraDB無料枠＋LangChain/LangGraphで、顧客・製品・デバイス・コンテンツの最小スキーマを設計。Golden Set（実際の問い合わせ50〜100件）を作り、ベクトルRAG単独 vs グラフ＋ベクトルで正答率・解決時間を定量比較。**閾値：グラフ併用でGolden Set正答率が有意（例：+15ポイント以上）改善しなければ、グラフ投資を見送りベクトルRAG＋構造化メタデータで十分。**
   - **Stage 2（限定本番, 3〜6か月）**：効果が出た問い合わせ類型に限定して本番投入。「複雑な関係質問だけGraphRAG、それ以外は従来RAG」のIntent Routerでハイブリッド化。Kafka経由のIoT/利用状況取り込みを追加。エンティティ解決とグラフ自動更新パイプラインを必ず実装する。
   - **Stage 3（拡張）**：Graphiti/Zepでエージェント記憶（顧客状態履歴のbi-temporal管理）を追加し、複数事業部・チャネルへ展開。

2. **エンティティ解決とガバナンスを「後回しにしない」。** これが最大の失敗要因。スキーマ（オントロジー）設計を抽出に先行させ、命名規約・統制語彙をカタログ管理する。10万件超の名寄せにはSenzing等の専用ER製品を検討。

3. **DB選定の指針**：AWS中心なら**Neptune（Bedrock GraphRAGでグラフ知識不要に開始）**、開発者体験・LLM統合・自前運用なら**Neo4j**、テラバイト級超大規模分析なら**TigerGraph**、低レイテンシ・エージェント記憶重視なら**Memgraph/FalkorDB**。

4. **コスト管理**：本番投入前に「文書数×LLM抽出コスト」を試算。LazyGraphRAG/LightRAGやGPT-4o-miniでインデックスコストを抑制し、FinOps SLOを設定する。

5. **評価を継続的に回す**：グラフ鮮度のドリフト（四半期15〜20%）を監視し、自動リフレッシュを運用要件として扱う。CIでベクトルRAGとの定量比較を継続する。

## Caveats
- LinkedIn・data.world・Microsoftの数値は各社の論文/発表に基づくが、多くは自社環境・自社ベンチマークでの測定であり、汎用的な再現性は保証されない。特にTigerGraph「377倍」「600% ROI（Forrester TEI）」、Memgraph各種比較は**ベンダー自社ベンチ／ベンダー委託調査**であり割り引いて解釈すべき。
- 『Neo4j in Action』の深さ別ベンチ（約1,135倍）は2014年のベンダー系書籍が一次出典で、査読論文（arXiv:1706.06654）に再掲されているが、ハードウェア・実装に依存する。グラフ優位は多段JOIN/パターンマッチに特有で、集約系ではRDBが勝つこともある（ワークロード依存）。
- カスタマーサポートで**解決時間/NPS/churnを定量報告した「実名」事例は依然少ない**。LinkedIn（実名・定量）が際立つが、eBay・Comcastは実名だが定性的、NPS+23・解決40%高速化を報告したArcadeDB事例は企業名非公開。「グラフ＝必ず効果」と一般化しないこと。
- GraphRAGは2024〜2026年に急成長中の新領域で、ベストプラクティス・ベンチマーク・コスト構造が流動的。本報告の市場成長率（CAGR）やコスト数値は調査時点（2026年6月）のものであり、引用元（renue等のまとめ記事や二次情報）の検証レベルにばらつきがある点に留意されたい。