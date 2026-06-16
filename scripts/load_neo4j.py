"""
Load the Vezilka RDF knowledge graph into Neo4j (AuraDB).

AuraDB Free does not support the neosemantics (n10s) RDF plugin, so we read
output/vezilka-data.ttl with rdflib and project it into a native property
graph via the Bolt driver:

  - every vez resource (vezr:) becomes a node, labelled by its rdf:type
    (Лексема -> :Lexeme, Дијалект -> :Dialect, ...) plus a shared :Resource
  - literal-valued predicates become node properties (wordForm, frequency, ...)
  - resource-valued predicates become relationships (APPEARS_IN_DIALECT, ...)

Connection details are read from a local .env file (see .env.example):
  NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

Usage:
  pip install -r requirements.txt
  python scripts/load_neo4j.py            # load
  python scripts/load_neo4j.py --wipe     # delete all nodes first, then load
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

DATA_FILE = Path(__file__).resolve().parent.parent / "output" / "vezilka-data.ttl"

VEZ = "http://example.org/vezilka/ontology#"
VEZR = "http://example.org/vezilka/resource/"

# rdf:type local name (Cyrillic) -> clean Neo4j label
CLASS_LABELS = {
    "Наречје": "DialectArea",
    "ДијалектнаГрупа": "DialectGroup",
    "Дијалект": "Dialect",
    "ТекстуаленСегмент": "Segment",
    "Реченица": "Sentence",
    "Лексема": "Lexeme",
    "Фраза": "Phrase",
    "Место": "Place",
    "Лице": "Person",
    "Тема": "Theme",
    "Извор": "Source",
}

BATCH = 5000


def local_name(uri: str) -> str:
    return uri.split("#")[-1].split("/")[-1]


def rel_type(predicate_local: str) -> str:
    """camelCase / lowercase predicate -> UPPER_SNAKE relationship type."""
    s = re.sub(r"(?<=[a-zа-я])(?=[A-ZА-Я])", "_", predicate_local)
    return s.upper()


def build_graph(g: Graph):
    """Return (nodes_by_label, rels_by_type) projected from the RDF graph."""
    nodes: dict[str, dict] = {}          # uri -> {"label": str, "props": {}}
    rels: list[tuple[str, str, str]] = []  # (subj_uri, REL_TYPE, obj_uri)

    def ensure(uri: str) -> dict:
        return nodes.setdefault(uri, {"label": None, "props": {}})

    for s, p, o in g:
        s_str = str(s)
        if not s_str.startswith(VEZR):
            continue  # skip ontology schema (vez:), owl:, skos: definitions

        node = ensure(s_str)
        node["props"]["uri"] = local_name(s_str)

        if p == RDF.type:
            label = CLASS_LABELS.get(local_name(str(o)))
            if label:
                node["label"] = label
            continue

        if isinstance(o, Literal):
            key = local_name(str(p))
            node["props"][key] = o.toPython()
        elif isinstance(o, URIRef) and str(o).startswith(VEZR):
            ensure(str(o))["props"]["uri"] = local_name(str(o))
            rels.append((s_str, rel_type(local_name(str(p))), str(o)))

    # Group nodes by label (default :Resource only, for the rare untyped node)
    nodes_by_label: dict[str, list[dict]] = defaultdict(list)
    for uri, data in nodes.items():
        nodes_by_label[data["label"] or "Resource"].append(data["props"])

    rels_by_type: dict[str, list[dict]] = defaultdict(list)
    for s_uri, rtype, o_uri in rels:
        rels_by_type[rtype].append(
            {"from": local_name(s_uri), "to": local_name(o_uri)}
        )

    return nodes_by_label, rels_by_type


def batched(items, size=BATCH):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def load(driver, nodes_by_label, rels_by_type, wipe=False):
    with driver.session() as session:
        if wipe:
            print("Wiping existing graph...")
            session.run("MATCH (n) CALL { WITH n DETACH DELETE n } IN TRANSACTIONS OF 10000 ROWS")

        print("Creating uniqueness constraint on :Resource(uri)...")
        session.run(
            "CREATE CONSTRAINT resource_uri IF NOT EXISTS "
            "FOR (n:Resource) REQUIRE n.uri IS UNIQUE"
        )

        total_nodes = 0
        for label, rows in nodes_by_label.items():
            cypher = (
                f"UNWIND $rows AS row "
                f"MERGE (n:Resource {{uri: row.uri}}) "
                f"SET n:{label}, n += row"
            )
            for chunk in batched(rows):
                session.run(cypher, rows=chunk)
                total_nodes += len(chunk)
            print(f"  :{label:<13} {len(rows):>6} nodes")
        print(f"Nodes loaded: {total_nodes}")

        total_rels = 0
        for rtype, rows in rels_by_type.items():
            cypher = (
                f"UNWIND $rows AS row "
                f"MATCH (a:Resource {{uri: row.from}}) "
                f"MATCH (b:Resource {{uri: row.to}}) "
                f"MERGE (a)-[:{rtype}]->(b)"
            )
            for chunk in batched(rows):
                session.run(cypher, rows=chunk)
                total_rels += len(chunk)
            print(f"  -[:{rtype}]-> {len(rows):>6}")
        print(f"Relationships loaded: {total_rels}")


def main():
    load_dotenv()
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    if not all((uri, user, password)):
        sys.exit(
            "Missing credentials. Copy .env.example to .env and fill in "
            "NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD."
        )

    if not DATA_FILE.exists():
        sys.exit(f"Data file not found: {DATA_FILE}\nRun scripts/extract_triples.py first.")

    print(f"Parsing {DATA_FILE.name}...")
    g = Graph()
    g.parse(str(DATA_FILE), format="turtle")
    print(f"  {len(g)} triples")

    nodes_by_label, rels_by_type = build_graph(g)

    wipe = "--wipe" in sys.argv
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        print(f"Connected to {uri}\n")
        load(driver, nodes_by_label, rels_by_type, wipe=wipe)
    finally:
        driver.close()
    print("\nDone. Open Neo4j Browser and try:  MATCH (d:Dialect)<-[:APPEARS_IN_DIALECT]-(l:Lexeme) RETURN d, l LIMIT 100")


if __name__ == "__main__":
    main()
