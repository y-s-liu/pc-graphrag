
# App 容器（資料匯入與未來應用）

## 匯入你的 JSON 到 Neo4j
1) 將你的 JSON 放到 `app/data/component_data_schema.json`（或換一個檔名）。
2) 確認 `../.env` 的 `NEO4J_PASSWORD`；`NEO4J_AUTH` 會自動帶入同一密碼。
3) 啟動環境：
   ```bash
   docker compose up -d --build
   ```
4) 建立唯一性約束與索引：
   ```bash
   docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD -f /var/lib/neo4j/import/neo4j_constraints.cypher
   ```
5) 執行匯入：
   ```bash
   docker compose run --rm app python /app/ingest_components_to_neo4j.py \
     --json /data/component_data_schema.json \
     --uri bolt://neo4j:7687 --user neo4j --password $NEO4J_PASSWORD --source dataset
   ```

## 檢查圖譜
- 開啟 Neo4j Browser： http://localhost:7474
- 帳密：neo4j / 你在 `.env` 設定的密碼

## （選配）安裝 GDS 後跑社群偵測示例
```bash
docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD -f /var/lib/neo4j/import/gds_community.cypher
```

## 下一步
- 將 ch04 的 Cypher 模板貼到 Browser 測試
- 將 ch02/03 的文本檢索接到你的應用（可在此容器擴充 FastAPI 服務）


## 啟動 API
```bash
docker compose up -d --build
# 等 app 起來後，瀏覽 http://localhost:8000/docs
```

## 測試 API
- 健康檢查：
  ```
  curl http://localhost:8000/health
  ```
- 檢查顯卡能否放進機殼：
  ```
  curl "http://localhost:8000/fit?gpu=MSI%20GeForce%20RTX%204070%20SUPER&case=Fractal%20Design%20North"
  ```
- 列主機板（AM5 + DDR5）：
  ```
  curl "http://localhost:8000/mb?socket=AM5&mem=DDR5&limit=20"
  ```
- 電供是否足夠：
  ```
  curl "http://localhost:8000/psu/check?gpu=MSI%20GeForce%20RTX%204070%20SUPER&cpu=AMD%20Ryzen%205%207600X&psu=Seasonic%20Focus%20GX-850"
  ```


## 預算內自動組裝（/build/plan）
- 參數：`budget`(TWD), `socket`(預設 AM5), `mem`(預設 DDR5), `form_factor`(預設 Mini-ITX), `include_gpu`(bool), `topn`(每類別候選數), `max_results`
- 範例：
  ```
  curl "http://localhost:8000/build/plan?budget=30000&socket=AM5&mem=DDR5&form_factor=Mini-ITX&include_gpu=false&topn=5&max_results=10"
  ```


### 使用 GPT-5 生成中文說明（explain=1）
- 顯卡裝機殼＋說明：
  ```
  curl "http://localhost:8000/fit?gpu=MSI%20GeForce%20RTX%204070%20SUPER&case=Fractal%20Design%20North&explain=1"
  ```
- 電源瓦數檢查＋說明：
  ```
  curl "http://localhost:8000/psu/check?gpu=...&cpu=...&psu=...&explain=1"
  ```
- 預算內自動組裝＋說明：
  ```
  curl "http://localhost:8000/build/plan?budget=30000&socket=AM5&mem=DDR5&form_factor=Mini-ITX&include_gpu=false&explain=1"
  ```
