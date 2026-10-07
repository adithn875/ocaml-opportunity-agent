import sqlite3
import traceback

from . import collector
from . import discuss_collector
from . import hnhiring_collector
from . import jane_street_collector
from . import ocamlpro_collector
from . import inria_collector
from . import tezos_collector
from . import trustinsoft_collector
from . import framac_collector


DB_PATH = "data/agent.db"


def database_count():
    con = sqlite3.connect(DB_PATH)
    count = con.execute(
        "SELECT COUNT(*) FROM seen_items"
    ).fetchone()[0]
    con.close()
    return count


def record_run(sources_ok, sources_failed, new_items, notes):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        INSERT INTO runs (
            sources_ok,
            sources_failed,
            new_items,
            notes
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            sources_ok,
            sources_failed,
            new_items,
            notes,
        ),
    )
    con.commit()
    con.close()


def run_collector(name, function):
    print("\n" + "=" * 60)
    print(f"RUNNING: {name}")
    print("=" * 60)

    before = database_count()

    try:
        function()
        after = database_count()

        print(f"\n{name}: {after - before} new records")
        return True

    except Exception:
        print(f"\n{name}: FAILED")
        traceback.print_exc()
        return False


def main():
    print("Starting OCaml Opportunity Agent collection...")
    initial_count = database_count()
    print(f"Initial database records: {initial_count}")

    collectors = [
        ("OCaml.org", collector.main),
        ("OCaml Discuss", discuss_collector.main),
        ("HN Who's Hiring", hnhiring_collector.main),
        ("Jane Street", lambda: jane_street_collector.save_jobs(
            jane_street_collector.collect_ocaml_jobs()
        )),
        ("OCamlPro", lambda: ocamlpro_collector.save_jobs(
            ocamlpro_collector.collect_all()
        )),
        ("Inria", lambda: inria_collector.save_jobs(
            inria_collector.collect_offers()
        )),
        ("Tezos", lambda: tezos_collector.save_jobs(
            tezos_collector.fetch_tezos_jobs()
        )),
        ("TrustInSoft", lambda: trustinsoft_collector.save_jobs(
            trustinsoft_collector.collect_opportunities()
        )),
        ("Frama-C", lambda: framac_collector.save_jobs(
            framac_collector.collect_opportunities()
        )),
    ]

    results = []

    for name, function in collectors:
        success = run_collector(name, function)
        results.append((name, success))

    sources_ok = sum(1 for _, success in results if success)
    sources_failed = sum(1 for _, success in results if not success)

    final_count = database_count()
    new_items = final_count - initial_count

    record_run(
        sources_ok=sources_ok,
        sources_failed=sources_failed,
        new_items=new_items,
        notes="Unified collection run",
    )

    print("\n" + "=" * 60)
    print("COLLECTION SUMMARY")
    print("=" * 60)

    for name, success in results:
        status = "OK" if success else "FAILED"
        print(f"{name:<20} {status}")

    print(f"\nFINAL DATABASE RECORDS: {database_count()}")


if __name__ == "__main__":
    main()
