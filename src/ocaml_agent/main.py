#!/usr/bin/env python3
import sys
from . import collect
from . import llm_score
from . import notify


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m ocaml_agent.main <command>")
        print("Commands:")
        print("  collect  - Run all collectors")
        print("  score    - Run LLM scoring pipeline")
        print("  notify   - Send Telegram notification")
        sys.exit(1)

    command = sys.argv[1]

    if command == "collect":
        collect.main()
    elif command == "score":
        llm_score.main()
    elif command == "notify":
        notify.main()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
