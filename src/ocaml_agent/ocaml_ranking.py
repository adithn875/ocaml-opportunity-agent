"""Python adapter for the OCaml final-ranking formula."""

import json
import math
import subprocess
from pathlib import Path
from typing import Any


OCAML_RANKING = (
    Path(__file__).resolve().parents[2]
    / "ocaml-scoring"
    / "ocaml_scoring"
    / "_build"
    / "default"
    / "bin"
    / "main.exe"
)


def _validated_score(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be between 0 and 100")

    try:
        score = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be between 0 and 100") from exc

    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return score


def calculate_final_score(*, technical_score: Any, practicality_score: Any) -> float:
    """Calculate one validated final score through the OCaml evaluator."""

    payload = {
        "technical_score": _validated_score("technical_score", technical_score),
        "practicality_score": _validated_score(
            "practicality_score", practicality_score
        ),
    }

    try:
        result = subprocess.run(
            [str(OCAML_RANKING), "--calculate-final-score"],
            input=json.dumps(payload) + "\n",
            text=True,
            capture_output=True,
            check=True,
        )
        response = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"OCaml final-ranking evaluator failed or returned invalid JSON: {exc}"
        ) from exc

    if not isinstance(response, dict):
        raise RuntimeError("OCaml final-ranking evaluator returned a non-object JSON value")

    final_score = response.get("final_score")
    if isinstance(final_score, bool) or not isinstance(final_score, (int, float)):
        raise RuntimeError(
            "OCaml final-ranking evaluator returned an invalid 'final_score' value"
        )

    final_score = float(final_score)
    if not math.isfinite(final_score) or not 0 <= final_score <= 100:
        raise RuntimeError(
            "OCaml final-ranking evaluator returned an out-of-range 'final_score'"
        )
    return final_score
