
# Docker 環境：Neo4j(+APOC+GDS) + Python App

## 快速開始
```bash
cd docker_graphrag_pc
# 第一次請修改 .env 的密碼
docker compose up -d --build
# 套用約束與索引
docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD -f /var/lib/neo4j/import/neo4j_constraints.cypher
# 匯入示例 JSON（請先把你的 JSON 放到 app/data/ 內）
docker compose run --rm app python /app/ingest_components_to_neo4j.py --json /data/component_data_schema.json --uri bolt://neo4j:7687 --user neo4j --password $NEO4J_PASSWORD --source dataset
```

## 目錄結構
- `compose.yaml`：定義 neo4j 與 app 兩個服務
- `.env`：密碼設定（`NEO4J_PASSWORD` 與 `NEO4J_AUTH`）
- `neo4j/`：Neo4j 的資料、日誌與 import 目錄（放 cypher 初始化檔）
- `app/`：Python 應用容器（含 `ingest_components_to_neo4j.py` 與 `requirements.txt`）

## 連線資訊
- Neo4j Browser: http://localhost:7474
- Bolt: bolt://localhost:7687
- 帳號/密碼：`neo4j / $NEO4J_PASSWORD`

> 提醒：本範例使用 Neo4j 5 Enterprise 映像（需接受授權）。如需社群版請改 `neo4j:5` 並移除 `NEO4J_ACCEPT_LICENSE_AGREEMENT` 與 GDS 插件。
