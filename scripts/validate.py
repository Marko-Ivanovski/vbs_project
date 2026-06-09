"""
Validate the Vezilka knowledge graph against SHACL shapes.
"""

from pathlib import Path

from pyshacl import validate
from rdflib import Graph

BASE = Path(__file__).resolve().parent.parent
DATA_FILE = BASE / "output" / "vezilka-data.ttl"
SHAPES_FILE = BASE / "ontology" / "vezilka-shapes.ttl"


def run_validation():
    print("Loading data graph...")
    data_graph = Graph()
    data_graph.parse(str(DATA_FILE), format="turtle")
    print(f"  {len(data_graph)} triples")

    print("Loading shapes graph...")
    shapes_graph = Graph()
    shapes_graph.parse(str(SHAPES_FILE), format="turtle")
    print(f"  {len(shapes_graph)} triples")

    print("\nValidating...")
    conforms, results_graph, results_text = validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="none",
        abort_on_first=False,
    )

    if conforms:
        print("\n  CONFORMS: All shapes pass.")
    else:
        print(f"\n  VIOLATIONS FOUND:")
        print(results_text[:5000])

    report_file = BASE / "output" / "validation-report.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"Conforms: {conforms}\n\n")
        f.write(results_text)
    print(f"\nFull report: {report_file}")

    return conforms


if __name__ == "__main__":
    run_validation()
