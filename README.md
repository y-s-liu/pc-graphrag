
# PC-GraphRAG（gpt-5-nano 版）

這是一個全新專案，Docker 一鍵啟動 **Neo4j(+APOC+GDS)** 與 **FastAPI**，並提供 **/build/plan** 自動配單。
OpenAI 預設模型改為 **gpt-5-nano**，可在 `.env` 調整。

## 快速開始
```bash
git clone <你的repo>
cd pc-graphrag-nano/docker

# 0) 設定 .env
#    - NEO4J_PASSWORD（初始化 neo4j 使用者密碼）
#    - OPENAI_API_KEY（要用 explain=1 才需要）
#    - OPENAI_MODEL 預設 gpt-5-nano
vi .env

# 1) 啟動
docker compose up -d --build

# 2) 套用唯一性約束與索引
docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD   -f /var/lib/neo4j/import/neo4j_constraints.cypher

# 3) 匯入資料（把你的 JSON 放到 docker/app/data/）
docker compose run --rm app python /app/ingest_components_to_neo4j.py   --json /data/component_data_schema.json   --uri bolt://neo4j:7687 --user neo4j --password $NEO4J_PASSWORD --source dataset

# 4) 打開 API 文件
open http://localhost:8000/docs
```

## API（皆可加 `&explain=1` 由 gpt-5-nano 生成中文說明）
- `GET /health`
- `GET /fit?gpu=<型號>&case=<型號>`
- `GET /mb?socket=AM5&mem=DDR5&limit=50`
- `GET /psu/check?gpu=<型號>&cpu=<型號>&psu=<型號>`
- `GET /build/plan?...`

## 常見問題
- **Restarting**：`.env` 只放 `NEO4J_PASSWORD`，`compose.yaml` 內的 `NEO4J_AUTH: "neo4j/${NEO4J_PASSWORD}"` 會自動帶入。
- **權限**（Linux）：`sudo chown -R 7474:7474 neo4j/data neo4j/logs neo4j/import` 再 `up -d`。
