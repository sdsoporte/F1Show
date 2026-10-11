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
| `:348-354` | R3-003 | SUGGESTION | F10 | the composition wiring, when a dialect and a base URL are chosen | OPEN |
| `:258-259` | R3-004 | SUGGESTION | F10 | the composition wiring | OPEN |
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
| `:170-175` | R3-fromisoformat-version-tail | SUGGESTION | F10 | the composition wiring, where a parse is first fed from configuration | OPEN |
| `:121-131` | R3-gapreading-cross-kind | SUGGESTION | F06 | F06 consuming `classify_gap` | OPEN |
| `tests/test_collector.py:26-33` | R3-fixtures-outside-candidate | SUGGESTION | — | — | **DEAD RECORD**: a note about the fixtures living outside the candidate; the fixtures are committed, so the condition it described has passed |

## booth.py and its tests — the peer's, deduped by location

| Location | Ids observed there | Severity | Owner | Trigger | Status |
|---|---|---|---|---|---|
| `:117-123` | R3-005 (integration) = R3-persona-validator-uncovered (unit) | SUGGESTION | issue #8 | promoting probe-only coverage, or any change to the personas | OPEN |
| `:317-322` | R3-001 and R3-003 (integration) = R3-render-repr-determinism (unit) | SUGGESTION | F13 | the first real prompt assembled for a live provider, or an evidence value that is not serializable (a change in F04's contract) | OPEN |
| `:336-340` | R3-002 (integration) = R3-positive-seconds-overflow (unit) | SUGGESTION | F10 | a bound that arrives from **configuration** instead of a constant, which is the composition wiring | OPEN |
| `tests/test_booth.py:1039-1050` | R3-006 (integration) = R3-bound-guards-uncovered (unit) | SUGGESTION | issue #8 | any change to the bounds list | OPEN |
| `:288-294` | R3-004 (integration) | SUGGESTION | the peer's citation-channel unit | **inside the unit currently in flight**, so it closes there or is re-registered here | OPEN |
| — | R3-positive-seconds-overflow | SUGGESTION | — | — | **DEAD RECORD only until F10 ships**: as soon as a bound can come from configuration the trigger above exists, so it is promoted rather than dead |

The peer's own reading, carried as its own: the `repr` fallback in `_render` is not deterministic because it
can print **memory addresses**, so a real prompt could leak implementation detail to the provider. That is
why its trigger is the first live prompt rather than a general tidy-up.

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
