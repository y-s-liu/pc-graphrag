
import os
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from neo4j import GraphDatabase, basic_auth
from openai import OpenAI

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")

driver = GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD))
oa_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = FastAPI(title="PC GraphRAG Mini API", version="0.5.0")

def run_cypher(query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    with driver.session() as session:
        res = session.run(query, params or {})
        return [r.data() for r in res]

def llm_explain(system: str, prompt: str) -> str:
    if not oa_client:
        return "(未設定 OPENAI_API_KEY，略過說明生成)"
    resp = oa_client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":prompt}]
    )
    return resp.choices[0].message.content.strip()

@app.get("/health")
def health():
    try:
        rows = run_cypher("RETURN 1 AS ok")
        return {"status": "ok", "neo4j": rows[0]["ok"] == 1}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fit")
def fit_check(gpu: str = Query(..., description="GPU model_name"),
              case: str = Query(..., description="Case model_name"),
              explain: bool = Query(False, description="是否用 GPT-5-nano 生成中文說明")):
    q = """
    MATCH (g:GPU {model_name:$gpu}), (c:Case {model_name:$case})
    WITH g, c,
         coalesce(g.length_num, g.length) AS gl,
         c.max_gpu_length AS cl,
         g.width_slots AS gw,
         c.max_gpu_width AS cw
    RETURN g.model_name AS gpu, c.model_name AS case,
           gl AS gpu_length, cl AS case_max_length,
           gw AS gpu_slots, cw AS case_max_slots,
           (gl <= cl) AS fits_by_length,
           (gw <= cw) AS fits_by_width
    """
    rows = run_cypher(q, {"gpu": gpu, "case": case})
    if not rows:
        raise HTTPException(status_code=404, detail="GPU 或 Case 找不到，請確認 model_name")
    row = rows[0]
    row["fits_all"] = bool(row.get("fits_by_length")) and bool(row.get("fits_by_width"))
    if explain:
        sys_msg = "你是裝機顧問，請用台灣繁體中文，清楚說明相容與否與依據，列點描述。"
        user_msg = f"顯卡: {row['gpu']}，機殼: {row['case']}，長度 {row['gpu_length']} vs 上限 {row['case_max_length']}，槽寬 {row['gpu_slots']} vs 上限 {row['case_max_slots']}。請給結論與理由。"
        row["explanation"] = llm_explain(sys_msg, user_msg)
    return row

@app.get("/mb")
def list_motherboards(socket: str = Query(..., description="Socket，如 AM5"),
                      mem: str = Query(..., description="Memory type，如 DDR5"),
                      limit: int = Query(50, ge=1, le=200)):
    q = """
    MATCH (m:Motherboard)-[:SUPPORTS_SOCKET]->(:Socket {name:$socket})
    MATCH (m)-[:SUPPORTS_MEMORY_TYPE]->(:MemoryStandard {name:$mem})
    RETURN m.model_name AS model_name, m.chipset AS chipset, m.form_factor AS form_factor,
           m.memory_slots AS memory_slots, m.memory_max AS memory_max
    ORDER BY model_name
    LIMIT $k
    """
    return run_cypher(q, {"socket": socket, "mem": mem, "k": limit})

@app.get("/psu/check")
def psu_check(gpu: str = Query(...), cpu: str = Query(...), psu: str = Query(...), explain: bool = Query(False)):
    q = """
    MATCH (g:GPU {model_name:$gpu})
    MATCH (c:CPU {model_name:$cpu})
    MATCH (p:PSU {model_name:$psu})
    WITH g, c, p,
         coalesce(g.recommended_psu,
                  coalesce(g.tgp_num, g.tgp) + coalesce(c.tdp_num, c.tdp) + 200) AS req
    RETURN p.model_name AS psu, p.wattage AS psu_watt,
           req AS recommended_min, (p.wattage >= req) AS ok
    """
    rows = run_cypher(q, {"gpu": gpu, "cpu": cpu, "psu": psu})
    if not rows:
        raise HTTPException(status_code=404, detail="GPU/CPU/PSU 其中有找不到的型號")
    row = rows[0]
    if explain:
        sys_msg = "你是裝機顧問，請用台灣繁體中文解釋電源瓦數是否足夠，並給建議裕度。"
        user_msg = f"PSU: {row['psu']}({row['psu_watt']}W)，需求最小瓦數 {row['recommended_min']}W，是否足夠: {row['ok']}。"
        row["explanation"] = llm_explain(sys_msg, user_msg)
    return row

@app.get("/build/plan")
def build_plan(
    budget: int = Query(30000, ge=1000, description="總預算（含稅，TWD）"),
    socket: str = Query("AM5", description="平台插槽，如 AM5 / LGA1700"),
    mem: str = Query("DDR5", description="記憶體代別"),
    form_factor: str = Query("Mini-ITX", description="主機板/機殼尺寸（如 Mini-ITX/ATX）"),
    include_gpu: bool = Query(False, description="是否包含獨立顯卡"),
    topn: int = Query(5, ge=1, le=20, description="每類別候選數"),
    max_results: int = Query(20, ge=1, le=50, description="最多回傳組合數"),
    explain: bool = Query(False, description="是否用 GPT-5-nano 產生中文解說與選購建議")
):
    cypher = """
    WITH $socket AS socket, $mem AS mem, $form_factor AS ff, $include_gpu AS wantGpu,
         toInteger($topn) AS N, toInteger($max_results) AS K, toInteger($budget) AS BUD

    CALL {
      MATCH (cpu:CPU)-[:REQUIRES_SOCKET]->(:Socket {name:socket})
      OPTIONAL MATCH (cpu)-[:HAS_PRICE]->(pr:PriceRecord)
      WITH cpu, pr ORDER BY pr.fetched_at DESC
      WITH cpu, collect(pr)[0] AS lpr
      WITH cpu, coalesce(lpr.price, 0) AS price
      RETURN collect({n:cpu, price:price})[0..N] AS cpus
    }

    CALL {
      MATCH (mb:Motherboard)-[:SUPPORTS_SOCKET]->(:Socket {name:socket})
      MATCH (mb)-[:SUPPORTS_MEMORY_TYPE]->(:MemoryStandard {name:mem})
      OPTIONAL MATCH (mb)-[:HAS_PRICE]->(pr:PriceRecord)
      WITH mb, pr ORDER BY pr.fetched_at DESC
      WITH mb, collect(pr)[0] AS lpr
      WITH mb, coalesce(mb.form_factor, ff) AS formf, coalesce(lpr.price,0) AS price
      RETURN collect({n:mb, price:price, form:formf})[0..N] AS mbs
    }

    CALL {
      MATCH (ram:MemoryKit)-[:STANDARD]->(:MemoryStandard {name:mem})
      OPTIONAL MATCH (ram)-[:HAS_PRICE]->(pr:PriceRecord)
      WITH ram, pr ORDER BY pr.fetched_at DESC
      WITH ram, collect(pr)[0] AS lpr
      RETURN collect({n:ram, price:coalesce(lpr.price,0)})[0..N] AS rams
    }

    CALL {
      MATCH (cse:Case)-[:SUPPORTS_FORM_FACTOR]->(:FormFactor {name:ff})
      OPTIONAL MATCH (cse)-[:HAS_PRICE]->(pr:PriceRecord)
      WITH cse, pr ORDER BY pr.fetched_at DESC
      WITH cse, collect(pr)[0] AS lpr
      RETURN collect({n:cse, price:coalesce(lpr.price,0)})[0..N] AS cases
    }

    CALL {
      WITH wantGpu AS wg, N AS N
      CALL {
        WITH wg, N
        MATCH (g:GPU)
        OPTIONAL MATCH (g)-[:HAS_PRICE]->(pr:PriceRecord)
        WITH g, pr ORDER BY pr.fetched_at DESC
        WITH g, collect(pr)[0] AS lpr
        WITH g, coalesce(lpr.price,0) AS price
        RETURN collect({n:g, price:price})[0..N] AS arr
      }
      RETURN CASE WHEN wg THEN arr ELSE [ {n:null, price:0} ] END AS gpus
    }

    CALL {
      MATCH (p:PSU)
      OPTIONAL MATCH (p)-[:HAS_PRICE]->(pr:PriceRecord)
      WITH p, pr ORDER BY pr.fetched_at DESC
      WITH p, collect(pr)[0] AS lpr
      RETURN collect({n:p, price:coalesce(lpr.price,0)})[0..N] AS psus
    }

    WITH cpus, mbs, rams, cases, gpus, psus, BUD
    UNWIND cpus AS C
    UNWIND mbs AS M
    WITH C, M, rams, cases, gpus, psus, BUD
    WHERE C.n.socket = M.n.socket
      AND (M.form = $form_factor OR M.n.form_factor = $form_factor OR $form_factor IS NULL)
    UNWIND rams AS R
    WITH C, M, R, cases, gpus, psus, BUD
    WHERE R.n.type = $mem OR R.n.type IS NULL

    UNWIND cases AS S
    WITH C, M, R, S, gpus, psus, BUD

    UNWIND gpus AS G
    WITH C, M, R, S, G, psus, BUD,
         (G.n IS NULL OR (
           coalesce(G.n.length_num, G.n.length, 999999) <= S.n.max_gpu_length AND
           coalesce(G.n.width_slots, 0) <= coalesce(S.n.max_gpu_width, 10)
         )) AS gpuFits
    WHERE gpuFits

    WITH C, M, R, S, G, psus, BUD,
         CASE
           WHEN G.n IS NULL THEN coalesce(C.n.tdp_num, C.n.tdp, 65) + 150
           ELSE coalesce(G.n.recommended_psu,
                         coalesce(G.n.tgp_num, G.n.tgp, 150) + coalesce(C.n.tdp_num, C.n.tdp, 65) + 200)
         END AS reqW

    UNWIND psus AS P
    WITH C, M, R, S, G, P, BUD, reqW
    WHERE P.n.wattage >= reqW

    WITH
      C.n AS cpu, C.price AS cpu_price,
      M.n AS mb,  M.price AS mb_price,
      R.n AS ram, R.price AS ram_price,
      S.n AS case, S.price AS case_price,
      G.n AS gpu, G.price AS gpu_price,
      P.n AS psu, P.price AS psu_price,
      reqW,
      (C.price + M.price + R.price + S.price + G.price + P.price) AS total

    WHERE total <= BUD
    RETURN
      cpu.model_name   AS cpu,
      mb.model_name    AS motherboard,
      ram.model_name   AS memory,
      case.model_name  AS case,
      psu.model_name   AS psu,
      gpu.model_name   AS gpu,
      reqW             AS required_watt_min,
      cpu_price, mb_price, ram_price, case_price, psu_price, gpu_price,
      total
    ORDER BY total ASC
    LIMIT K
    """
    rows = run_cypher(cypher, {
        "budget": budget, "socket": socket, "mem": mem,
        "form_factor": form_factor, "include_gpu": include_gpu,
        "topn": topn, "max_results": max_results
    })
    if not rows:
        raise HTTPException(status_code=404, detail="沒有找到符合預算與條件的組合；可放寬條件或提高 topn/budget")
    payload = {"params": {
                "budget": budget, "socket": socket, "mem": mem,
                "form_factor": form_factor, "include_gpu": include_gpu,
                "topn": topn, "max_results": max_results
            },
            "results": rows}
    if explain:
        sys_msg = "你是專業裝機顧問，使用台灣繁體中文。根據提供的多組零件與總價，挑出 1~2 組最合理的搭配並說明取捨，附上相容性與功耗依據。"
        preview = rows[:3]
        user_msg = "候選：\n" + "\n".join([str(r) for r in preview]) + f"\n條件：預算 {budget}，平台 {socket}/{mem}/{form_factor}，含獨顯: {include_gpu}。"
        payload["explanation"] = llm_explain(sys_msg, user_msg)
    return payload
