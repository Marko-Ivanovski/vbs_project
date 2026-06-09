"""
Run all SPARQL competency queries against the Vezilka knowledge graph.
"""

import sys
import io
from pathlib import Path

from rdflib import Graph

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_FILE = Path(__file__).resolve().parent.parent / "output" / "vezilka-data.ttl"
QUERIES_DIR = Path(__file__).resolve().parent


def run_all():
    print("Loading knowledge graph...")
    g = Graph()
    g.parse(str(DATA_FILE), format="turtle")
    print(f"  Loaded {len(g)} triples\n")

    query_files = sorted(QUERIES_DIR.glob("q*.rq"))
    for qf in query_files:
        print(f"{'=' * 60}")
        header_lines = []
        query_text = qf.read_text(encoding="utf-8")
        for line in query_text.splitlines():
            if line.startswith("#"):
                header_lines.append(line.lstrip("# "))
            else:
                break
        print(f"  {qf.name}: {header_lines[0] if header_lines else ''}")
        if len(header_lines) > 1:
            print(f"  {header_lines[1]}")
        print()

        try:
            results = g.query(query_text)
            if results.vars:
                col_names = [str(v) for v in results.vars]
                print("  " + " | ".join(f"{c:<25}" for c in col_names))
                print("  " + "-" * (27 * len(col_names)))
                row_count = 0
                for row in results:
                    values = [str(v) if v is not None else "" for v in row]
                    print("  " + " | ".join(f"{v:<25}" for v in values))
                    row_count += 1
                print(f"\n  ({row_count} rows)")
            else:
                print("  (no results)")
        except Exception as e:
            print(f"  ERROR: {e}")
        print()


if __name__ == "__main__":
    run_all()
