
"""Python adapter for the OCaml candidate eligibility evaluator."""

import json
import math
import subprocess
from pathlib import Path
from typing import Any, Mapping


OCAML_EVALUATOR = (
    Path(__file__).resolve().parents[2]
    / "ocaml-scoring"
    / "ocaml_scoring"
    / "_build"
    / "default"
    / "bin"
    / "main.exe"
)


def evaluate_candidate(job: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one job using OCaml and return its JSON decision."""

    title = job.get("title")
    if title is None:
        title = ""
    elif not isinstance(title, str):
        raise ValueError("candidate title must be a string or null")

    description = job.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError("candidate description must be a string or null")

    source = job.get("source")
    if source is not None and not isinstance(source, str):
        raise ValueError("candidate source must be a string or null")

    raw_score = job.get("score", 0)
    if raw_score is None:
        score = 0.0
    elif isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
        raise ValueError("candidate score must be a finite number or null")
    else:
        try:
            score = float(raw_score)
        except OverflowError as exc:
            raise ValueError("candidate score must be a finite number or null") from exc
        if not math.isfinite(score):
            raise ValueError("candidate score must be a finite number or null")

    payload = {
        "title": title,
        "score": score,
        "description": description,
        "source": source,
    }

    try:
        result = subprocess.run(
            [str(OCAML_EVALUATOR), "--evaluate-candidate"],
            input=json.dumps(payload) + "\n",
            text=True,
            capture_output=True,
            check=True,
        )
        decision = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"OCaml candidate evaluator failed or returned invalid JSON: {exc}"
        ) from exc

    if not isinstance(decision, dict):
        raise RuntimeError("OCaml evaluator returned a non-object JSON value")

    if not isinstance(decision.get("accepted"), bool):
        raise RuntimeError("OCaml evaluator returned an invalid 'accepted' value")

    if not isinstance(decision.get("reason"), str):
        raise RuntimeError("OCaml evaluator returned an invalid 'reason' value")

    signals = decision.get("title_signals")
    if not isinstance(signals, list) or not all(
        isinstance(signal, str) for signal in signals
    ):
        raise RuntimeError("OCaml evaluator returned invalid 'title_signals'")

    return decision
