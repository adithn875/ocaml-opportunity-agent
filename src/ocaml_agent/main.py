#!/usr/bin/env python3
import sys

from . import collect
from . import llm_score
from . import notify
from . import ranking
from . import score_jobs


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m ocaml_agent.main <command>")
        print("Commands:")
        print("  collect            - Run all collectors")
        print("  deterministic-score - Score records missing deterministic scores")
        print("  score              - Run LLM scoring pipeline")
        print("  rank               - Preview missing final scores")
        print("  notify             - Send Telegram notification")
        sys.exit(1)

    command = sys.argv[1]

    if command == "collect":
        collect.main()
    elif command == "deterministic-score":
        score_jobs.main()
    elif command == "score":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        llm_score.main()
    elif command == "rank":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        ranking.main()
    elif command == "notify":
        notify.main()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
