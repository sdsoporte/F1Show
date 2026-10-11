# Carried findings register

Every entry here is **non-blocking** and was opened by a native review or an independent verification
that offered **no correction**. None of them reopens an approved review: a burned authority is never
queried again, so these are later work by construction.

**An important limit on everything below.** The provider returns a finding's **id, lens, location and
severity** and never its body — proven when a search of the machine found the ids only in documents this
project wrote. So where an entry says what it is about, that reading is the **parent's or the peer's own,
derived from the location**, and explicitly **not** the provider's intent. Where the location alone is not
enough to name a subject, the entry says so instead of inventing one.

## How this register stays honest

- **Identity is the LOCATION, not the finding id.** The review gate is size-based, so when a candidate
  grows, the integration re-reviews bytes that were already approved and the same defect reappears under a
  fresh id. Deduplicating by location is what stops this list from inflating itself. One real example: five
  of the six findings in the F09 integration review re-surfaced findings the booth's own review had already
  raised, at the same lines, under different ids.
- **The register has its own trigger, and it is not "when someone looks at it".** This file is reviewed at
  **every unit closure**, and again the moment any entry's trigger fires.
- **An entry can be closed as a dead record, and saying so is part of the audit.** Without that exit,
  entries with no trigger accumulate and teach the opposite of what this list is for: that being listed
  means nothing. The dead-record section exists so the register can be left, and leaving it is evidence
  that the list is real.
- **A trigger names a concrete condition, never a person's attention.** Owner answers *who*; trigger
  answers *when*. An entry whose only possible trigger is "the next time someone touches that file" is a
  dead record by this rule, because that is attention wearing a costume.
- **"Carried as informational" is not a resting place.** It is how a broken public export survived five
  units in this repository, registered in every static report with a name and a line number and with
  nothing forcing anyone to look again.

## Register trigger

Reviewed at each unit closure, and whenever one of the listed triggers fires — currently **F10** for the
composition entries and **F13** for everything that needs the live service.

## auth.py — from the F03d-2 reviews

| Location | Ids | Severity | Owner | Trigger | Status |
|---|---|---|---|---|---|
| `:391-394` | R1-001 | WARNING | F03d follow-up | any change to bearer-header injection or the caller-`Authorization` refusal | OPEN |
| `:263-264` | R1-002 | WARNING | F03d follow-up | any change to credential acceptance | OPEN |
| `:140-148` | R1-003 | WARNING | F03d follow-up | any change to `expires_in` parsing | OPEN |
| `:211-222` | R3-001 | WARNING | F03d follow-up | any change to expiry or skew arithmetic | OPEN |
| `:283-292` | R4-retry-amplification | WARNING | F13 | the first live call, where retry behaviour against a real quota matters | OPEN |
| `:305-311` | R4-stale-token | WARNING | F13 | the first live call, since a revoked or rotated token is only observable against the real service | OPEN |
| `:193-200` | R2-repr-secret-materialization | SUGGESTION | — | — | **CLOSED**: the hardening unit removed `get_secret_value` from `repr` entirely, so the reported shape no longer exists |
| `:347` | R4-001 | WARNING | F13 | the first live call, same reasoning as R4-retry-amplification | OPEN |
| `:375-383` | R3-001 (hardening review) | SUGGESTION | F03d follow-up | any change to the token exchange path | OPEN |
| `tests/test_auth.py:558-559` | R2-magic-yield-count | SUGGESTION | — | — | **DEAD RECORD**: a test-local readability remark with no future condition that forces revisiting it |
| `:272-295`, `:168-173`, `:279-291`, `:282-288`, `:405-415`, `:256-269`, `:325-335` | R2-exchange-lifecycle, R2-post-except-raise, R3-002, R3-003, R3-004, R3-005, R4-transport-taxonomy | SUGGESTION | F13 | the first live call, where the exchange taxonomy and lifecycle become observable | OPEN, bodies unknown |

## gemini.py — from the F08 integration review

| Location | Ids | Severity | Owner | Trigger | Status |
|---|---|---|---|---|---|
| `:484-488` | R3-001 | **WARNING** | F13 | the live spend report, where usage accounting becomes observable | OPEN |
| `:477-480` | R3-002 | SUGGESTION | F13 | the live spend report | OPEN |
| `:348-354` | R3-003 | SUGGESTION | F13 | **the F10 trigger fired and the finding was not addressed**: F10 shipped without touching this call site, so no configured timeout reaches the SDK. The condition that matters is now the first live call, where an unbounded call becomes observable | OPEN |
| `:258-259` | R3-004 | SUGGESTION | F13 | **the F10 trigger fired and the finding was not addressed**: the composition wiring does not touch the failure classifier. What matters is a real provider whose coded status is typed differently from what the classifier tests for, which only a live call produces | OPEN |
| `:488` | R3-005 | SUGGESTION | F13 | the live spend report | OPEN |
| `:559-566` | R3-006 | SUGGESTION | F13 | the live spend report | OPEN |

The peer's reading, carried as its own and not as provider intent: the retry logic compares the error
`code` against an integer, so a provider sending `"429"` **as a string** would not be retried — whose
natural trigger is the **first live call of F13**, where a rate limit is exactly what should be retried.

## collector.py — from the F04 reviews

| Location | Ids | Severity | Owner | Trigger | Status |
|---|---|---|---|---|---|
| `:245-249` | R3-unhashable-identity | WARNING | — | — | **CLOSED**: `cfbe614` made the dedup identity hashable for any payload value |
| `:197-200` | R3-recursion-escape | WARNING | — | — | **DEAD RECORD**: reproduced by the parent and it does **not** crash; a pathologically deep programmatic payload is not reachable from a JSON parse |
| `:198-199` | R3-canonical-not-faithful | WARNING | F06 | F06 consuming `classify_gap`, or any change to the intervals normalization | OPEN |
| `:199-200` | R3-valueerror-branch-untested | SUGGESTION | issue #8 | promoting probe-only coverage into the suite | OPEN |
| `:170-175` | R3-fromisoformat-version-tail | SUGGESTION | F11, or F07 | **the F10 trigger did NOT fire**: F10 feeds no timestamp parse from configuration — the only configuration-fed values on the path are the integer `session_key` and the base-URL string. The condition is still a timestamp arriving from configuration, which is packaging/CLI work or F07 | OPEN |
| `:121-131` | R3-gapreading-cross-kind | SUGGESTION | F06 | F06 consuming `classify_gap` | OPEN |
| `tests/test_collector.py:26-33` | R3-fixtures-outside-candidate | SUGGESTION | — | — | **DEAD RECORD**: a note about the fixtures living outside the candidate; the fixtures are committed, so the condition it described has passed |

## booth.py and its tests — the peer's, deduped by location

**Every anchor below was re-measured after the F09b unit**, which grew `booth.py` from 615 to 763 lines and
`tests/test_booth.py` by 619. The re-anchoring was done by **reading the old blob and finding the same
subject in the new file**, never by trusting a diff's arithmetic: the repr fallbacks moved from `:317-322`
to `:466-470`, the positive-seconds bound from `:336-340` to `:482-489`, and the bound guards in the test
file from `1039-1050` to `1658-1670`. This is the standing cost of the location-as-identity rule: when a file
grows, a location that is not re-derived by subject becomes silently wrong, and a wrong location is worse
than no location because it reads as verified.

| Location | Ids observed there | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `:117-123` | R3-005 (integration) = R3-persona-validator-uncovered (unit) | SUGGESTION | issue #8 | promoting probe-only coverage, or any change to the personas | OPEN |
| `:466-470` | R3-001 and R3-003 (integration) = R3-render-repr-determinism (unit) | SUGGESTION | F13 | **an evidence value that cannot be serialized reaches the prompt** — a data event, or a change in F04's contract | OPEN, with the fix already decided below |
| `:482-489` | R3-002 (integration) = R3-positive-seconds-overflow (unit) | SUGGESTION | whoever sources a bound from configuration | **the F10 trigger did NOT fire**: `main` calls `run_session` without the bound parameters, so they keep their signature defaults. The composition wiring shipped without promoting a single bound into configuration | OPEN |
| `tests/test_booth.py:1658-1670` | R3-006 (integration) = R3-bound-guards-uncovered (unit) | SUGGESTION | issue #8 | any change to the bounds list | OPEN |
| `:299-302` | R3-bullet-commentary-false-refusal (F09b unit) | SUGGESTION | F13 | the first live trial that observes the model's output style, or any unit touching `_CITATION_SHAPED` | OPEN, **re-measured by the parent** below |
| `:375-377` | R3-bracket-continuation-leak (F09b unit) | **WARNING** | the next unit touching the scanner, or a live transcript showing a fragment | a fragment of a never-supplied reference airing in an aired turn | OPEN, **re-measured by the parent** below |
| `:288-294` (pre-F09b) | R3-004 (integration) | SUGGESTION | — | — | **SUPERSEDED by measurement**, see below |
| — | R3-positive-seconds-overflow | SUGGESTION | — | — | **promoted, not dead**: F10 shipped and the bound is still a constant, so the entry above stays OPEN under its original condition |

**The two F09b findings, re-measured by the parent on the integrated bytes** rather than taken from the
report. Both reproduced exactly, and the second came back **sharper than the report**:

- **The attached-bracket continuation leaks.** `position[0].position.[99].evil`, `position[0].position.[99]`
  and `position[0].position [99].evil` all **air**, while `position[0].position[99]`,
  `position[0].position[99].evil`, `position[9].position.invented` and `position[0].position[0].evil` are all
  refused. So the rule catches a bracket only when it is glued directly onto the matched token, and a dot or
  a space defeats both the scanner's token boundary and the attached-bracket check. The guarantee holds
  because what airs is a **fragment**, never a complete never-supplied token.
- **The over-refusal is new for the bullet and case forms, and the measurement says which.** `- Evidence: the
  gap closed by four tenths.` and `* evidence: tyres are gone` are refused as `MULTIPLE_CITATION_LINES`, and
  so is the unbulleted `Evidence: the gap closed by four tenths.` — but the **exact** reading that shipped
  before this unit, still present and still used for acceptance, returns `False` for the two bullet forms and
  `True` for the unbulleted one. So one of the three was already refused, and the other two are refused
  **only because the unit widened the violation predicate to close the bullet and case escape channels**.
  The declared fail-closed cost in the design is about *reference-shaped* prose; prose that merely opens with
  the marker's own word is a separate case and is not declared, which is what makes this worth its own row,
  and the peer reported it as undeclared. The deliberate pin survives the measurement: a mid-sentence mention
  still airs, and a supplied reference still airs.

**R3-004 retired as superseded, and a measurement is what retired it.** The pre-F09b `booth.py:288-294` held
`if any(_opens_with_citation_marker(line) for line in lines[start + 1:]):` followed by
`return _RefusedAnswer(BoothReason.MULTIPLE_CITATION_LINES)` — the citation-violation predicate itself. The
F09b unit rewrote exactly that predicate, and its own review then placed a measured finding on the successor
code. So the subject R3-004 pointed at was rewritten by the unit that owned it, and the surviving issue on
that subject is registered above with a body and a trigger. Keeping R3-004 open beside it would be two rows
for one subject, and with no recoverable body no fix could ever be verified. This is a scope retirement
**proved by the location's content**, not a claim that something was fixed.

The peer's reading, carried as its own, and it carries **two damages of different kinds**, which is why it
matters more than a tidy-up. The `_render` path has two ways to fall back to `repr` —
`json.dumps(..., default=repr)` for a nested value JSON cannot encode, and an
`except (TypeError, ValueError)` branch that calls `repr` on the whole value — and either can print a
**memory address**. Confirmed by the parent in the
source at `booth.py:466-470` (re-measured after the F09b unit; it was `:311-322` before). So a non-serializable value would (a) **filter implementation detail outward**
to the provider, and (b) **break reproducibility inward**, and that second one is not a wording problem:
"a replay re-produces the transcript" is the MVP's acceptance criterion, so a prompt carrying an address is
a non-deterministic run with a differently-shaped transcript every time.

**The trigger is therefore not "F13" in the abstract, and the fix is a one-line policy decision.** The
reference is unreachable for any JSON-serializable value, and the collector's evidence today comes from
JSON fixtures, so the condition that matters is exactly: **an evidence value that cannot be serialized
reaches the prompt.** When that happens the right response is **to refuse the value with a typed error
rather than render it approximately** — a non-serializable value in the evidence is a violation of F04's
contract, not a shape to be drawn as well as possible. Refusing deletes the `repr` fallback, and with it
both damages. Recorded this way so that whoever picks it up does not have to design anything: the decision
is already made, and the only work is the error type and its test.

## run.py — from the F10 review

F10 was reviewed and approved as `review-0114285928bfdd2d` (medium tier, one `review-reliability` lens),
and all four findings are non-blocking: none opened a correction and none reopens the review. The reviewer's
descriptions are **not recoverable** — the receipt carries ids, severities and locations only — so the
**subject of each row is the parent's reading of the location, and the owner and trigger are the parent's
inference, not the reviewer's words**. The location is the identity.

| Location | Ids | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `:123-128` | R3-001 | **WARNING** | the next corpus refresh (issue #3, or any re-recording) | a corpus file that does not parse: this is the branch that puts the decoder's own message into a `RecordedSourceError`, so its shape matters exactly when a truncated or half-written file exists | OPEN, body unknown |
| `:243-255` | R3-002 | SUGGESTION | F13 | the first live call: `main` builds the model client **before** it reads the corpus, so the gemini branch constructs a real SDK client ahead of a load that may fail | OPEN, body unknown |
| `:286-316` | R3-003 | SUGGESTION | F13 | the first live call: the gemini branch materializes the credential and builds the SDK client with a base URL and **no timeout**, so the same subject as the `gemini.py` row above sits on the F10 side too | OPEN, body unknown |
| `:168-173` | R3-004 | SUGGESTION | the first live call, or any change to the declared base URL | the `native_base_url` derivation: the trailing-segment rule is proved for the two declarations in use, so a third declaration shape is what would revisit it | OPEN, body unknown |

One honest note about this unit: **the four F10-owned triggers in the tables above were reached by the same
commit**, and three of them did not fire, which is the reconciliation this register exists to force. F10
chose a dialect and a base URL, and it promoted nothing else: no bound, no timestamp and no timeout travelled
from configuration into the engine. That is recorded at the location of each entry rather than summarised,
because a reviewer of the register should be able to check the claim without trusting this paragraph.

## Cross-cutting, from verification rather than from reviews

| Subject | Where recorded | Owner | Trigger | Status |
|---|---|---|---|---|
| Five probe-only cases from F03c-3a: empty checkpoint from a distinct prior stamp, checkpoint-await cancellation, direct-await KI/SystemExit, no-prior-watermark write failure, drivers immutability/mixed-session refusal | issue #8 | issue #8 | promoting probe-only coverage | OPEN |
| The F03c-4 generation branch is unreachable through the public API | issue #8 | issue #8 | deciding to reach it or to delete it | OPEN |
| Race coverage in the session lifecycle is scripted, not real concurrency | issue #8 | issue #8 | any change to the lifecycle, or a decision that real concurrency is needed | OPEN |
| A retried POST may be sent more than once — an unverified provider assumption | issue #9 | issue #9 | any live call, or a decision to exclude POST from the retry set | OPEN |
| The declared Python 3.12 floor is proven runnable but nothing enforces it | issue #7 | issue #7 | committing a CI matrix, or any dependency bump | OPEN |
| No lint configuration is committed, so every "clean" claim is scoped to an external harness file | issue #7 | issue #7 | committing a real configuration | OPEN |
| The live service, the real token exchange and real responses are unverified | issue #3 | F13 | a purchased subscription and an explicit grant | OPEN |

## Closed as dead records, and why

- **`R2-magic-yield-count`** (`tests/test_auth.py:558-559`): a test-local readability remark. No future
  event forces it; the only way it would ever be revisited is someone happening to open that file, which is
  attention rather than a trigger.
- **`R3-recursion-escape`** (`collector.py:197-200`): reproduced by the parent on the real bytes and it does
  **not** crash. The pathological input it describes cannot come from a JSON parse, so there is no condition
  under which the product meets it.
- **`R3-fixtures-outside-candidate`** (`tests/test_collector.py:26-33`): it described the fixtures living
  outside the reviewed candidate, and the fixtures are now committed. The condition has passed.

Recording these as dead is the point of the section, not an admission: a register that cannot be left
teaches that membership means nothing.
