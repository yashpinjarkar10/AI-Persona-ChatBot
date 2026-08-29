from __future__ import annotations

import argparse
import sys
from app.services.ingestion import sync_knowledge_base


def main():
    """Run CLI knowledge base ingestion from personal_facts.md into Supabase."""
    parser = argparse.ArgumentParser(description="Sync personal_facts.md into Supabase documentation table.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect planned changes without writing to DB or generating embeddings.")
    parser.add_argument("--verbose", action="store_true", help="Print verbose step-by-step progress.")

    args = parser.parse_args()

    print("=== Personal Facts Ingestion Pipeline ===")
    if args.dry_run:
        print("[Mode: DRY-RUN]")

    try:
        stats = sync_knowledge_base(dry_run=args.dry_run, verbose=args.verbose)
        print("\nSync completed successfully:")
        print(f"  Inserted : {stats['inserted']}")
        print(f"  Updated  : {stats['updated']}")
        print(f"  Archived : {stats['archived']}")
        print(f"  Unchanged: {stats['unchanged']}")
    except Exception as e:
        print(f"\n[Error] Sync failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
