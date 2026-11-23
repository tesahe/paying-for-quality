"""SummEval reader (Fabbri et al., 2021): expert and crowd ratings of news summaries.

The file is the public `model_annotations.aligned.jsonl` from the Yale-LILY/SummEval repository,
kept under data/raw/ (git-ignored; not redistributed here). Each line is one summary with
`expert_annotations` (3 raters) and `turker_annotations` (5 raters), each a list of objects that
score four dimensions on a 1-5 scale. Only those scores are read; no text is loaded.

Scores are untrusted input: each one goes through Core `score_in_scale`, and a score that fails
becomes a missing rating and is counted, never guessed.
"""

from __future__ import annotations

import json
from pathlib import Path

from ...core.agreement import RatingData, score_in_scale
from ...core.errors import ConfigError

DIMENSIONS = ("coherence", "consistency", "fluency", "relevance")
GROUPS = {"expert": "expert_annotations", "crowd": "turker_annotations"}
SCALE = (1, 5)
DATASET = "SummEval"
LICENSE = "MIT (Yale-LILY/SummEval repository LICENSE; confirm when downloading)"
DOWNLOAD_HINT = (
    "download model_annotations.aligned.jsonl as described in the Yale-LILY/SummEval README and "
    "save it under data/raw/summeval/ (git-ignored)"
)



def parse_lines(lines) -> RatingData:
    data = RatingData(DATASET, DIMENSIONS, tuple(GROUPS), tables={(d, g): [] for d in DIMENSIONS for g in GROUPS})
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            raise ConfigError(f"SummEval file line {number} is not valid JSON") from None
        if not isinstance(record, dict):
            raise ConfigError(f"SummEval file line {number} is not a JSON object")
        data.units += 1
        for group, key in GROUPS.items():
            annotations = record.get(key)
            if not isinstance(annotations, list):
                raise ConfigError(f"SummEval file line {number} has no '{key}' list")
            for dimension in DIMENSIONS:
                row: list[float | None] = []
                for annotation in annotations:
                    value = annotation.get(dimension) if isinstance(annotation, dict) else None
                    if score_in_scale(value, *SCALE):
                        row.append(float(value))
                    else:
                        row.append(None)
                        data.rejected_scores += 1
                data.tables[(dimension, group)].append(row)
    return data


def load_summeval(path: str | Path) -> RatingData:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"SummEval file not found at {path}; {DOWNLOAD_HINT}")
    with path.open(encoding="utf-8") as handle:
        return parse_lines(handle)
