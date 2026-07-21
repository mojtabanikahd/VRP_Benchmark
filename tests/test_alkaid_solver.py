"""Contract tests for the external Alkaid-SDVRP adapter."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from vrpbench.core import evaluate
from vrpbench.core.instance import SDVRP, Instance
from vrpbench.datasets import loader
from vrpbench.solvers.alkaid_solver import AlkaidSDVRPSolver
from vrpbench.solvers.base import SolverError


SD1 = Path("data/instances/SDVRP_R1_instances/SET-1/SD1.txt")


def _toy(source_path: Path) -> Instance:
    source_path.write_text(
        "3 20\n5 8 15\n0 0\n1 0\n2 0\n3 0\n",
        encoding="utf-8",
    )
    coords = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    diff = coords[:, None, :] - coords[None, :, :]
    return Instance(
        name="toy-sdvrp",
        variant=SDVRP,
        num_nodes=4,
        coords=coords,
        demands=np.array([0, 5, 8, 15]),
        capacity=20,
        distance=np.floor(np.sqrt((diff**2).sum(axis=-1)) + 0.5),
        source_path=str(source_path),
    )


def _fake_script(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_alkaid.py"
    script.write_text(body, encoding="utf-8")
    return script


def test_alkaid_passes_original_instance_and_decodes_json(tmp_path, monkeypatch):
    original_path = tmp_path / "original instance.sd"
    instance = _toy(original_path)
    record = tmp_path / "record.json"
    monkeypatch.setenv("ALKAID_FAKE_RECORD", str(record))
    script = _fake_script(
        tmp_path,
        """
import json, os, sys
from pathlib import Path
config_path = Path(sys.argv[sys.argv.index('--config') + 1])
values = {}
for line in config_path.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
Path(os.environ['ALKAID_FAKE_RECORD']).write_text(json.dumps(values), encoding='utf-8')
routes = [
    [{'customer': 0, 'quantity': 0}, {'customer': 2, 'quantity': 8},
     {'customer': 3, 'quantity': 12}, {'customer': 0, 'quantity': 0}],
    [{'customer': 0, 'quantity': 0}, {'customer': 1, 'quantity': 5},
     {'customer': 3, 'quantity': 3}, {'customer': 0, 'quantity': 0}],
]
Path(values['output'].strip('"')).write_text(json.dumps(routes), encoding='utf-8')
""",
    )

    solution = AlkaidSDVRPSolver([sys.executable, str(script)]).solve(
        instance, time_budget_s=2.5, seed=19
    )

    observed = json.loads(record.read_text(encoding="utf-8"))
    assert Path(observed["input"].strip('"')).resolve() == original_path.resolve()
    assert observed["random-seed"] == "19"
    assert float(observed["time-limit"]) == pytest.approx(2.5)
    assert observed["inter-operators"] == (
        '["Relocate", "Swap<2, 0>", "Swap<2, 1>", "Swap<2, 2>", '
        '"Cross", "SwapStar", "SdSwapStar"]'
    )
    assert observed["intra-operators"] == '["Exchange", "OrOpt<1>"]'
    assert observed["acceptance-rule-type"] == '"LAHC"'
    assert observed["acceptance-rule-args"] == '["length=83"]'
    assert observed["ruin-method-type"] == '"SISRs"'
    assert observed["ruin-method-args"] == (
        '["average_customers=36", "max_length=8", "split_rate=0.740", '
        '"preserved_probability=0.096"]'
    )
    assert observed["sorters"] == (
        '["random=0.078", "demand=0.225", "far=0.942", "close=0.120"]'
    )
    assert solution.routes == [[2, 3], [1, 3]]
    assert solution.route_deliveries == [{2: 8, 3: 12}, {1: 5, 3: 3}]
    evaluation = evaluate.verify(instance, solution)
    assert evaluation.feasible, evaluation.violations
    assert evaluation.obj_mismatch == pytest.approx(0.0)


def test_alkaid_requires_executable_and_original_source(tmp_path, monkeypatch):
    monkeypatch.delenv("ALKAID_SDVRP_EXECUTABLE", raising=False)
    instance = _toy(tmp_path / "input.sd")
    with pytest.raises(SolverError, match="ALKAID_SDVRP_EXECUTABLE"):
        AlkaidSDVRPSolver().solve(instance, time_budget_s=1, seed=0)

    without_source = Instance(
        **{**instance.__dict__, "source_path": None}
    )
    with pytest.raises(SolverError, match="source_path"):
        AlkaidSDVRPSolver([sys.executable]).solve(without_source, time_budget_s=1, seed=0)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("import sys; sys.stderr.write('boom'); raise SystemExit(7)", "exit code 7"),
        ("import sys", "did not create"),
    ],
)
def test_alkaid_reports_process_and_output_failures(tmp_path, body, message):
    instance = _toy(tmp_path / "input.sd")
    script = _fake_script(tmp_path, body)
    with pytest.raises(SolverError, match=message):
        AlkaidSDVRPSolver([sys.executable, str(script)]).solve(
            instance, time_budget_s=1, seed=0
        )


def test_alkaid_accepts_official_trailing_comma_output(tmp_path):
    instance = _toy(tmp_path / "input.sd")
    script = _fake_script(
        tmp_path,
        """
import sys
from pathlib import Path
cfg = Path(sys.argv[sys.argv.index('--config') + 1])
values = {}
for line in cfg.read_text().splitlines():
    if '=' in line:
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"')
Path(values['output']).write_text(
    '[[{"customer": 0, "quantity": 0}, {"customer": 1, "quantity": 5},'
    ' {"customer": 3, "quantity": 15}, {"customer": 0, "quantity": 0}],'
    '[{"customer": 0, "quantity": 0}, {"customer": 2, "quantity": 8},'
    ' {"customer": 0, "quantity": 0}],]',
    encoding='utf-8',
)
""",
    )

    solution = AlkaidSDVRPSolver([sys.executable, str(script)]).solve(
        instance, time_budget_s=1, seed=0
    )

    assert solution.routes == [[1, 3], [2]]
    assert solution.route_deliveries == [{1: 5, 3: 15}, {2: 8}]


def test_alkaid_rejects_malformed_or_invalid_json(tmp_path):
    instance = _toy(tmp_path / "input.sd")
    for payload, message in [
        ("not-json", "malformed JSON"),
        (json.dumps([[{"customer": 9, "quantity": 5}]]), "invalid customer"),
        (json.dumps([[{"customer": 1, "quantity": 0}]]), "positive integer"),
    ]:
        script = _fake_script(
            tmp_path,
            f"""
import sys
from pathlib import Path
cfg = Path(sys.argv[sys.argv.index('--config') + 1])
values = {{}}
for line in cfg.read_text().splitlines():
    if '=' in line:
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"')
Path(values['output']).write_text({payload!r}, encoding='utf-8')
""",
        )
        with pytest.raises(SolverError, match=message):
            AlkaidSDVRPSolver([sys.executable, str(script)]).solve(
                instance, time_budget_s=1, seed=0
            )


@pytest.mark.skipif(
    not os.environ.get("ALKAID_SDVRP_EXECUTABLE") or not SD1.exists(),
    reason="official Alkaid executable or SD1 is not available",
)
def test_official_alkaid_solves_sd1():
    instance = loader.load(SD1, variant=SDVRP)
    solution = AlkaidSDVRPSolver().solve(instance, time_budget_s=10, seed=0)
    evaluation = evaluate.verify(instance, solution)
    assert evaluation.feasible, evaluation.violations
    assert evaluation.obj_mismatch == pytest.approx(0.0)
    appearances = {
        customer: sum(customer in delivered for delivered in solution.route_deliveries)
        for customer in instance.customers
    }
    assert max(appearances.values()) >= 2
