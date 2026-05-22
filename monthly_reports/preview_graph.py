import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monthly_reports.generate_visualisation import render_graph, initialise_brand

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 2:
        print("Usage: python monthly_reports/preview_graph.py <client_name>", file=sys.stderr)
        sys.exit(1)

    client_name = sys.argv[1]

    data_path = os.path.join(PROJECT_ROOT, "storage", f"{client_name}_monthly_data.json")
    if not os.path.exists(data_path):
        print(f"ERROR: No cached data found at {data_path}", file=sys.stderr)
        sys.exit(1)

    spec_path = os.path.join(PROJECT_ROOT, "storage", ".preview_spec.json")
    if not os.path.exists(spec_path):
        print(f"ERROR: No spec file found at {spec_path} — write the graph spec there before calling this script", file=sys.stderr)
        sys.exit(1)

    with open(data_path, encoding="utf-8") as f:
        client = json.load(f)

    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    initialise_brand()

    path = render_graph(client, spec)

    if path is None:
        print("ERROR: render_graph returned None — check that all metrics exist in the data and the graph_type is valid", file=sys.stderr)
        sys.exit(1)

    print(path)


if __name__ == "__main__":
    main()
