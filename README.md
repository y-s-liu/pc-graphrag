
# PC-GraphRAG — 完整專案

一站式專案，含：
- `docker/`：Neo4j(+APOC+GDS) 與 FastAPI 應用（查相容/列主機板/電源檢查），可 `docker compose up` 起來
- `starter/`：對應書本第 1–8 章的逐章實作範例包
- `scripts/`：Neo4j 匯入腳本與查詢範本
- `data/`：示例 JSON（可替換成你的資料）

## 快速開始（Docker）
```bash
cd docker
# 1) 編輯 .env 設定密碼
# 2) 啟動
docker compose up -d --build
# 3) 套用唯一性約束與索引
docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD -f /var/lib/neo4j/import/neo4j_constraints.cypher
# 4) 匯入示例 JSON（先把你的 JSON 放入 app/data/）
docker compose run --rm app python /app/ingest_components_to_neo4j.py \
  --json /data/component_data_schema.json \
  --uri bolt://neo4j:7687 --user neo4j --password $NEO4J_PASSWORD --source dataset
# 5) 打開 API 文件
open http://localhost:8000/docs
```

## 專案結構
```
pc-graphrag/
├─ docker/                 # Docker 環境（Neo4j + FastAPI）
├─ starter/                # 逐章實作範例包（ch01~ch08）
├─ scripts/                # 匯入與查詢腳本
├─ data/
│  └─ component_data_schema.json   # 示例資料（可換成你自己的）
└─ README.md
```

> 建議流程：先 `docker/` 起服務 → 用 `scripts/` 匯入 → 跑 `starter/` 的章節練習與擴充。


## 安裝與執行步驟（本機 Docker）
1. 安裝 Docker 與 Docker Compose v2
2. 下載或 `git clone` 此專案
3. 到 `docker/` 目錄並編輯 `.env`（設定 `NEO4J_PASSWORD`）
4. 啟動服務：
   ```bash
   docker compose up -d --build
   ```
5. 套用 Neo4j 唯一性約束與索引：
   ```bash
   docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD -f /var/lib/neo4j/import/neo4j_constraints.cypher
   ```
6. 匯入資料（把你的 JSON 放到 `docker/app/data/`）：
   ```bash
   docker compose run --rm app python /app/ingest_components_to_neo4j.py      --json /data/component_data_schema.json      --uri bolt://neo4j:7687 --user neo4j --password $NEO4J_PASSWORD --source dataset
   ```
7. 打開 API 文件： http://localhost:8000/docs

### 常用 API
- `/fit?gpu=...&case=...`：檢查顯卡能否裝進機殼  
- `/mb?socket=AM5&mem=DDR5&limit=20`：列主機板  
- `/psu/check?gpu=...&cpu=...&psu=...`：電源瓦數檢查  
- `/build/plan?budget=30000&socket=AM5&mem=DDR5&form_factor=Mini-ITX&include_gpu=false`：預算內自動組裝  
