"""The repository's own CI claims, checked by the repository's own suite.

**Why this file exists.** Until now nothing in ``tests/`` read ``ruff.toml``, the carried-findings
register or the workflow. The register guard in CI was the *only* thing asserting that an ignored
lint rule carries a row, and a guard whose own neutralisation passes the whole suite is one step
away from not existing. The measured evidence for that: replacing the guard's ``if missing:`` with
``if False:`` left every test green, and so did deleting a job's ``timeout-minutes``.

**The mirror rule.** This file **derives** the ignored rule set from ``ruff.toml`` and the rows from
the register, and asserts the guard agrees with that derivation. It must not simply run the guard:
if the guard were the only source of truth, neutralising the guard would make this file pass
alongside it. Two independent derivations that must agree is the point, and a divergence fails here.

**What is deliberately NOT asserted: full YAML grammar.** No YAML library is a declared dependency
of this project (the project environment has none), and GitHub parses the workflow before any job
runs, so the authoritative YAML validator is the platform. What is asserted here is the structure
this repository depends on, read without a parser nobody declared.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tomllib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RUFF_CONFIG = REPO_ROOT / "ruff.toml"
REGISTER = REPO_ROOT / "docs" / "CARRIED-FINDINGS.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: The guard is one heredoc block in the workflow. It is located by this marker rather than by a
#: YAML parse, because no YAML library is a declared dependency (see the module docstring).
_HEREDOC_OPEN = "python3 - <<'PY'"
_HEREDOC_CLOSE = "PY"
_GUARD_TIMEOUT_SECONDS = 30


def _lint_table() -> dict[str, object]:
    """The ``[lint]`` table of the committed Ruff configuration."""
    return tomllib.loads(RUFF_CONFIG.read_text())["lint"]


def ignored_rules() -> set[str]:
    """Every lint rule this repository silences, global or per-file.

    This is the derivation the mirror compares the guard against; it reads the configuration
    rather than the guard, so a change to either one alone fails the other's test.
    """
    lint = _lint_table()
    codes = set(lint.get("ignore", []))
    for rules in lint.get("per-file-ignores", {}).values():
        codes.update(rules)
    return codes


def guard_script() -> str:
    """The guard's own text, extracted from the workflow's heredoc block.

    Deliberately dumb: it takes the lines between the marker and its terminator, dedented by the
    marker's indentation. Anything cleverer would be a second YAML parser to keep correct.
    """
    lines = WORKFLOW.read_text().splitlines()
    openings = [index for index, line in enumerate(lines) if line.strip() == _HEREDOC_OPEN]
    assert len(openings) == 1, f"expected exactly one guard heredoc, found {len(openings)}"
    start = openings[0]
    indent = len(lines[start]) - len(lines[start].lstrip())
    for end in range(start + 1, len(lines)):
        if lines[end].strip() == _HEREDOC_CLOSE:
            break
    else:  # pragma: no cover - a missing terminator is a broken workflow, not a test case
        raise AssertionError("the guard heredoc is not terminated")
    body = [lines[index][indent:] if lines[index].strip() else "" for index in range(start + 1, end)]
    return "\n".join(body) + "\n"


def run_guard(directory: pathlib.Path, script: str) -> subprocess.CompletedProcess[str]:
    """Run the guard with ``directory`` as its working directory.

    The guard reads ``ruff.toml`` and ``docs/CARRIED-FINDINGS.md`` from the current directory, so a
    temporary directory is all a sandbox needs. It runs under this interpreter, which is the same
    Python the suite runs on and therefore also has ``tomllib``.
    """
    # noqa: S603 -- both the interpreter and the script are this repository's own, the argument
    # list is fixed here, and no value reaches it from outside the repository. This is the in-site
    # exception the committed Ruff configuration documents for a security rule firing on new code.
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=_GUARD_TIMEOUT_SECONDS,
        check=False,
    )


def write_sandbox(
    directory: pathlib.Path,
    *,
    ignore: list[str] | None,
    register: str,
    config_text: str | None = None,
) -> None:
    """Write a minimal tree the guard can read: a Ruff config and a register."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "docs").mkdir(parents=True, exist_ok=True)
    (directory / "docs" / "CARRIED-FINDINGS.md").write_text(register)
    (directory / "ruff.toml").write_text(config_text if config_text is not None else _config_with(ignore))


def _config_with(ignore: list[str] | None) -> str:
    codes = "\n".join(f'    "{code}",' for code in (ignore or []))
    return (
        "line-length = 88\n\n[lint]\nselect = [\"E\", \"F\"]\nignore = [\n"
        + codes
        + "\n]\n\n[lint.per-file-ignores]\n\"tests/**\" = [\"S101\"]\n"
    )


def job_keys() -> list[str]:
    """The job names declared under ``jobs:``.

    Read by indentation rather than by a YAML parse, for the reason in the module docstring. The
    section is sliced first because the trigger block under ``on:`` is indented the same way and a
    scan over the whole file would read ``push:`` as a job.
    """
    _, _, jobs_section = WORKFLOW.read_text().partition("\njobs:\n")
    assert jobs_section, "the workflow declares no jobs: section"
    return re.findall(r"(?m)^  ([a-z][a-z0-9-]*):", jobs_section)


def jobs_without_timeout() -> list[str]:
    """Every job in the workflow that does not declare ``timeout-minutes``."""
    _, _, jobs_section = WORKFLOW.read_text().partition("\njobs:\n")
    lines = jobs_section.splitlines()
    starts = [index for index, line in enumerate(lines) if re.fullmatch(r"  [a-z][a-z0-9-]*:", line)]
    missing = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = lines[start:end]
        if not any(line.startswith("    timeout-minutes:") for line in block):
            missing.append(lines[start].strip().rstrip(":"))
    return missing


# --- the mirror: the configuration, the register, and the guard must agree ---------------------------------
def test_every_ignored_rule_is_named_in_the_register() -> None:
    """The property the guard exists for, derived here from the configuration and the register.

    Asserted independently of the guard on purpose: a guard whose own removal passes this suite
    would be one step away from not existing.
    """
    codes = ignored_rules()
    assert codes, "no ignored rules were read; a mirror over an empty set would pass vacuously"
    register = REGISTER.read_text()
    missing = sorted(code for code in codes if code not in register)
    assert not missing, f"ignored lint rules with no row in the register: {missing}"


def test_the_lint_table_declares_an_ignore_key() -> None:
    """A missing ``[lint].ignore`` must fail loudly here, not silently narrow the guard.

    Measured defect this pins: deleting only the ``[lint]`` header while keeping
    ``[lint.per-file-ignores]`` left the guard green while it checked three rules instead of five,
    because the sub-table still creates the ``lint`` table and a defaulted empty list looked like
    an honest empty set.
    """
    assert "ignore" in _lint_table(), "ruff.toml must declare [lint].ignore explicitly"


# --- the guard itself: executed, in a sandbox, in both directions -------------------------------------------
def test_the_guard_passes_on_this_repository() -> None:
    """The guard, run against the real tree, exits 0 and reports every ignored rule it checked."""
    script = guard_script()
    result = run_guard(REPO_ROOT, script)
    assert result.returncode == 0, f"guard failed on this repository: {result.stdout}{result.stderr}"
    codes = sorted(ignored_rules())
    assert f"all {len(codes)} ignored rules have a row" in result.stdout
    assert all(code in result.stdout for code in codes)


def test_the_guard_fails_when_an_ignored_rule_has_no_row(tmp_path: pathlib.Path) -> None:
    """The failure direction, which is the only thing that makes the guard a check.

    This is the test that makes the guard's own neutralisation visible: with the failure branch
    removed (``if missing:`` -> ``if False:``) the guard exits 0 here and this test fails.
    """
    write_sandbox(tmp_path, ignore=["E501", "B904"], register="| `E501` | a carried finding |\n")
    result = run_guard(tmp_path, guard_script())
    assert result.returncode != 0, "the guard accepted an ignored rule with no row"
    assert "B904" in result.stdout + result.stderr
    # A readable refusal, not a traceback: the assignment this unit answers asked for the failure
    # to name the rule, and a KeyError that happens to exit non-zero would not.
    assert "register guard:" in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_the_guard_refuses_a_config_without_an_ignore_key(tmp_path: pathlib.Path) -> None:
    """The two-line fix, pinned by behaviour: no ``[lint].ignore`` means the guard must refuse.

    Without this refusal the guard checks only the per-file rules and reports success, which is the
    false green measured before this unit.
    """
    write_sandbox(
        tmp_path,
        ignore=None,
        register="| `S101` | a carried finding |\n",
        config_text='line-length = 88\n\n[lint]\nselect = ["E", "F"]\n\n[lint.per-file-ignores]\n"tests/**" = ["S101"]\n',
    )
    result = run_guard(tmp_path, guard_script())
    assert result.returncode != 0, "the guard accepted a configuration with no [lint].ignore"
    assert "ignore" in result.stdout + result.stderr
    # The two-line fix must refuse in its own words: without the explicit check this sandbox
    # fails through a KeyError instead, which is a non-zero exit for the wrong reason.
    assert "register guard:" in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_the_guard_refuses_a_missing_register(tmp_path: pathlib.Path) -> None:
    """A register that does not exist is a failure, never an empty one."""
    (tmp_path / "ruff.toml").write_text(_config_with(["E501"]))
    result = run_guard(tmp_path, guard_script())
    assert result.returncode != 0, "the guard accepted a missing register"
    assert "register guard:" in result.stdout + result.stderr


# --- the workflow's own structure, in the part that does not need GitHub ------------------------------------
def test_every_ci_job_declares_a_timeout() -> None:
    """Every job carries an explicit ``timeout-minutes``.

    Measured defect this pins: deleting one job's ``timeout-minutes`` used to pass the whole suite,
    while GitHub's implicit default is 360 minutes a job, so a hung step is invisible in a green
    badge. This asserts the declaration, never the runner's behaviour.
    """
    missing = jobs_without_timeout()
    assert not missing, f"CI jobs with no timeout-minutes: {missing}"


def test_the_workflow_declares_at_least_one_job() -> None:
    """Guard against the structural scan above passing over an empty or unparsed workflow."""
    assert job_keys(), "no CI jobs were found; the structural scan would pass vacuously"


def test_the_guard_heredoc_is_locatable_exactly_once() -> None:
    """The locator the other guard tests depend on finds exactly one block, so they cannot pass
    while testing nothing."""
    script = guard_script()
    assert "tomllib" in script and "CARRIED-FINDINGS" in script


def test_no_ignored_rule_is_duplicated_or_blank() -> None:
    """A duplicated or blank entry would make the configuration unreadable as a set."""
    raw = list(_lint_table().get("ignore", []))
    assert raw, "the global ignore list is empty; per-file silences would be the only ones read"
    assert all(code.strip() == code and code for code in raw)
    assert len(set(raw)) == len(raw)
