#!/usr/bin/env python3
"""
Ingest PC components JSON into Neo4j (property graph).
- Creates nodes for: CPU, Motherboard, MemoryKit, GPU, Storage, PSU, Case, Cooler
- Creates vocab nodes: Socket, Chipset, MemoryStandard, FormFactor, Brand
- Creates relationships:
  CPU -> REQUIRES_SOCKET -> Socket
  Motherboard -> SUPPORTS_SOCKET -> Socket
  Motherboard -> HAS_CHIPSET -> Chipset
  Motherboard -> SUPPORTS_MEMORY_TYPE -> MemoryStandard
  MemoryKit -> STANDARD -> MemoryStandard
  Case -> SUPPORTS_FORM_FACTOR -> FormFactor (parsed from 'motherboard_support')
  Part -> MADE_BY -> Brand (brand inferred from model_name first token)
  Part -> HAS_PRICE -> PriceRecord {price, fetched_at, source}
Usage:
  python ingest_components_to_neo4j.py --json /data/component_data_schema.json \
    --uri bolt://neo4j:7687 --user neo4j --password <pwd> --source dataset
"""
import argparse, json, re
from typing import Dict, Any, List
from neo4j import GraphDatabase, basic_auth

PART_LABELS = ["CPU","Motherboard","MemoryKit","GPU","Storage","PSU","Case","Cooler"]

def infer_brand(model_name: str) -> str:
    return (model_name or "").split()[0] if model_name else None

def ensure_vocab(tx, label: str, name: str):
    tx.run(f"MERGE (v:{label} {{name:$name}})", name=name)

def set_props(tx, label: str, model_name: str, props: Dict[str, Any]):
    tx.run(f"MERGE (n:{label} {{model_name:$model}}) SET n += $props", model=model_name, props=props)

def link(tx, src_label: str, src_key: str, rel: str, dst_label: str, dst_key: str, src_id: str, dst_name: str):
    tx.run(
        f"MATCH (s:{src_label} {{model_name:$sid}}), (d:{dst_label} {{name:$dname}}) "
        f"MERGE (s)-[r:{rel}]->(d)",
        sid=src_id, dname=dst_name
    )

def create_price(tx, part_label: str, model: str, price: float, fetched_at: str = None, source: str = None):
    tx.run(
        "MATCH (p:{pl} {{model_name:$m}}) "
        "CREATE (p)-[:HAS_PRICE]->(:PriceRecord {{price:$price, fetched_at:$dt, source:$src}})"
        .format(pl=part_label),
        m=model, price=price, dt=fetched_at, src=source
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    ap.add_argument("--uri", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--source", default="dataset")
    args = ap.parse_args()

    drv = GraphDatabase.driver(args.uri, auth=basic_auth(args.user, args.password))
    data = json.load(open(args.json, "r", encoding="utf-8"))
    comps = data.get("components", {})

    with drv.session() as ses:
        # 1) Upsert part nodes with all properties
        for label in PART_LABELS:
            for item in comps.get(label.lower(), []):
                model = item.get("model_name") or item.get("name")
                if not model:
                    continue
                props = dict(item)
                props["source_tag"] = args.source
                ses.execute_write(set_props, label, model, props)

                # Brand
                b = infer_brand(model)
                if b:
                    ses.execute_write(ensure_vocab, "Brand", b)
                    ses.run(
                        "MATCH (p:{pl} {{model_name:$m}}),(b:Brand {{name:$b}}) "
                        "MERGE (p)-[:MADE_BY]->(b)".format(pl=label),
                        m=model, b=b)

        # 2) Link structured relationships
        for cpu in comps.get("cpu", []):
            model = cpu.get("model_name")
            if not model: continue
            sock = cpu.get("socket")
            if sock:
                ses.execute_write(ensure_vocab, "Socket", sock)
                ses.execute_write(link, "CPU", "model_name", "REQUIRES_SOCKET", "Socket", "name", model, sock)

        for mb in comps.get("motherboard", []):
            model = mb.get("model_name")
            if not model: continue
            sock = mb.get("socket")
            if sock:
                ses.execute_write(ensure_vocab, "Socket", sock)
                ses.execute_write(link, "Motherboard", "model_name", "SUPPORTS_SOCKET", "Socket", "name", model, sock)
            chip = mb.get("chipset")
            if chip:
                ses.execute_write(ensure_vocab, "Chipset", chip)
                ses.execute_write(link, "Motherboard", "model_name", "HAS_CHIPSET", "Chipset", "name", model, chip)
            mtype = mb.get("memory_type")
            if mtype:
                ses.execute_write(ensure_vocab, "MemoryStandard", mtype)
                ses.execute_write(link, "Motherboard", "model_name", "SUPPORTS_MEMORY_TYPE", "MemoryStandard", "name", model, mtype)

        for ram in comps.get("ram", []):
            model = ram.get("model_name")
            if not model: continue
            rtype = ram.get("type") or ram.get("memory_type")
            if rtype:
                ses.execute_write(ensure_vocab, "MemoryStandard", rtype)
                ses.execute_write(link, "MemoryKit", "model_name", "STANDARD", "MemoryStandard", "name", model, rtype)

        for cs in comps.get("case", []):
            model = cs.get("model_name")
            if not model: continue
            sup = cs.get("motherboard_support")
            if sup:
                import re
                vals = re.split(r"[,\s/]+", sup)
                vals = [v for v in vals if v]
                for ff in vals:
                    ses.execute_write(ensure_vocab, "FormFactor", ff)
                    ses.execute_write(link, "Case", "model_name", "SUPPORTS_FORM_FACTOR", "FormFactor", "name", model, ff)

        # 3) Price records (best-effort)
        for label in PART_LABELS:
            for item in comps.get(label.lower(), []):
                model = item.get("model_name")
                if not model: continue
                price = item.get("price")
                fetched_at = item.get("fetched_at")
                src = item.get("source") or args.source
                if price is not None:
                    ses.execute_write(create_price, label, model, float(price), fetched_at, src)
                for pr in item.get("prices", []) or item.get("price_records", []) or []:
                    p = pr.get("price")
                    if p is None: continue
                    ses.execute_write(create_price, label, model, float(p), pr.get("fetched_at"), pr.get("source") or src)

    print("Ingest done.")

if __name__ == "__main__":
    main()
