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
- **A row carries a COORDINATE and a SUBJECT, and a coordinate without a subject is not evidence.** Lines
  move — a file grows by an insertion far above a row and every number below it is wrong while still looking
  verified. Each file's table is therefore followed by a **measured subject block**: what the location holds,
  read from the old blob and found again in the current file. This rule was added after the F09b unit, when
  two rows in this file were found pointing at the wrong code and one of them had been *described in a note as
  re-measured* when it never was.
- **Staleness has a mechanical trigger, and it is a HASH, not a line count.** The key is the file's **blob
  OID** at the revision its rows were recorded against: any change of bytes flips it, so it cannot give a
  false green. A line-count delta is only a cheaper first pass and it is **necessary but not sufficient** — a
  refactor that adds and removes the same number of lines, a reorder or a rename leaves the length untouched,
  and every row in that file would read as current without ever having been re-derived. The per-file keys are
  recorded in **Staleness keys** below, so this is an operation (`git rev-parse HEAD:<path>`) rather than a
  reading. Measured when the rule was upgraded: the false green it exists to prevent **had not occurred** here —
  no file changed bytes with an unchanged length — but the hash did find two files the line audit had missed,
  `tests/test_auth.py` and `tests/test_collector.py`. **The mechanism is named so that the re-derivation is
  done for a reason and not by rote**: the error that created this rule was a `sed -n '286,295p'` window printed
  and then read as if it were the cited range `288-294` — a real measurement of a **different object** than the
  row asserts, which is why it survived every check that only asked whether the number looked right.
- **A closure has a TYPE, and "closed" alone is not evidence.** Four kinds appear here and they are not
  interchangeable: closed by **change** (bytes moved and a test went red first), closed by **pin** (a test was
  added that also passes on the unaffected code, so behaviour did not change and there was **no RED**), closed
  as a **dead record** (no future condition forces it), and closed as **superseded by a rewrite**, where the
  location no longer holds the subject at all. A pin proves that an intended behaviour is now watched; it
  proves nothing about a defect having been fixed, so a row closed by pin must say so. **The fourth kind earns
  its own sentence because it is the dangerous one: it depends on coordinates, and a coordinate can be
  asserted without measuring anything** — which is how the error this rule came from was born. "Superseded"
  proves nothing until the subject descriptor shows that the location really changed. Added after the F09b
  unit, whose `R3-004` closed by pin while this register first recorded it as superseded by a rewrite — see
  that row.
- **"Carried as informational" is not a resting place.** It is how a broken public export survived five
  units in this repository, registered in every static report with a name and a line number and with
  nothing forcing anyone to look again.
- **Absence is checked by CONTEXT, never by count.** Once this register — or the task record — **quotes** a
  wrong claim in order to record that it was corrected, a bare `git grep -c` for that claim returns a hit on
  `main` again: the quotation itself. Measured when it happened: three corrected phrases each came back as `1`
  after the correction record was published, while every one of those hits sits inside the single sentence that
  lists what was fixed. So the check is **where** a phrase appears and **how** it is framed, never how many
  times — otherwise the honest record of a correction reads as a surviving defect, and the next reader either
  panics at it or, worse, "re-fixes" the quotation.

## Staleness keys

The blob OID of each file **at the revision its rows were recorded against**, next to the current one. A
difference means every row in that table must be re-derived by subject before its numbers are used; identity
means the coordinates are still the ones the reviewer saw. One command per row: `git rev-parse HEAD:<path>`.

| File | Blob at the recorded revision | Blob now | Verdict |
| --- | --- | --- | --- |
| `src/f1show/gemini.py` | `466db02b1977788c0faf3e6ffbd019a219c767fa` | same | **current** |
| `src/f1show/run.py` | `ee44616f94838abfd2e2d44ab83b7241b0c0c801` | same | **current** |
| `tests/test_run.py` | `e4fd5317baf868bf0a6cfa76de238ff9dd2203b3` | same | **current** |
| `src/f1show/auth.py` | `b1ab34d8f1b3cfff856ec7a4cbf2633cbbb2d8cc` | `51918e432e3b8ae617fb3a1f566b72a9a6193099` | **STALE — rows re-derived** (16 anchors with ids and subjects); the key stays different, correctly |
| `src/f1show/collector.py` | `a8a81ee93795b7934b32c715bfc47111770155c2` | `3973eb134e797bda1d7062cee357eb70bf69de9f` | **STALE — rows re-derived** (three already current, two moved one line, one closed by change); the key stays different |
| `tests/test_auth.py` | `66e7e41e39640744de2670a7371c6226ce98258b` | `d9cda83a99a94e8b13da03c814baf1df54c7846e` | **STALE — its row re-derived and UNMOVED** (`:558-559` is exact); the blob over-flagged |
| `tests/test_collector.py` | `1b3123c684aab95ebf3ae1b9bfcc12b0941da7a7` | `7b4891758e49c00aded53413c85603e87ca169f6` | **STALE — row re-derived** (`:26-33` → `:27-34`) |
| `src/f1show/booth.py` | `0d1191c626fca1b9f559a6a5ea89e10f2c621c28` (post-F09b) | `a21d4d1d75e0a5c291b8bdf01183210127748bf5` | **STALE — rows re-derived by SUBJECT** for the F09c `+32` docstring shift (four of four tokens consistent), and the new key is the current one |
| `tests/test_booth.py` | `8704aeeda5f7623f8b8875c61af7e0fe2d4e35a3` (post-F09b) | `cc65c60e8926df10112e6ac3e7834e1bc1a535ba` | **STALE — row re-derived** by subject: the bounds guards moved to `:1783-1795`, and the 17-case pin lives at `:1191` |

**The per-symbol hash is REJECTED, and the rejection is a decision rather than a deferral.** The proposal — its
author's, and offered as reasoning rather than as a measurement — was to key staleness on the hash of the symbol
that contains the subject, since the blob is file-level and therefore **over-flags**: a row in `booth.py` does
not age because `run.py` grew. Measured, that over-flagging has cost **exactly one row-check so far**:
`tests/test_auth.py` is STALE by blob while its single row was UNMOVED, and the check that revealed it was one
grep. Against that, adopting it costs a stored symbol per row plus resolving the enclosing symbol at every
re-derivation, on a register whose rows are re-derived only when a file actually changes — a structural cost
paid always, for a small benefit paid rarely.
**The trigger that revives it is stated so this stays a decision with a condition rather than a closed door**: a
single change that forces the re-derivation of **more than five rows in one file where only one or two actually
moved**. That is the shape the blob key cannot handle cheaply, and it is a measurement anybody can take when it
happens.

## Register trigger

Reviewed at each unit closure, and whenever one of the listed triggers fires — currently **F10** for the
composition entries and **F13** for everything that needs the live service.

## auth.py — from the F03d-2 reviews

**Every coordinate in this table is from the F03d-2 revision, and `auth.py` has grown by 70 lines since (416
→ 486) through the auth-hardening unit. No row here has been re-derived by subject, so read these numbers as
HISTORICAL, not as verified pointers.** The re-derivation was run at the F09b closure and the measured anchors
are recorded at the end of this section, so the work is not lost and the next unit touching this file can
finish it. This is exactly the rot the register suffers when coordinates are trusted: the hardening is one of
this project's own reviewed units, and its rows were never re-anchored.

| Location | Ids | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `:391-394` | R1-001 | WARNING | F03d follow-up | any change to bearer-header injection or the caller-`Authorization` refusal | OPEN |
| `:263-264` | R1-002 | WARNING | F03d follow-up | any change to credential acceptance | OPEN |
| `:140-148` | R1-003 | WARNING | F03d follow-up | any change to `expires_in` parsing | OPEN |
| `:211-222` | R3-001 | WARNING | F03d follow-up | any change to expiry or skew arithmetic | OPEN |
| `:283-292` | R4-retry-amplification | WARNING | F13 | the first live call, where retry behaviour against a real quota matters | OPEN |
| `:305-311` | R4-stale-token | WARNING | F13 | the first live call, since a revoked or rotated token is only observable against the real service | OPEN |
| `:193-200` | R2-repr-secret-materialization | SUGGESTION | — | — | **CLOSED**: the hardening unit removed `get_secret_value` from `repr` entirely, so the reported shape no longer exists |
| `:410-423` | R4-001 | WARNING | F13 | the first live call: the docstring promises a lifecycle — adoption, exactly one `close`, refusal after closing — that only a real call can witness | OPEN |
| `:375-383` | R3-001 (hardening review) | SUGGESTION | F03d follow-up | any change to the token exchange path | OPEN |
| `tests/test_auth.py:558-559` | R2-magic-yield-count | SUGGESTION | — | — | **DEAD RECORD**: a test-local readability remark with no future condition that forces revisiting it |
| `:272-295`, `:168-173`, `:279-291`, `:282-288`, `:405-415`, `:256-269`, `:325-335` | R2-exchange-lifecycle, R2-post-except-raise, R3-002, R3-003, R3-004, R3-005, R4-transport-taxonomy | SUGGESTION | F13 | the first live call, where the exchange taxonomy and lifecycle become observable | OPEN, bodies unknown |

**Measured re-anchoring, old → current, with the subject and the ROW ID at each new location.** These are the
numbers a reader should use; the table's are historical. `:391-394` **R1-001** → **`:464`** (the bearer-header
merge inside `get_json`); `:263-264` **R1-002** → **`:282`** (credential acceptance); `:140-148` **R1-003** →
**`:157`** (the `expires_in` parse); `:211-222` **R3-001** → **`:235`** (the expiry/skew arithmetic, in the
docstring); `:283-292` **R4-retry-amplification** → **`:304`** (a completed exchange that left no valid token
is discarded); `:305-311` **R4-stale-token** → **`:357`** (the clock and skew passed to the state);
`:193-200` **R2-repr-secret-materialization**, closed → **`:212`** (the timezone-aware `issued_at` refusal);
`:375-383` **R3-001 (hardening)** → **`:450`** (the bearer header added to the caller's request); and for the
grouped row, in the order the anchors are listed there: `:272-295` → **`:295`** (the provider `repr`),
`:168-173` → **`:186`** (pydantic captures the refused input, so the raise happens after the handler),
`:279-291` → **`:298`** (the valid-token docstring), `:405-415` → **`:475`** (`post_form_json`),
`:256-269` → **`:280`** (the credentials message), `:325-335` → **`:374`** (`_post_credentials`). Their seven
ids **are not paired to their seven anchors here**, because the bodies are unrecoverable and that pairing
cannot be measured — the honest record is the set on both sides, not an invented marriage.
**`:347` (R4-001), re-anchored to `:410-423`, and the coordinate was never the interesting part.** The row
sat on a line that no longer exists, so it was recorded as NOT FOUND; measuring the old blob showed why
arithmetic could not settle it and why it did not need a human either: **`:347` is a blank line inside the
`AuthenticatedHttpClient` docstring** (`:346` opens it), so the subject was always **prose describing a
contract**, not a branch of code. In the current file that docstring is `:410-423` — the caller-`Authorization`
refusal, and the adoption/`close` lifecycle it promises — with the refusal implemented at `:457` and the header
injection at `:463`. Re-anchored with its **F13 trigger intact**, because a documented lifecycle promise is
witnessed only by a real call: that is a re-anchor, not a closure, and it leaves the table with **zero rows in
NOT FOUND**.

## gemini.py — from the F08 integration review

| Location | Ids | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `:484-488` | R3-001 | **WARNING** | F13 | the live spend report, where usage accounting becomes observable | OPEN |
| `:477-480` | R3-002 | SUGGESTION | F13 | the live spend report | OPEN |
| `:348-354` | R3-003 | SUGGESTION | F13 | **the F10 trigger fired and the finding was not addressed**: F10 shipped without touching this call site, so no configured timeout reaches the SDK. The condition that matters is now the first live call, where an unbounded call becomes observable | OPEN |
| `:258-259` | R3-004 | SUGGESTION | F13 | **the F10 trigger fired and the finding was not addressed**: the composition wiring does not touch the failure classifier. What matters is a real provider whose coded status is typed differently from what the classifier tests for, which only a live call produces | OPEN |
| `:488` | R3-005 | SUGGESTION | F13 | the live spend report | OPEN |
| `:559-566` | R3-006 | SUGGESTION | F13 | the live spend report | OPEN |

**Subject block, now measured.** `gemini.py` is unchanged since its review — blob
`466db02b1977788c0faf3e6ffbd019a219c767fa`, 567 lines — so these coordinates are the reviewer's own and the
subjects below were read from those exact lines, not inferred: `:484-488` the retry loop's tail
(`self._record(request, response, attempt)`, then `return response`, then the exhaustion branch
`if not failure.retryable or attempt >= policy.max_attempts: raise failure`); `:477-480` the `TimeoutError`
mapping inside the attempt loop; `:348-354` `_to_model_response`'s empty-turn refusal; `:258-259`
`code = getattr(exc, "code", None)`, the status-code read; `:488` the `raise failure` that re-raises the
classified error after the handler has exited; `:559-566` the measured-usage alert.
**One thing the coordinates reveal that the rows did not say**, and it is worth stating because it makes the
first row's trigger concrete rather than vague: usage is recorded **per attempt** (`self._record` runs on every
try), so a retried call records usage **more than once**, and the only place that becomes observable is a real
quota — which is why this row's trigger is the live spend report and not a unit. The alert at `:559-566` says
the rest out loud itself: *"measured usage is not a hard spend limit and no cost stop exists before F13"*.
**And a limit of this whole table that the re-derivation cannot fix**: the bodies are unrecoverable, so the
subjects above say what the code at each coordinate **does**, never what the reviewer **meant**. Where a row's
stated trigger and its subject look unrelated, the honest reading is that one of the two is wrong and no
measurement available here can say which.

The peer's reading, carried as its own and not as provider intent: the retry logic compares the error
`code` against an integer, so a provider sending `"429"` **as a string** would not be retried — whose
natural trigger is the **first live call of F13**, where a rate limit is exactly what should be retried.

## collector.py — from the F04 reviews

**The coordinates in this table are correct as they stand, and the reason this section first said they were
HISTORICAL is itself the lesson.** The blob said the file had changed (288 → 330 lines, +42 through the F04
identity correction), and the parent then re-anchored by matching lines against the **F04 tree** — the wrong
revision — and reached a wrong conclusion: that three rows had "collapsed" onto one line and that everything
here was stale. Read against the revision they were actually recorded against, the picture is specific and
mostly reassuring. **Three rows are exactly current**, recorded after the correction, and they sit inside
`_canonical_rendering` where they are told apart by **subject** rather than by coordinate: `:197-200` is the
`default=repr` / `repr(value)` pair (R3-recursion-escape, dead), `:198-199` is the
`json.dumps(value, sort_keys=True, default=repr)` line (R3-canonical-not-faithful) and `:199-200` is the
`except (TypeError, ValueError): return repr(value)` branch (R3-valueerror-branch-untested). Two more moved by
exactly **one line**: `:121-131` → **`:122-131`** (the `GapReading` fields and `_value_matches_kind`, subject
"a laps reading must carry its lap count") and `:170-175` → **`:174-184`** (`_as_instant`, subject
`dt.datetime.fromisoformat(value)`, the version-tail question). The closed row is the interesting one:
`:245-249` described the dedup identity, and the fix moved that code into `_identity_token` at **`:203-220`**
plus `_canonical_rendering` at **`:187-200`** — so the row is closed **by change**, and what is recorded is the
code's new home rather than a new number for the old one. And the test row moved by one:
`tests/test_collector.py:26-33` → **`:27-34`**, the module constants including the fixtures path.

| Location | Ids | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `:245-249` | R3-unhashable-identity | WARNING | — | — | **CLOSED**: `cfbe614` made the dedup identity hashable for any payload value |
| `:197-200` | R3-recursion-escape | WARNING | — | — | **DEAD RECORD**: reproduced by the parent and it does **not** crash; a pathologically deep programmatic payload is not reachable from a JSON parse |
| `:198-199` | R3-canonical-not-faithful | WARNING | F06 | F06 consuming `classify_gap`, or any change to the intervals normalization | OPEN |
| `:199-200` | R3-valueerror-branch-untested | SUGGESTION | issue #8 | promoting probe-only coverage into the suite | OPEN |
| `:170-175` | R3-fromisoformat-version-tail | SUGGESTION | F11, or F07 | **the F10 trigger did NOT fire**: F10 feeds no timestamp parse from configuration — the only configuration-fed values on the path are the integer `session_key` and the base-URL string. The condition is still a timestamp arriving from configuration, which is packaging/CLI work or F07 | OPEN |
| `:121-131` | R3-gapreading-cross-kind | SUGGESTION | F06 | F06 consuming `classify_gap` | OPEN |
| `tests/test_collector.py:26-33` | R3-fixtures-outside-candidate | SUGGESTION | — | — | **DEAD RECORD**: a note about the fixtures living outside the candidate; the fixtures are committed, so the condition it described has passed |

**A concrete case of the over-flagging that the blob key admits, and the reason the subject is what decides.**
`tests/test_collector.py` and `tests/test_auth.py` are **both STALE by blob**, and only one of their rows
actually moved: the collector row above shifted by a line, while `tests/test_auth.py:558-559` — the
`for _ in range(50): await asyncio.sleep(0)` yield count — sits at **exactly** its recorded coordinate in a file
that grew by 172 lines. So the blob answers *"did this file change"* and only the subject answers *"did **this
row** change"*. That is the per-symbol refinement's argument, with an instance instead of a theory.

## booth.py and its tests — the peer's, deduped by location

**This note was wrong in its first form, and the error is the point.** It said every anchor below had been
re-measured after the F09b unit. Three had been: the repr fallbacks (`:317-322` → `:466-470`), the
positive-seconds bound (`:336-340` → `:482-489`) and the bound guards in the test file (`1039-1050` →
`1658-1670`). **The fourth had not**, and it had moved: the persona validator is now at `:143-150`, not
`:117-123`, because the hardening inserted lines above it too. A note claiming that everything was re-measured,
written over a table where one row was not, is the failure mode this whole register is built against — **a
statement that reads as verified without being about the thing it claims.** The lesson is mechanical: the
re-derivation is per ROW, and a section-level claim is not a substitute for it.

| Location | Ids observed there | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `:175-182` | R3-005 (integration) = R3-persona-validator-uncovered (unit) | SUGGESTION | issue #8 | promoting probe-only coverage, or any change to the personas | OPEN |
| `:498-502` | R3-001 and R3-003 (integration) = R3-render-repr-determinism (unit) | SUGGESTION | F13 | **an evidence value that cannot be serialized reaches the prompt** — a data event, or a change in F04's contract | OPEN, with the fix already decided below |
| `:514-521` | R3-002 (integration) = R3-positive-seconds-overflow (unit) | SUGGESTION | whoever sources a bound from configuration | **the F10 trigger did NOT fire**: `main` calls `run_session` without the bound parameters, so they keep their signature defaults. The composition wiring shipped without promoting a single bound into configuration | OPEN |
| `tests/test_booth.py:1783-1795` | R3-006 (integration) = R3-bound-guards-uncovered (unit) | SUGGESTION | issue #8 | any change to the bounds list | OPEN |
| `:331-335` | R3-bullet-commentary-false-refusal (F09b unit) = R3-marker-word-false-refusal (integration review) | **WARNING** | F13 | the first live trial that observes the model's output style, or any unit touching `_CITATION_SHAPED` | OPEN, **re-measured by the parent**, and **independently re-surfaced by the integration review under a fresh id**. Now also the subject of the user's authorized redesign |
| `:407-409` | R3-bracket-continuation-leak (F09b unit) | **WARNING** | the next unit touching the scanner, or a live transcript showing a fragment | a fragment of a never-supplied reference airing in an aired turn | OPEN, **now a DECLARED shape** rather than an undeclared one — see the closure below |
| `:53-54` (pre-F09c) | R3-docstring-omits-bracket-fragment-leak (integration review) | SUGGESTION | — | — | **CLOSED by declaration and pin** (F09c, `bde8d5f`) — see below |
| `:56-57` | R3-doc-stale-leak-placement (F09c review) | SUGGESTION | the next unit touching the scanner's docs | any change to the docstring's boundary sentence | OPEN — the noun is stale (see the notes) |
| `tests/test_booth.py:1124-1127` | R3-shape5-whitespace-tolerance-scope (F09c review) | SUGGESTION | the next unit touching the scanner or its declaration | any change to the `space` parameter's id or comment | OPEN — the label and the measured discriminator disagree (see the notes) |
| `:288-294` (pre-F09b) | R3-004 (integration) | SUGGESTION | — | — | **CLOSED inside the F09b unit by two pins** — no behaviour change and **no RED**, a weaker evidence class than closed by change; see below |
| — | R3-positive-seconds-overflow | SUGGESTION | — | — | **promoted, not dead**: F10 shipped and the bound is still a constant, so the entry above stays OPEN under its original condition |

**The F09c unit moved every coordinate below the module docstring by exactly +32 lines, and the shift was verified by SUBJECT, not by arithmetic.** The source commit `bde8d5f` is one hunk, `@@ -49,14 +49,46 @@`, entirely inside the module docstring — so nothing below it changed behaviour, and everything below it moved. Each row's new coordinate was found by locating the token recorded as that row's subject: `_strip_non_blank` 146→178, `_CITATION_SHAPED` 299→331, the scanner's compile 375→407, `default=repr` 468→500, `def _positive_seconds` 482→514 — four of four consistent with +32, which is why +32 is stated rather than assumed. New keys: `booth.py` `a21d4d1d75e0a5c291b8bdf01183210127748bf5` (was `0d1191c626fca1b9f559a6a5ea89e10f2c621c28`, 795 lines), `tests/test_booth.py` `cc65c60e8926df10112e6ac3e7834e1bc1a535ba` (1810 lines).

**A closure, and the first one here closed by DECLARATION rather than by change or pin alone.**
`R3-docstring-omits-bracket-fragment-leak` is **closed** by `bde8d5f`: the module docstring now enumerates
every airing shape — the four it already named, the **bracket fragment as a fifth declared shape**, and the
known `U+034F` leak — and a parametrized pin covers **all 17 cases** (measured by collecting the test: 17
parameters), one per declared shape plus three for the leak family. The fifth shape is declared **by
mechanism**, and the peer's reason is measurable rather than stylistic: the space-separated form
(`position[0].position [99].evil`) contains **no dot at all**, so calling the whole family a dotted suffix would
be **false for one of the three measured cases** and would relocate the ambiguity instead of removing it. The
correction cycle ended when the sentence stopped naming a category and named the mechanism instead — a
category can always have a sister category, and `Mc`/`Me` turned out to leak exactly like `Mn`.

**Two informational findings from that unit's review, recorded with its author's reading and not the
provider's intent.** `R3-doc-stale-leak-placement` (`:56-57`): the sentence uses **placement** for what was
unrecorded about the **character**, while the docstring does define the place (inside a structural joint), so the
noun is stale. `R3-shape5-whitespace-tolerance-scope` (`tests/test_booth.py:1124-1127`): the id and the `space`
parameter's comment suggest the mechanism is the **separator**, while the discriminator actually measured is the
**family word consumed**. Neither changes behaviour, and both carry an owner and a trigger above.

**Three more things this unit left in the record, and none of them is a fix.** (1) **The ten structural mutants
are now LISTED** where they earlier were only named as a result — a verifier had to ask for the set, and that
was a defect of the register rather than of the verifier. (2) **`Me` is named in the docstring but has no pin
of its own**: its behaviour was probed, not fixed, and the docstring only claims the marks are common cases, so
there is no over-claim — but a named case with no case exercising it is thin, and it is recorded as such.
(3) **`position]99[.invented`, with the brackets inverted, airs**, covered only by the general out-of-scope
sentence; enumerating it would be a **seventh declared shape**, which is a **decision rather than a fix** — and
by this unit's own rule it belongs to the user, exactly like the shape it just declared.

**The two F09b findings, re-measured by the parent on the integrated bytes** rather than taken from the report.
Both reproduced exactly, and the second came back **sharper than the report**. The first of the two has since
been **closed by declaration** in F09c — which is why its row above reads as a declared shape rather than as a
hole — and the second is now the subject of a redesign the user authorized:

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

**One defect, two independent reviewers, and the fresh id is the point.** The integration review of the F09b
unit approved on its first run and re-surfaced the over-refusal at `booth.py:300-303` under a new id,
`R3-marker-word-false-refusal`, one line off the location this unit's own review had used. That is the exact
behaviour this register was built around — **the size-based gate re-reviews already-approved bytes and
surfaces the same defect under a fresh id** — now observed rather than predicted, which is why the id sits in
the row it shares with the unit's id instead of on a parallel row. It also **raises the weight of the
finding**: what was one reviewer's reading plus the parent's re-measurement is now two independent reviewers
on the same subject, and it was created by the very change that closed the escape channels.

**Subjects at these locations, measured at the F09b closure** — the coordinate plus what it holds, which is
what makes a row checkable: `:143-150` the persona validator (`@field_validator("name",
"register_instruction")` / `_strip_non_blank`); `:466-470` the two `repr` fallbacks inside `_render`;
`:482-489` `_positive_seconds`; `tests/test_booth.py:1658-1670` the bounds list in
`test_every_bound_must_be_in_range`; `:299-303` the tolerant violation predicate `_CITATION_SHAPED`;
`:375-377` `_reference_scanner`'s compiled pattern; `:53-54` the module docstring's list of shapes left
airing; and `:288-294` (pre-F09b) the `cited` construction, the duplicate collapse and the empty-item drop.

**R3-004: closed inside the F09b unit by PIN, and this register had it wrong until the peer measured it.**
The row pointed at the pre-F09b `booth.py:288-294`, which held
`cited = tuple(dict.fromkeys(item.strip() for item in header[...].split(",") if item.strip()))` — that is the
**duplicate collapse** and the **silent drop of empty items**, a **coverage** subject, and the peer who owned
the unit closed it as such: the collapse is pinned by
`test_duplicate_citations_are_collapsed_and_their_order_is_preserved`, and the empty-item tolerance is pinned
with the reason that a dropped empty item cannot carry a reference that was never supplied. Both pass, and
both **passed before the change too** — they are pins, with **no RED**.
**This entry was wrong in its first form**, and the correction is worth more than the tidied text. It claimed
the location held the `MULTIPLE_CITATION_LINES` predicate, which in fact sits **one line above**, at
`:286-287`. The mistake was mechanical: a `sed -n '286,295p'` window was read as if it were the cited range.
That is the same class of error this register exists to catch — **a measurement that reads as verified
without being about the thing it claims** — and it survived because the surrounding story was coherent. The
unit's own review then placed a measured finding on the successor code, and the over-refusal the unit created
by widening its predicate is a **different** finding, registered above under its own location as a WARNING.
What the row needed was never a retirement narrative: it needed the closure **typed**, and a pin is not a
change.

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

**Subjects at these locations, measured** (and this file is unchanged since its review, so the coordinates are
current): `:123-128` the unreadable-JSON branch of `load_recorded_session`, the only place that puts a
decoder's own message into a `RecordedSourceError`; `:243-255` the client construction in `main`, which
happens **before** the corpus is read; `:286-316` the provider branches of `_model_client`, including the
gemini branch that materializes the credential and builds the SDK client with no timeout; `:168-173` the
version-segment derivation inside `native_base_url`.

One honest note about this unit: **the four F10-owned triggers in the tables above were reached by the same
commit**, and three of them did not fire, which is the reconciliation this register exists to force. F10
chose a dialect and a base URL, and it promoted nothing else: no bound, no timestamp and no timeout travelled
from configuration into the engine. That is recorded at the location of each entry rather than summarised,
because a reviewer of the register should be able to check the claim without trusting this paragraph.

## The committed lint configuration — every silence, with its trigger

`ruff.toml` is committed (F12, `dbcd58c`), so this table is the other half of that file's own obligation, stated
in its header: **the configuration is reviewable only when a reader can follow every silence to an owner.**
Counts measured on **`26dc06da` with ruff 0.17.0**, per rule **and per tree**, because the *shape* of an
exception depends on **where** the rule fires: a rule that only fires in one tree is **scoped**, not silenced
globally, so it still reports in the other. Two rules fire in both trees and are therefore global, and three
the rules inherited from the agent harness (`B008`, `SIM108`, `S311`, `S603`, `S607`) report **zero** here and
were **removed** from the ignore rather than carried: their inherited reasons came from `requests`, `pip` and
FastAPI, not from this repository.

| Rule | Count | `src/` | `tests/` | How it is silenced | Owner | Trigger that removes it |
| --- | --- | --- | --- | --- | --- | --- |
| **E501** | 809 | 279 | 530 | global `ignore` — it fires in both trees | whoever decides formatting policy | **adopting a formatter, or an explicit line-length policy**: without a formatter 809 long lines are not fixed by hand without noise |
| **S101** | 1552 | **0** | 1552 | **per-file, `tests/**` only** | the next writer to revisit test style | **running the suite under `-O`**, or any decision that makes test asserts load-bearing — that is when silencing them in tests would actually matter |
| **UP017** | 24 | 5 | 19 | global `ignore` — it fires in both trees | the next unit that edits an affected file | **that unit's diff**: the rename to `datetime.UTC` is mechanical and behaviour-equivalent, so it travels free; a standalone sweep would touch files outside any review context |
| **UP042** | 9 | 9 | **0** | **per-file, `src/**` only** | a unit that changes an enum's input or serialization surface | **that unit**, because `StrEnum` is **not** equivalent in `str()`, in formatting or in `isinstance` — it needs behaviour tests, and this is a different class from UP017 |
| **I001** | 2 | **0** | 2 | **per-file, `tests/**` only** | the next commit touching an affected file | that commit's diff |

The scoping was verified **behaviourally in both directions** by the parent on the delivered bytes, not accepted
as a declaration: a planted `assert` in `src/` **reports**, the same `assert` under `tests/` is **silenced**, and
the enforcement command run from the worktree root finds the committed configuration and passes. That check
matters because **asserts are compiled out under `-O`**: a globally silenced S101 would leave the one place where
it has real weight unwatched.

Two findings from the F12 review, both flagged by **two independent lenses** and therefore recorded with
special weight, neither of them fixed here because either would change the `ci.yml` bytes that were just
approved:

| Location | Ids | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `.github/workflows/ci.yml` | R3-no-job-timeout = R4-CI-TIMEOUT | OPEN finding, no body | the next commit touching that file | **that commit** adds `timeout-minutes` | OPEN — a job with no wall-clock bound can hang until the runner's own limit |
| the `ruff.toml` obligation sentence, and the enforcement step that does not exist yet | R2-register-obligation-unverifiable = R3-carried-register-unenforced | OPEN finding, no body | a small CI unit | **the five rows above existing — which this commit makes true** | OPEN, **trigger FIRED**: a step that fails when an ignored rule has no row cannot land before the rows, and it cannot ride this integration without changing the approved `ci.yml` |

## Cross-cutting, from verification rather than from reviews

| Subject | Where recorded | Owner | Trigger | Status |
| --- | --- | --- | --- | --- |
| Five probe-only cases from F03c-3a: empty checkpoint from a distinct prior stamp, checkpoint-await cancellation, direct-await KI/SystemExit, no-prior-watermark write failure, drivers immutability/mixed-session refusal | issue #8 | issue #8 | promoting probe-only coverage | OPEN |
| The F03c-4 generation branch is unreachable through the public API | issue #8 | issue #8 | deciding to reach it or to delete it | OPEN |
| Race coverage in the session lifecycle is scripted, not real concurrency | issue #8 | issue #8 | any change to the lifecycle, or a decision that real concurrency is needed | OPEN |
| A retried POST may be sent more than once — an unverified provider assumption | issue #9 | issue #9 | any live call, or a decision to exclude POST from the retry set | OPEN |
| The declared Python 3.12 floor is proven runnable but nothing enforces it | issue #7 | issue #7 | committing a CI matrix, or any dependency bump | OPEN |
| No lint configuration is committed, so every "clean" claim is scoped to an external harness file | issue #7 | — | — | **CLOSED** by F12 (`dbcd58c`): `ruff.toml` is committed with a pinned `0.17.0`, every silence is scoped and carries a row in the section above, and the **committed** configuration is now the yardstick. The agent harness's file remains a tool, not the measure |
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
