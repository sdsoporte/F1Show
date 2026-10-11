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
The comparison itself is a function of two texts, so its **failure** direction is exercised on
planted texts rather than only on this repository, where it succeeds.

**The job-key charset.** The two structural scans read job keys **permissively** and a separate
test rejects a key outside GitHub's charset, because a scan that accepts only well-formed keys
hides a malformed one from the timeout check: a job declared as ``register_check:`` with no
``timeout-minutes`` matched neither scan and left every test green.

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

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RUFF_CONFIG = REPO_ROOT / "ruff.toml"
REGISTER = REPO_ROOT / "docs" / "CARRIED-FINDINGS.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: The guard is one heredoc block in the workflow. It is located by this marker rather than by a
#: YAML parse, because no YAML library is a declared dependency (see the module docstring).
_HEREDOC_OPEN = "python3 - <<'PY'"
_HEREDOC_CLOSE = "PY"
_GUARD_TIMEOUT_SECONDS = 30

#: GitHub's own charset for a job key. The scans below read the workflow without a YAML parser, so
#: a key outside this charset has to fail loudly here instead of being skipped in silence.
_GITHUB_JOB_KEY = re.compile(r"[a-z][a-z0-9-]*\Z")

#: A job key line: exactly two spaces of indentation inside the ``jobs:`` section. Deliberately
#: permissive about the key itself, so a malformed key is *seen* by both scans and rejected by
#: ``test_every_job_key_uses_the_github_charset`` rather than disappearing from both of them.
_JOB_KEY_LINE = re.compile(r"(?m)^  ([^\s#][^:]*):")


def _lint_table() -> dict[str, object]:
    """The ``[lint]`` table of the committed Ruff configuration."""
    return tomllib.loads(RUFF_CONFIG.read_text())["lint"]


def ignored_rules_from(config_text: str) -> set[str]:
    """Every lint rule a given Ruff configuration silences, global or per-file."""
    lint = tomllib.loads(config_text)["lint"]
    codes = set(lint.get("ignore", []))
    for rules in lint.get("per-file-ignores", {}).values():
        codes.update(rules)
    return codes


def ignored_rules() -> set[str]:
    """Every lint rule this repository silences, global or per-file.

    This is the derivation the mirror compares the guard against; it reads the configuration
    rather than the guard, so a change to either one alone fails the other's test.
    """
    return ignored_rules_from(RUFF_CONFIG.read_text())


def missing_register_rows(config_text: str, register_text: str) -> list[str]:
    """Ignored rules in ``config_text`` with no row anywhere in ``register_text``.

    A function of two texts rather than of the two repository paths, so its failure direction can
    be exercised: only the real tree, where the comparison succeeds, was ever run against it.
    """
    return sorted(code for code in ignored_rules_from(config_text) if code not in register_text)


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


def write_sandbox(directory: pathlib.Path, *, register: str, config_text: str) -> None:
    """Write a minimal tree the guard can read: a Ruff config and a register.

    ``config_text`` is the only way to say what the sandbox's configuration is: an earlier
    signature also took an ``ignore`` list and ignored it whenever ``config_text`` was passed, so a
    caller could pass both and have one of them silently discarded. Callers build the text with
    :func:`_config_with`.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "docs").mkdir(parents=True, exist_ok=True)
    (directory / "docs" / "CARRIED-FINDINGS.md").write_text(register)
    (directory / "ruff.toml").write_text(config_text)


def _config_with(ignore: list[str] | None) -> str:
    codes = "\n".join(f'    "{code}",' for code in (ignore or []))
    return (
        "line-length = 88\n\n[lint]\nselect = [\"E\", \"F\"]\nignore = [\n"
        + codes
        + "\n]\n\n[lint.per-file-ignores]\n\"tests/**\" = [\"S101\"]\n"
    )


def _workflow_with_extra_job(key: str, timeout: int | None = None) -> str:
    """This repository's workflow plus a job declared with ``key``."""
    declared = "" if timeout is None else f"    timeout-minutes: {timeout}\n"
    job = (
        f"  {key}:\n"
        "    name: a planted job\n"
        "    runs-on: ubuntu-latest\n" + declared + "    steps:\n"
        "      - name: noop\n"
        "        run: echo noop\n\n"
    )
    return WORKFLOW.read_text().replace("\njobs:\n", "\njobs:\n" + job, 1)


def _jobs_section(workflow_text: str) -> str:
    """The text under ``jobs:``, to the end of the file.

    Sliced before scanning because the trigger block under ``on:`` is indented the same way and a
    scan over the whole file would read ``push:`` as a job. Slice once, in one place: both scans
    need it, and while the slice lived in two copies so did responsibility for noticing its absence
    from one of them.
    """
    _, _, jobs_section = workflow_text.partition("\njobs:\n")
    assert jobs_section, "the workflow declares no jobs: section"
    return jobs_section


def _job_key_starts(lines: list[str]) -> list[tuple[int, str]]:
    """``(line index, key)`` for every job key line in ``lines``."""
    starts = []
    for index, line in enumerate(lines):
        match = _JOB_KEY_LINE.fullmatch(line)
        if match is not None:
            starts.append((index, match.group(1)))
    return starts


def job_keys(workflow_text: str | None = None) -> list[str]:
    """The job names declared under ``jobs:``, read permissively rather than by charset.

    Read by indentation rather than by a YAML parse, for the reason in the module docstring. The
    key itself is not filtered to GitHub's charset: a filter there hides a malformed key from this
    scan *and* from :func:`jobs_without_timeout`, and
    ``test_every_job_key_uses_the_github_charset`` rejects it instead. ``workflow_text`` exists so a
    test can plant a workflow rather than edit this repository's own.
    """
    text = WORKFLOW.read_text() if workflow_text is None else workflow_text
    return [key for _, key in _job_key_starts(_jobs_section(text).splitlines())]


def jobs_without_timeout(workflow_text: str | None = None) -> list[str]:
    """Every job that does not declare ``timeout-minutes``, keys read as in :func:`job_keys`.

    The shared key rule is the point: a job key outside GitHub's charset used to match neither
    scan, so a job carrying no timeout passed this check in silence.
    """
    text = WORKFLOW.read_text() if workflow_text is None else workflow_text
    lines = _jobs_section(text).splitlines()
    starts = _job_key_starts(lines)
    missing = []
    for position, (start, key) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        if not any(line.startswith("    timeout-minutes:") for line in lines[start:end]):
            missing.append(key)
    return missing


# --- the mirror: the configuration, the register, and the guard must agree ---------------------------------
def test_every_ignored_rule_is_named_in_the_register() -> None:
    """The property the guard exists for, derived here from the configuration and the register.

    Asserted independently of the guard on purpose: a guard whose own removal passes this suite
    would be one step away from not existing.
    """
    codes = ignored_rules()
    assert codes, "no ignored rules were read; a mirror over an empty set would pass vacuously"
    missing = missing_register_rows(RUFF_CONFIG.read_text(), REGISTER.read_text())
    assert not missing, f"ignored lint rules with no row in the register: {missing}"


def test_the_mirror_fails_when_an_ignored_rule_has_no_row() -> None:
    """The mirror's failure direction, on planted texts instead of only on this repository.

    Measured defect this pins: neutralising the comparison inside ``missing_register_rows`` left the
    whole suite green, because the only case ever run against it was this tree, where it succeeds. A
    comparison whose failure branch never runs is the same distance from not existing as the guard's
    was. The control is in the same test: the same configuration against a register that *does* name
    every rule must report nothing, so a comparison that failed everything would not pass this.
    """
    config = _config_with(["E501", "B904"])
    register = "| `E501` | a carried finding |\n| `S101` | a carried finding |\n"
    assert missing_register_rows(config, register) == ["B904"]
    assert missing_register_rows(config, register + "| `B904` | a carried finding |\n") == []


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
    write_sandbox(
        tmp_path,
        register="| `E501` | a carried finding |\n",
        config_text=_config_with(["E501", "B904"]),
    )
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


def test_every_job_key_uses_the_github_charset() -> None:
    """Every job key uses GitHub's ``[a-z][a-z0-9-]*`` charset, checked rather than filtered.

    Measured defect this pins: both scans selected key lines with ``[a-z][a-z0-9-]*``, so a job
    declared as ``register_check:`` or ``Register:`` matched neither of them. A job named that way
    and carrying no ``timeout-minutes`` therefore left ``test_every_ci_job_declares_a_timeout``
    green — a false green inside the test that exists to stop false greens. The scans now read keys
    permissively and this test rejects them, so a malformed key fails loudly in one place.
    """
    offenders = sorted(key for key in job_keys() if not _GITHUB_JOB_KEY.match(key))
    assert not offenders, (
        f"CI job keys outside GitHub's [a-z][a-z0-9-]* charset: {offenders}; the timeout scan "
        "reads keys by indentation, so such a key must be renamed rather than read past"
    )


def test_a_malformed_job_key_is_read_rather_than_skipped() -> None:
    """The same defect, exercised on a planted workflow, with a well-formed key as the control.

    Both halves are in one test on purpose: a scan that reported every job and a scan that reported
    none would each pass one half of this and fail the other, so only a scan that reads the two keys
    differently can pass both. The planted workflow is a string, so this measures the scan without
    editing this repository's own workflow.
    """
    malformed = _workflow_with_extra_job("register_check")
    assert "register_check" in job_keys(malformed)
    assert "register_check" in jobs_without_timeout(malformed)
    assert [key for key in job_keys(malformed) if not _GITHUB_JOB_KEY.match(key)] == ["register_check"]
    control = _workflow_with_extra_job("register")
    assert "register" in job_keys(control)
    assert "register" in jobs_without_timeout(control)
    assert [key for key in job_keys(control) if not _GITHUB_JOB_KEY.match(key)] == []
    # A job that does declare a timeout must not be reported, or a scan that reported every job
    # would satisfy the two cases above.
    assert "deploy" not in jobs_without_timeout(_workflow_with_extra_job("deploy", timeout=5))


def test_the_sandbox_configuration_is_the_text_it_was_given(tmp_path: pathlib.Path) -> None:
    """``write_sandbox`` writes the configuration it was handed, read back by the mirror's own rule.

    The guard tests are only as good as their sandbox: an earlier signature took the ignored rules
    twice, as an ``ignore`` list and as a ``config_text``, and used one of them, so a caller could
    build a sandbox other than the one it described. Reading the written file back is what makes
    that impossible to do silently.
    """
    write_sandbox(
        tmp_path,
        register="| `E501` | a carried finding |\n",
        config_text=_config_with(["E501"]),
    )
    assert ignored_rules_from((tmp_path / "ruff.toml").read_text()) == {"E501", "S101"}


def test_no_key_line_in_the_jobs_section_is_invisible_to_the_scans() -> None:
    """Every two-space key line the slice contains is read by the scans that slice it.

    The scans and this check share one key rule, so the property they cannot violate between
    themselves is that a key line is never *dropped*: either it is read as a job, or the charset
    test rejects it. Counted here rather than trusted, because dropping them was the defect.
    """
    lines = _jobs_section(WORKFLOW.read_text()).splitlines()
    candidates = [
        line
        for line in lines
        if len(line) > 2 and line.startswith("  ") and line[2] not in " #"
    ]
    read = job_keys()
    assert len(read) == len(candidates), (
        f"{len(candidates)} key lines under jobs: but {len(read)} were read as jobs; a key line "
        "the scans do not read is a job they cannot check"
    )


def test_a_workflow_without_a_jobs_section_is_not_read_as_an_empty_one() -> None:
    """The slice both scans share asserts its own success, so neither can pass over nothing.

    Guarded because ``jobs_without_timeout`` used to slice its own copy of the section and would
    have returned an empty list, and therefore claimed every job carries a timeout, if the section
    had gone missing.
    """
    without_jobs = WORKFLOW.read_text().replace("\njobs:\n", "\non:\n", 1)
    with pytest.raises(AssertionError, match="no jobs: section"):
        jobs_without_timeout(without_jobs)


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
