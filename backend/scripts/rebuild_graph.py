"""
Rebuilds the entire PharmaGraph synchronously from the command line - the
same work as POST /graph/rebuild, but runs inline instead of via a Celery
worker. Useful right after you've bulk-filled composition data (e.g. after
running backfill_composition.py) so substitute/interaction/condition edges
reflect the new data immediately, without needing Redis/Celery running.

For a large catalog this can take a while (SUBSTITUTES edges are an
O(catalog) scan per medicine) - progress is printed as it goes.

Usage:
    cd backend
    python scripts/rebuild_graph.py
"""
import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.services import graph_service


def main():
    db = SessionLocal()
    start = time.time()
    print("Rebuilding PharmaGraph...")
    print("  (this recomputes CONTAINS, SUBSTITUTES, SUPPLIES edges, and reloads the")
    print("   curated INTERACTS_WITH/TREATS seed data - safe to re-run anytime)\n")

    stats = graph_service.rebuild_full_graph(db)
    db.close()

    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s.")
    print(f"  CONTAINS edges (medicines processed):  {stats['contains']}")
    print(f"  SUBSTITUTES edges written:             {stats['substitutes']}")
    print(f"  SUPPLIES edges (confirmed bill items): {stats['supplies']}")
    print(f"  INTERACTS_WITH edges (seed data):      {stats['interactions']}")
    print(f"  TREATS edges (seed data):              {stats['treats']}")


if __name__ == "__main__":
    main()
