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
  **And the delta only decides THAT a file must be reviewed; the SUBJECT TOKEN is the only method to relocate a
  row.** That distinction was paid for in F09d: its change was **not additive** — the docstring grew, a function
  landed in the middle and the parse path changed — so the rows moved by **different** amounts, and the `+32`
  rule that happened to hold in F09c would have been **wrong for all eight** rows. A register that re-anchors by
  arithmetic rots whole on the first non-additive change, and this one is exactly that.
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
- **A check's DISCRIMINATOR must be a marker that only the intended failure produces.** The exit status is
  shared by **every** failure mode, including the ones nobody imagined, so a test that asserts only that
  *something* failed accepts a different failure in place of the right one. Two instances, one from each
  session: the F10 unit's provider-disagreement refusal went undetected because the test used a message-blind
  `pytest.raises(ValueError)` and the removed refusal fell through to the credential guard, which raises a
  **different** `ValueError` of the same type; and the CI guard's three failure tests assert the guard's **own
  prefix** (`register guard:`) as the discriminating marker, plus **no traceback** in the two cases where a
  `KeyError` could disguise itself — because a `KeyError` also exits non-zero. The general form, and it is the
  same shape as the staleness rule above: a **shared** signal says *something happened*; a **distinguishing**
  one says *what*. The line-count delta shares "something changed" and the subject token distinguishes what;
  the exit code shares "something failed" and the prefix distinguishes what. Added from the peer's synthesis,
  and it is the reason the F12b coverage unit exists at all: those three tests are the first ones in this
  repository that assert a CI failure by the marker that only that failure can produce.
- **A discriminator has TWO failure modes, and the repair is the same for both.** Too **weak**: a different
  failure disguises itself as the expected one (a `KeyError` also exits non-zero). Too **coarse**: a message
  from the **same** component passes because it shares the carrier (a generic guard message passes an assertion
  that only checks the `register guard:` prefix). In both cases the repair is to assert the **specific subject**
  - the rule, the register - instead of the shared carrier, which is the exit code or the prefix. **And the
  durability consequence nobody had written: adding a new message to a component can silently weaken an
  assertion that already existed**, because the new message can share the carrier. The assertion that was
  sufficient yesterday may not be today without anyone touching it, and the subject is the only thing stable
  against new paths. Measured twice in this round, the second time **above**: a mutant that replaced the
  refusal's subject with a generic phrase kept the prefix AND the exit code, survived the earlier review of the
  file, and only died once the assertion started naming the register.
- **The OBJECT of the claim determines the obligation.** Every rule above is one of two kinds, and the
  distinction is whether the thing exists yet. **A claim about existing bytes is measured before it is
  asserted, whoever the author is** - including when the claim arrives as a correction from the other session.
  **A candidate over bytes that do not exist yet is labelled as a candidate, given its experiment, and
  re-measured when those bytes exist**; demanding measurement earlier would be writing the fix first and
  measuring it after, which is circular. This round's three half-wrong corrections were all of the first kind
  made without running them - a record, two reviews, and a test - so they were not cases of *no obligation*:
  they were obligations **misclassified as such**. Corollary for reading a tool's own store: a record is
  trustworthy as an **execution** of the rule and never as **authority** - the allocator is a function of
  (tier, size) evaluated at a moment, while authority is tied to the bytes it covered. A record can be
  **dead authority and live data at once**, and the difference is not in the record but in the question.
- **The WRITE PATH decides the writer profile.** A change written through the structured tools carries the
  model that wrote it and the gate reads `runtime`/`large`; the **same change written by a shell command**
  (`printf`, `sed`, a heredoc) carries **no attribution**, falls to `fallback`/`small`, and the gate compensates
  by raising the tier **for verification** - the difference between being believed and being sent to verify.
  Measured in one worktree with one kind of change: shell -> `small`/fallback + `independentVerifier: true`;
  edit tool -> `large`/runtime + `false`. Material changes are therefore written through the tools, and that is
  a decision with a measurable price, not a style preference.
- **A child's reported artifact hash is a PRE-`agent_end` claim, and the harness rewrites the file after it
  was measured.** pi-lens autoformat is on by default with `format.mode` **deferred**, and its own
  documentation states that formatting for an `edit` is deferred to `agent_end` — which lands **after** the
  child has measured and reported its own hash, so a settled child's hash and diff size describe bytes that no
  longer exist. Measured **twice in one unit**: `+49/-2` reported against `+127/-21` live (`SHA 79074a10…`
  against `9ed90d6e…`), and `+32/-18` plus `+236/-0` reported against `+54/-31` and `+438/-64` live
  (`SHA 77809ffc…`/`24ad91a6…` against `f0fde318…`/`7f8993bc…`), with the first delta **proven AST-equivalent**
  (comment and whitespace reflow only) rather than argued. The discipline that follows, and it is not
  optional: the parent re-measures the artifact **after** the child settles, and acceptance, commits and the
  review candidate bind to the **parent-measured** bytes, never to a child's self-report. `--no-autoformat` or
  `format.enabled: false` removes the delta, but that is the operator's configuration decision and **no
  configuration was changed here**.
- **A committed range is measured with a CLEAN tree, and the leak has a DIRECTION.** The profile is read from
  the pending tool-written work the root holds **at measurement time**, even when the candidate measured is a
  committed range - so unrelated uncommitted work gives the candidate the profile of work *not in it*, and the
  verdict moves to `verifier: false`. **The contamination FAVOURS the candidate**, which makes it dangerous
  rather than merely imprecise: a distracted probe **under-verifies**. The general rule: **when the context of a
  measurement can only move the verdict in the permissive direction, the permissive verdict is the one to
  distrust.**
- **An assess plan belongs to the MEASUREMENT EVENT, not to the candidate.** The same range, with the same
  declared conditions, returned two different verification plans at two different moments. So a plan is cited
  **only for the run that produced it** - fresh, in the root where the work will land, on the bytes to be
  delivered - and **never as precedent**. A plan measured in one's own house describes that root and is not
  evidence of what the candidate needs to verify.
- **Measure facts now; name boundaries and defer them.** An assertion that enters this register as a **fact** is
  measured **now**. A **boundary** with no decision hanging on it is recorded **with its experiment named** and
  deferred - which is safe precisely because the experiment is named: a boundary without one is an assumption,
  with one it is a debt with a collection date. Both halves are auditable; an implicit criterion is not.
- **A rule found by two independent measurements is a rule; one two sessions agree on is a CONVENTION.** Until
  an independent measurement finds it, a one-sided claim stays a convention - including when the agreement is
  enthusiastic. Three rules from this round passed that test and all three share the property that makes them
  transferable beyond the case that produced them: **they name an ACTION, never an actor or an identity.**
  'Write with the tools' can be complied with on purpose; 'be the kind of writer who...' cannot. The F12c
  discriminator is the same shape: the marker had to be one that only the searched failure produces.

## Staleness keys

The blob OID of each file **at the revision its rows were recorded against**, next to the current one. A
difference means every row in that table must be re-derived by subject before its numbers are used; identity
means the coordinates are still the ones the reviewer saw. One command per row: `git rev-parse HEAD:<path>`.

| File | Blob at the recorded revision | Blob now | Verdict |
| --- | --- | --- | --- |
| `src/f1show/gemini.py` | `466db02b1977788c0faf3e6ffbd019a219c767fa` | same | **current** |
| `src/f1show/run.py` | `ee44616f94838abfd2e2d44ab83b7241b0c0c801` | `bd49f2f5901f6da408658db07cab999c0ccdfac7` (post-F09j, `043d2a5`, 400 lines) | **STALE — it read CURRENT at the previous revision**, and all four of its rows moved again when the loader gained the championship families. **A row that reads CURRENT is a measurement, not a promise** and the subject block below re-derived by SUBJECT at `bad0eba`**, where the shift is again not constant: `:123-128` → `:140-143`, `:243-255` → `:288-293`, `:286-316` → `:317-369`, `:168-173` → `:186-189`. The cell read `same`/`current` until F09f added the driver-directory family to the loader. **F09j moved it by exactly +1**, and the shape of that move is worth keeping: the unit's only change to this file is the loader docstring's sentence about `sessions.json` growing from two lines to three, so every tracked subject **below** it moved exactly one line and nothing above it moved at all — `load_recorded_session` stays at **`:121`** while `native_base_url` reads **`:189`**, `main` **`:279`** and `_model_client` **`:337`**. A shift that is constant below a point and zero above it is the case a blob key cannot express and a subject can |
| `tests/test_run.py` | `e4fd5317baf868bf0a6cfa76de238ff9dd2203b3` | `355190918c8b795876afd2f32717da621281a0c3` (post-F09i, `b0f5f32`, 1,326 lines) | **STALE by blob, and this time the row MOVED**: the reference-only matcher sits at **`:95`** with its comment at `:91-94`, and F09i added a **second** matcher beside it — `_PROMPT_IDENTITY` at **`:101`**, which is what teaches the offline double the start turn's bare-identity form. A new matcher with no row of its own is the same shape as the module-with-no-key this register already names, recorded here so it is not discovered twice Re-derived at `bad0eba`, at `2b52519` and again at `b325770`: the reference-only matcher now sits at **`:94`** with its comment at `:90-93`, where the first two derivations found `:92` and `:88-91`, so the earlier "UNMOVED" verdicts were true when they were written. **The correction is the interesting part**: the same blob key produced two unmoved verdicts and then a moved one, which is the measured demonstration that a key says only that the **file** changed — never whether a **row** did — and that only the per-row derivation can tell them apart. What moved here is the line and not the subject: the matcher still anchors on a bare reference line instead of the old `= value` form, and the `e4fd5317…` cell read `same` while being wrong before the F09e change |
| `src/f1show/auth.py` | `b1ab34d8f1b3cfff856ec7a4cbf2633cbbb2d8cc` | `51918e432e3b8ae617fb3a1f566b72a9a6193099` | **STALE — rows re-derived** (16 anchors with ids and subjects); the key stays different, correctly |
| `src/f1show/collector.py` | `a8a81ee93795b7934b32c715bfc47111770155c2` | `3973eb134e797bda1d7062cee357eb70bf69de9f` | **STALE — rows re-derived** (three already current, two moved one line, one closed by change); the key stays different |
| `tests/test_second_session.py` | `52ab0d942dcda0f9f0a86cfab584bbbd0543efed` (289 lines, recorded at its creation, `043d2a5`) | same | **current** — key and row added by the unit that created both the module and the corpus it pins, in the same closure, which is the repair recorded above; the second unit in a row to satisfy it instead of extending the list of omissions |
| `tests/test_auth.py` | `66e7e41e39640744de2670a7371c6226ce98258b` | `d9cda83a99a94e8b13da03c814baf1df54c7846e` | **STALE — its row re-derived and UNMOVED** (`:558-559` is exact); the blob over-flagged |
| `tests/test_collector.py` | `1b3123c684aab95ebf3ae1b9bfcc12b0941da7a7` | `7b4891758e49c00aded53413c85603e87ca169f6` | **STALE — row re-derived** (`:26-33` → `:27-34`) |
| `src/f1show/booth.py` | `a21d4d1d75e0a5c291b8bdf01183210127748bf5` (post-F09c) | `15054e1a0ce5d6d91fb0440a7dbe462bf3865c95` (post-F09i, `b0f5f32`, 1,192 lines) | **STALE — rows re-derived by SUBJECT for F09d, F09e, F09g/U1, F09g/U2, F09g/U3b, F09h and now F09i**, where the shift is **not constant** (the docstring grew, a function landed at `:443`, the parse path changed) — which is the case that makes the subject the only workable key. Re-derived **a third time for F09f** (the prompt render changed and the parse path moved again), again by subject. **Re-derived once more for F09h** with a read-only explorer: this time the shift **is** constant — **+26** for every subject above the prompt block and **+41** inside it — and that exception is recorded as such, because the per-row list below still gives each located coordinate and **one row did not follow the arithmetic**. **F09i then broke the arithmetic again, in two places on purpose** — the scanner gained an alternative (R1-001's fix) and the walk gained the group branch and the coverage rule (R1-002's and R3-covered-without-start's fix) — so the located list below is the only usable form |
| `tests/test_booth.py` | `cc65c60e8926df10112e6ac3e7834e1bc1a535ba` (post-F09c) | `fb894a0a78f5c779a85fab8fd8d4ae298421ffad` (post-F09i, `b0f5f32`, 3,546 lines) | **STALE — rows re-derived again and they moved by +89** with the start section and the review-fix tests: the bounds guard is at **`:2985`** with its cases at `:2975-2982`, the shape-5 `space` case at **`:2273`** (`id` at `:2270-2274`) and the module-binding test at **`:1300`**/`:1302`. **Two of the numbers the previous cell carried were already wrong when they were written** — it claimed the bounds guards sit at `:2618` and the shape-5 case at `:1903-1907` "exactly where the previous derivation left them", while at the very revision it describes those subjects are at **`:2643`** and **`:1931`**, the coordinates the **table beside it already recorded**. A cell can be wrong while the table it summarises is right, so only the per-row search settles either |
| `src/f1show/start.py` | `5200acae3d8b56befe6e43b092c14bcef348fb55` (117 lines, recorded at its creation, `b0f5f32`) | same | **current** — key and row added by the unit that **created** the module, which is the procedural repair this register names for itself: a unit that creates a module must add its staleness key and its row **in the same closure commit**. F09i is the first unit since that repair was written to satisfy it instead of becoming its fifth instance |
| `tests/test_start.py` | `227454a9f153e32db8f7fe65a3abfcbfd76d4336` (197 lines, recorded at its creation, `b0f5f32`) | same | **current** — same closure, same repair, and the same satisfaction of it |

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

## The review budget, measured - and where it stops being known

The correction budget is not the review threshold: they are **two knobs**. The **tier decides whether a review
happens at all** (F12b was reviewed at 94 lines because it was high, not because it was large); the **size
decides the budget**, and whether `slice_budget_reached` fires. Measured deliveries, cited as the triple
**(tier, lines -> budget)** and **never by their delivery state**, because the same record can be dead authority
and live data:

| tier | lines -> budget |
| --- | --- |
| high | 94 -> 47, 264 -> 132 (**all below the ceiling**) |
| medium | 288 -> 200*, 350 -> 200*, 968 -> 200, 991 -> 200, 1340 -> 200 |

*The first two are `under_budget` points whose budget was not read; they are listed for the threshold, not for
the budget.*

**What is measured, part by part, so that nobody reads the formula as a measurement.**
`budget = max(2, min(ceil(lines / 2), 200))`: the **half** is measured in both tiers (94 -> 47 and 264 -> 132 on
the high side; 968 and 991 arrive already capped on the medium side); the **ceiling of 200** is measured in
**medium only**, because every capped case is medium and the high-tier data never reached it; the **floor
`max(2, ...)`** is inferred from the policy name `floor_two`, not measured; and the **rounding direction** is
not measured either, since the two uncapped points are both even and both odd ones sit above the ceiling.

**And tier and size are CONFOUNDED in every point we have**: every high point is small and every medium point
is large, so no point varies them separately and **any tier-scaling is invisible - in the `min` and in the
threshold alike**. The honest form of the threshold claim is therefore **"measured within medium: (350, 968];
the high side is not measured at all"**, not "the band narrows".

**Four boundaries, named with their experiments and deliberately not run**, because no decision hangs on them
today: (1) a **medium** unit above the threshold and below the ceiling (~350 lines -> 175 if the half is
tier-independent) - the most informative and a *normal* unit, so it may happen by itself; (2) a **high** unit
above the ceiling (~600 -> 200 if the ceiling is tier-independent); (3) a point with an **odd** number of lines
below the ceiling, for the rounding direction - the only artificial one; and (4) **the threshold on the high
side, which is only observable through `reviewDueReason`**, because a high candidate is reviewed regardless - a
large CI batch settles it at zero cost, and the reading rule for that datum is **pre-registered**:
`slice_budget_reached` means the threshold runs for high and the splitting criterion is capacity AND threshold;
only the tier's signal means it is a medium notion (or masked), and the criterion is capacity alone.

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
| `:256-262` | R3-005 (integration) = R3-persona-validator-uncovered (unit) | SUGGESTION | issue #8 | promoting probe-only coverage, or any change to the personas | OPEN |
| `:632-643` | R3-001 and R3-003 (integration) = R3-render-repr-determinism (unit) | SUGGESTION | F13 | **an evidence value that cannot be serialized reaches the prompt** — a data event, or a change in F04's contract | OPEN, with the fix already decided below |
| `:655-664` | R3-002 (integration) = R3-positive-seconds-overflow (unit) | SUGGESTION | whoever sources a bound from configuration | **the F10 trigger did NOT fire**: `main` calls `run_session` without the bound parameters, so they keep their signature defaults. The composition wiring shipped without promoting a single bound into configuration | OPEN |
| `tests/test_booth.py:2643` | R3-006 (integration) = R3-bound-guards-uncovered (unit) | SUGGESTION | issue #8 | any change to the bounds list | OPEN |
| `:413-417` | R3-bullet-commentary-false-refusal (F09b unit) = R3-marker-word-false-refusal (integration review) | **WARNING** | — | — | **CLOSED by change** (F09d, `e39c5f9`) — the first row here closed by a **behaviour** change under the user's authorization, and it is worth its own paragraph below |
| `:76-81`, the module docstring's accepted cost | the residual over-refusal — a declared cost rather than a finding, so no review id | declared cost | whoever weighs it at the live trial | **the first live trial showing this refusal repeated enough to cost retries** | **DECLARED, not hidden**: a marker-shaped line naming a **supplied** reference in prose (`Evidence: position[0].position shows P3.`) is refused too, because it is *byte-shaped exactly like a second citation and no structural test separates* the two; the docstring states that closing it would mean **trading away one of the four escape channels**, and that a model can rephrase trivially, so the cost is a **retry rather than a lost claim**. Measured by the parent: it does refuse, and the declaration is in the module docstring |
| `:489-491` | R3-bracket-continuation-leak (F09b unit) | **WARNING** | the next unit touching the scanner, or a live transcript showing a fragment | a fragment of a never-supplied reference airing in an aired turn | OPEN, **now a DECLARED shape** rather than an undeclared one — see the closure below |
| `:117-152` (was `:53-54` pre-F09c; subject `**Six shapes are deliberately left airing**` at `:117`, `Shapes 5 and 6` at `:148`) | R3-docstring-omits-bracket-fragment-leak (integration review) | SUGGESTION | — | — | **CLOSED by declaration and pin** (F09c, `bde8d5f`) — see below |
| `:116` | R3-doc-stale-leak-placement (F09c review) | SUGGESTION | the next unit touching the scanner's docs | any change to the docstring's boundary sentence | OPEN — the noun is stale (see the notes); **still open after F09d moved it**, because the sentence that uses *placement* for the character question is still the same sentence |
| `tests/test_booth.py:1928-1932` (id at `:1931`) | R3-shape5-whitespace-tolerance-scope (F09c review) | SUGGESTION | the next unit touching the scanner or its declaration | any change to the `space` parameter's id or comment | OPEN — the label and the measured discriminator disagree (see the notes) |
| `:530-531`, the `scanner is None` branch — reported by its lineage at `:460-463` | R3-kept-refusal-coverage (F09d review `review-6023526de250aed1`, tier medium, one `review-reliability` lens, candidate tree `c091a324`, **burned** with `consumed_revision sha256:e3145025a77c3dc70e5abeab18901dc344906150d2bdcb77106aa7c11fdcdbb9`) | informational, no body | the next unit touching the scanner | any change to the scanner's derivation | OPEN — exercised **only by direct call**, never end-to-end. That is **inherent** and the test declares it open: the collector's grammar never produces a reference without `<family>[<index>].<field>` structure, so the branch that stays **fail-closed** cannot be reached through the public path |
| `tests/test_booth.py:958` and `:960` — reported by its lineage at `:663` | R3-module-binding (F09d review `review-6023526de250aed1`, tier medium, one `review-reliability` lens, candidate tree `c091a324`, **burned** with the same `consumed_revision`) | **WARNING** | the next unit touching that test | any rename or re-export of the private symbol | OPEN — the test reaches the new private function through `f1show.booth._is_citation_attempt`, so it couples to the **package's attribute surface** instead of importing the symbol, and a **binding** failure would read as a **behaviour** failure |
| `_prompt`'s EVIDENCE block, and the citation acceptance | the live-model citation-form finding — the **first live observation of the model's output style** | **WARNING** by consequence, measured | the unit that touches the prompt or the acceptance | **fired**: this *is* the live observation, so any unit touching `_prompt` or `_parse_answer` | **CLOSED by change for its deterministic half, with no new live datum** (F09e, integrated as `fe4dda3`; native review `review-64713b02cce78401`, tier medium, one `review-reliability` lens, approved and burned): the prompt no longer renders a reference and its value on one line (`_prompt` `:923`, values split `:971-979`) and a copied `reference = value` is cut at its **first** `=` **before** the comma split (`:594`), so a comma-bearing copied value no longer manufactures citation items — three RED cases on list, dict and comma-bearing string values, ten new cases in total, focused 133 and full 821 green on the reviewed bytes. **Its live-rate half stays historical and unmeasured**, because no post-fix live run exists and none is authorized — measured live on 2026-10-11 over 206 model calls (the start → lap 5 window of the recorded Austin 2024 race, `gemini-3.5-flash-lite` through the operator's gateway): the model **copies what the prompt shows, at three different levels of fidelity**. **58** calls cited the **listed reference** (`laps[1].lap_number`) and aired; **93** cited the **event identity** (`laps[3]`) and aired **only because the probe normalised them**; **55** copied the reference **with its value** (`laps[6].lap_duration = 105.091`), exactly as the EVIDENCE block prints it, and were **refused as `invented_reference`** because the acceptance expects the bare reference. **So with the shipped protocol only 58 of 206 events (28%) can air**, and the cause is the prompt: the same block teaches `- <reference> = <value>` while the instruction says *exactly* `EVIDENCE: <reference>`. **Two candidate fixes, both product decisions**: print the reference unambiguously (value on its own line, or a delimiter that cannot be read as part of it), and/or accept the two faithful variants (the identity and the reference-with-value). The probe's normaliser is a **probe, not a fix** — it changed nothing in the repository |
| the acceptance cut at the first `=` (`:594`) and `_prompt`'s EVIDENCE/values split (`:923`, `:971-979`) | `R3-copy-shape-truncation` (F09e review `review-64713b02cce78401`, tier medium, one `review-reliability` lens, candidate tree `5c1f0748…`, **approved and burned**, `consumed_revision sha256:d663513e…`) | SUGGESTION, informational, no body returned | the next unit touching the `=` handling or the acceptance boundary | any change to the first-`=` cut, to the comma split, or to a reference used right of an `=` | OPEN — the approved review recorded it as **non-blocking** and opened no correction. Measured context, so the next reader need not re-derive it: the cut means a reference-shaped token **right** of the `=` is ignored rather than validated, a second **supplied** reference right of the `=` is **not attributed**, and a **supplied** reference used as the right-hand value has **no pin** — the pins cover the unsupplied shape (`tests/test_booth.py:1191`) and the identity case (`:1246`), with the comma-value RED at `:1129` |
| `:590-595` | `R3-001` (F09f review `review-1383183dff9c8a08`, tier medium, one `review-reliability` lens, candidate tree `442552a9…`, **approved and burned**, `consumed_revision sha256:4297a9c7…`) | **WARNING**, informational, no body returned | the next unit touching the acceptance path | any change to the header parsing around the first-`=` cut | OPEN — an advisory finding from an **approved** review: it opened no correction and the review offers none. Subject located by the parent, since the harness returns ids and locations but never bodies: the `cited_text` cut block, whose comment and `partition("=")[0]` both sit inside this range |
| `:594` | `R3-003` (same lineage) | SUGGESTION, informational, no body returned | the next unit touching that cut | any change to the line that partitions the header | OPEN — same approved review; the located subject is `cited_text = cited_text.partition("=")[0]` |
| `:689` | `R3-002` (same lineage) | **WARNING**, informational, no body returned | the next unit touching the booth constructor or its parameter validation | any change to that parameter or to its validation | OPEN — same approved review; the located subject is the new **required** `driver_directory: Mapping[int, tuple[str, str]]` parameter, which is the only line this unit added to the constructor signature |
| `mode.py:177-184` | `R3-case-handling-asymmetry` (F09g/U2 review `review-4bfd2fcf3ea2e4f2`, tier medium, one `review-reliability` lens, candidate tree `7eeaf198…`, **approved and burned**, `consumed_revision sha256:48bbad8a…`) | SUGGESTION, informational, no body returned | the next unit touching the caution signal | any change to how caution names or flags are matched | OPEN — subject **located by the parent** in the source: the case handling in the caution matching, which is asymmetric between the flag names and the message text |
| `mode.py:157-161` | `R3-unstripped-text-helper` (same lineage) | SUGGESTION, informational, no body returned | the next unit touching that helper | any change to the text normalisation used by the caution signal | OPEN — subject **located**: the small text helper that reads values without normalising surrounding whitespace |
| `booth.py:228`, `PRIORITY_EVENT_TYPES` | `R3-stale-band-export` (same lineage) | SUGGESTION, informational, no body returned | the next unit touching the band or the module's public surface | any change to `booth.__all__` or to the alias | OPEN — subject **located**: the band's **old public alias** still exported as `PRIORITY_EVENT_TYPES = CAUTION_EVENT_TYPES` while the real declaration lives in `mode.py`, so a reader of the package surface names a set that is no longer defined here. The register keeps it rather than deleting the earlier row, because an alias that survives a refactor is exactly how a dead name outlives its subject |
| `standings.py`, the tie rule (`order_standings`) | `R3-tie-order-not-derivable` — measured by U3a; the F09g/U3a review (`review-f0762d68ec5e9f68`) opened **no** findings | — | the next unit touching the derivation, or any future attempt to reproduce the source's tie order | any change to the tie rule, or a source that publishes its own tie-break | OPEN — the order **within a points tie is not derivable** from the recorded fields: a `driver_number` rule disagrees with the source's `position_current` on **8 rows** and a `position_start`-stability rule still on **2**, across four tie groups. Declared and pinned, and deliberately **not fitted** to the data; and as of U3b the **render states the tie** instead of asserting a settled position (**470 of 1,648** turns reworded, the other 1,178 byte-identical), so the limitation is no longer silent in the prompt |
| `tests/test_championship.py:564` | `R3-1` (F09g/U3b review `review-7438f42ae5527361`, tier medium, one `review-reliability` lens, 6 files, **1,966** lines, **approved and burned**, `consumed_revision sha256:8610deab…`) | **WARNING**, informational, no body returned | the next unit touching the championship tests | any change to that region | OPEN — subject **located by the parent** in the source: the assertion that no bracket-family character appears in the rendered block, and what it does **not** cover |
| `src/f1show/run.py:72-85` | `R3-2` (same lineage) | **WARNING**, informational, no body returned | the next unit touching the loaded-family contract | any change to `_CHAMPIONSHIP_FAMILIES`, `_LOADED_FAMILIES` or the loader | OPEN — subject **located**: the declaration of the loaded families and the comment that describes it, which is where a silent contract change would land |
| `tests/test_championship.py:709-715` | `R3-3` (same lineage) | SUGGESTION, informational, no body returned | the next unit touching the championship tests | any change to that counting loop | OPEN — subject **located**: the blast-radius counter that measures how many turns state a tie, which is the test that keeps the 470 figure honest |
| `championship_teams` against the driver rows | `R3-team-table-not-derivable` — measured by U3a, no review saw it | — | any unit touching championship **team** standings | any attempt to derive team standings from a session's entry list plus driver rows | OPEN — global totals agree at **2078.0**, but per team the source sits above the driver sum by **Ferrari 6, Haas 1 and RB 12**, exactly the **19** points held by the three drivers with no entry-list row. Two measured reasons: the entry list is **session-scoped**, and the driver table carries **one** team per driver per session, so a season scored across two teams cannot be expressed. **The season team table must come from the source's own endpoint**, and the numbers nevertheless determine the split uniquely |
| `src/f1show/standings.py` and `tests/test_standings.py` | staleness keys added at the U3a closure, because the register had **no key and no row** for either: `bd20acc1dc396a085b7183994eada9445d258b0d` (402 lines) and `4719cd18830ab9cca8ca7e870d3bc4363de4aa9d` (551 lines) at `6a07cda` | — | the next unit touching the derivation | any change to either file | NEW — and this is the **third** time in **one** feature that a module entered the tree with no key at all, after `salience.py` and `mode.py`. Three occurrences stop being an oversight and become a **gap in this register's own closure procedure**: nothing in the per-unit routine forces a new file to acquire a key, so the omission is named here as a procedural finding rather than repaired silently a fourth time |
| `:454-455` | `R3-empty-context-misstates-lap1` (F09g review `review-435383adf7953268`, tier medium, one `review-reliability` lens, candidate tree `f1ead79f…`, **approved and burned**, `consumed_revision sha256:7d359732…`) | **WARNING**, informational, no body returned | the next unit touching the CONTEXT block | any change to how an empty or story-less window is described | OPEN — subject **located by the parent** in the source: the prose the renderer emits when the window carries no story |
| `:475-485` | `R3-pit-flag-prose-unbounded` (same lineage) | SUGGESTION, informational, no body returned | the next unit touching the renderer | any change to how pit stops and flags are listed | OPEN — subject **located**: the pit and flag prose lines, which list every stop and every flag the window holds and are therefore unbounded in a long race |
| `:414` (the review reported `:415`) | `R3-salience-median-overflow` (same lineage) | **WARNING**, informational, no body returned | the next unit touching the outlier rule | any change to the median or the fence arithmetic | OPEN — subject **located**: the median computation over the window's valid laps |
| `booth.py:228`, `PRIORITY_EVENT_TYPES` | the **dead priority band** — found while mapping F09g, no review has seen it | — | **U2**, or the next unit touching seat priority | any change to race-control derivation or to the priority band | OPEN — replaced by U2: `PRIORITY_EVENT_TYPES` now exists at `booth.py:213` as `PRIORITY_EVENT_TYPES: frozenset[EventType] = CAUTION_EVENT_TYPES`, imported from `mode.py` at `:184` and still listed in `__all__` at `:196`, and `_speaker_for` consults `announces_caution`, so the band is no longer dead. **SUPERSEDED as a defect, and deliberately kept as a row** because the old literal set it quoted no longer exists: what remains open is the **stale public alias**, now carried as `R3-stale-band-export` below. U2's own measurement is the closure: under the base booth the seats equal strict alternation, and under U2 they change in 1,023 of 1,648 turns |
| `_prompt` `:923` and the `render_salience(...)` call at `:987` | the **CONTEXT block** (U1; no review row existed for it) | — | the next unit touching the prompt | any change to `_prompt` | OPEN — the live citation-form row's trigger **re-fired** with this unit, and its live half stays historical. **It fired a second time** with the START-block unit, which changed `_prompt` (a declaration emitted for the start turn only) while leaving the CONTEXT block itself untouched: the subject is unmoved and the row stays OPEN |
| `src/f1show/salience.py`, `tests/test_salience.py`, `src/f1show/mode.py`, `src/f1show/standings.py`, `tests/test_standings.py`, `src/f1show/championship.py` and `tests/test_championship.py` | staleness keys added at their own closures, because the register had **no key and no row** for any of them before, and each key is the **full blob OID** as the rule requires: `salience.py` `c7fe58a9bbb93eeaed595a86d0b09fc96e779043` (611, current), `tests/test_salience.py` `d912d8bf6a931ddcf9e8cf2133a500200378efda` (1100), `mode.py` `a7604d04455d412200c172e85d70f9f8efa9900d` (248, current), `standings.py` `bd20acc1dc396a085b7183994eada9445d258b0d` (402, current), `tests/test_standings.py` `4719cd18830ab9cca8ca7e870d3bc4363de4aa9d` (551), `championship.py` `c547205296236ab4df016a73ad5f2552202d0507` (700) and `tests/test_championship.py` `48ac7b246f35d6144d9bb58367f22a897e6560d0` (724) | — | the next unit touching any of them | any change to any of those files | NEW — and by the end of F09g this happened **four** times in one feature (`salience.py`, `mode.py`, `standings.py`, `championship.py`). Four occurrences are a **defect in this register's closure routine**, not four oversights: the per-unit procedure says to re-derive rows and update keys for files that **changed**, and nothing in it forces a **newly created** file to acquire a key. The repair is therefore procedural and is stated here for whoever owns the next closure: a unit that creates a module must add its staleness key and its row **in the same closure commit**. **At F09j's closure the `championship.py` blob moved to `9466e8f45788875c3c3346b9a0ac4d88122aff71`** (703 lines) because the declared-season comment had to name **both** recorded sessions; every tracked subject below that comment moved by exactly **+3**, measured on two anchors (`RECORDED_SEASON` `139` → **`:142`** and `build_championship_source` `265` → **`:268`**), and nothing above it moved |
| `tests/test_ci_config.py`, the property-naming comments | F12e's m4 survivor | — | — | — | **COVERAGE NOTE, and an expected one**: deleting a property-naming comment leaves **803 passed**, because prose has **no mechanical net**. Recorded so nobody reads the class closure as a test-enforced invariant: the class was closed by a **declaration with a measurable criterion** (a scan for the unit-citation tokens returns zero), not by an assertion |
| `tests/test_ci_config.py`, the imports block | R4-1 (F12c review) | **WARNING**, body unrecoverable | — | — | **CLOSED by characterisation, with the reason written**: the subject **admits no defect today** — every import is used and the grouping is correct (`__future__`, then stdlib, then third-party). Two measurers counted the usages slightly **differently** (`tomllib` 4 versus 2) and both concluded the same; the **counts are not the evidence, the usage is**, which is why this row cites no number. The residual is honest: an assertion whose **subject was something else on that line** cannot be recovered, because the harness returns ids, severities and locations and **never bodies** |
| `tests/test_ci_config.py`, the mirror comparison | R4-3 (F12c review) | **WARNING**, body unrecoverable | — | — | **CLOSED as obsolete by the previous refactor, with the reason**: the comparison moved into `missing_register_rows(config_text, register_text)` — a **named two-text function whose failure direction is exercised** — so the condition a readability assertion could describe there (a comparison buried in a test body with only its passing case run) **no longer exists in that form**. As a location the subject token is gone; that is the reason, not "no longer applies" |
| `tests/test_ci_config.py:55`, the key-line pattern | the `a:b` inner-colon escape — found by the parent's verifier, no review saw it | — | the next unit touching the **key reader** | that unit | **OPEN, and it is a SIBLING of the closed charset row for a different reason**: an inner-colon key (`deploy:prod`) is valid YAML as a block-context plain scalar, it fails the key regex **entirely** rather than being filtered, and so **both scans miss it** on planted workflows. Planting it in the shipped `ci.yml` **is** caught (a test counts the key lines the scans do not read), so the delivered file is closed and the escape lives at the **scan level over planted texts**. **A measured candidate fix exists**, recorded as the peer's measurement and labelled a **candidate over future bytes** — to be re-measured when the unit is written, never cited as fixed: the permissive key-line pattern `(?m)^  ([^\s#].*):$` reads `deploy:prod` and the charset predicate then rejects it |
| `tests/test_ci_config.py:373-386`, the charset test | the parent verifier's survivor — **refuted by the peer, then re-confirmed by measurement** | — | the next unit touching that test | any change to that test | **OPEN as a coverage note, in the precise form the two sessions converged on**: the assertion is **VACUOUS over the real tree** (every real key conforms, so `offenders` is empty and the assertion passes without looking) **and no other test calls it**, so neutering its body leaves **19 passed**. The peer claimed the planted test caught it; measured, it does **not** — the planted test computes the predicate **inline** and its control is about another **planted** workflow. The defect **class** is carried elsewhere: the planted test for the underscore and uppercase shapes, and the counting invariant for shapes that make `job_keys` return **fewer** keys than exist. **And the vacuity is a property of the TREE, not of the test**: it exists because the tree conforms |
| `tests/test_ci_config.py`, four comments in the middle of the file | R2-assignment-context-leak **as a CLASS** — found by the peer's subject-token re-derivation, which also produced four DIFFERENT offsets (`+7`, `+32`, `+90`, `+89`) | SUGGESTION | — | — | **CLOSED by F12e (`879e3b5` → integrated `5923015`), four instances to zero.** The criterion, fixed by the parent after the peer proposed the boundary: **the class is citing the UNIT** — `this unit`, `the assignment this unit`, `the two-line fix`, `Until now` — a referent that **dies at the merge**; whereas citing a **measured state of the code IS evidence**, and fully so when it **names the revision**. That is why the four instances are closed and the **five state-citations stay** (`:144`, `:236`, `:360`, `:413`, `:449`), each verified by the parent's verifier as a state-citation rather than a unit-citation. Each replacement names the property it protects: the exit code cannot tell a refusal from a crash; a config with no `[lint].ignore` makes the guard check a **subset in silence**, which is the false-green mechanism; the refusal must be **the guard's own** |
| — | R3-positive-seconds-overflow | SUGGESTION | — | — | **promoted, not dead**: F10 shipped and the bound is still a constant, so the entry above stays OPEN under its original condition |

**And its registered trigger fired on 2026-10-11, with a NEGATIVE result worth recording**: the first live trial that observes the model's output style produced **206 samples**, and **not one** `MULTIPLE_CITATION_LINES` refusal — the model never opened a line with the marker's own word as prose, so **the over-refusal did not bite**. What bit was the **citation form** (the row above this section). The closure stands on its own evidence; this adds that the condition it was registered against has now been looked for and not found.

**The first row here closed by a BEHAVIOUR change, and it is the one the user authorized.** `R3-bullet-commentary-false-refusal` = `R3-marker-word-false-refusal` is **closed by change** in F09d (`e39c5f9`): the violation predicate now requires the marker **and** a remainder that carries a reference-shaped token — the scanner's own principle, *the guarantee is about tokens, not lines*. Measured by the parent on the integrated bytes:

- **all five false refusals AIR** — the unbulleted marker word, the bullet form, the lowercase form, the exact marker, and the bullet plus exact marker;
- **all four channels stay REFUSED**, each with the test that covers it rather than "the suite": the bullet-prefixed channel and the space-before-the-colon channel by their own named tests under `MULTIPLE_CITATION_LINES`, and the mid-line mention and the bare reference by the **content rule** under `UNSUPPLIED_REFERENCE_IN_TEXT`, which was **not touched**;
- the deliberate pins still air: the mid-sentence marker mention, and a supplied reference in prose.

**The classification of the five is the parent's earlier measurement and it survived**: **A and D were already refused before F09b**, while **B, C and E were introduced by F09b's tolerant predicate** — so this unit fixed two failures that **predated** it and three that it **caused**, and the unit's own measurement added two cases to the three the parent had.
**And the layering held when the check was neutered, which the unit's verifier measured rather than assumed**: channels 1 and 2 do **not** re-open as turns — they escape the predicate and the **content rule** catches them with a **different** reason — and the channel that does re-open is a second citation carrying a **supplied** reference, whose pin then failed with the turn emitted. That is **stronger** than the expectation written into the assignment, which said channels 1 and 2 would re-open.
**A probe of mine was wrong, and it is this round's error class again**: checking whether the docstring declared the residual, I grepped for phrases **reconstructed from the peer's message** ("accepted cost", "byte-identical") instead of reading them from the file, and both returned false. The declaration is there at `:48-54`, worded *"byte-shaped exactly like a second citation"*. **A reconstructed string is not an observation** — including inside a check written to verify someone else's claim.

**The F09d unit moved the coordinates again, and this time the shift is NOT a constant — which is why the re-derivation is by SUBJECT and not by arithmetic.** `booth.py` went 795 → **843** lines and `tests/test_booth.py` 1810 → **1894**, but the insertion is not one block: the module docstring grew, a **new function** landed at `:443`, and the parse path changed, so rows moved by different amounts. Each coordinate below was found by locating the token recorded as that row's subject — `_strip_non_blank` 175→191, `_CITATION_SHAPED` 331→346, the scanner's compile 407→422, `default=repr` 500→548, `def _positive_seconds` 514→562, the word *placement* 56→70, the bounds guards 1795→1879, the shape-5 `space` case 1124→1210 — **eight of eight located**, and the +32 rule from F09c would have been wrong for every one of them.

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
**Re-derived once more at the F09e integration** (`fe4dda3`, `booth.py` `d6e56ea8…` 917 lines, `tests/test_booth.py` `34ef0009…` 2433 lines, `tests/test_run.py` `8aaa35e8…` 749 lines), every row located by its own token and not by arithmetic, and the shift was **again not constant**: the table above carries the new coordinates, `tests/test_run.py:92` is the reference-only matcher, and `tests/test_booth.py:2418` is the bounds guard.

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

**The F09h re-derivation, by SUBJECT, at `a8fbe981`** — a read-only explorer searched every coordinate in this section for its own token. **Thirty-one located, four not**, and both categories carry information.

*The ones that did **not** move.* Three coordinates are still the reviewer's, because this unit touched nothing above `:236`: `R3-doc-stale-leak-placement` (`:116`), the six-shape docstring anchors (`:117` and `:148`) and `R3-stale-band-export`'s alias (`:228`).

*The ones that moved, and by how much.* The module gained a **26-line** profile registry at `:236` and the prompt gained **15** lines at `:972`, so the shift is **+26** for every subject above the prompt block and **+41** inside it — measured on five anchors (`_strip_non_blank` `258→284`, `_CITATION_SHAPED` `413→439`, `default=repr` `641→667`, `_positive_seconds` `655→681`, `_prompt` `923→949`). Each row was nevertheless located by its **own token**, never by that arithmetic: `:256-262` → `:282-288`; `:632-643` → `:658-669`; `:655-664` → `:681-690`; `:413-417` → `:439` (predicate `456-458`, used at `554`); `:76-81` → `:76-83`; `:489-491` → `:526-533`; `:117-152` → `:117-157` (start and the *Shapes 5 and 6* anchor unmoved, tail grown); `:530-531` → `:556-557` (docstring `548-552`); `:594` → `:620`; `_prompt` `:923` → `:949` and the values split `:971-979` → `1012-1026` (heading `1018`, values `1020-1026`); `:590-595` → `:616-620`; `:689` → `:715` (the required `driver_directory` parameter); `:288-294` → `:621-623` and `:286-287` → `:613-614`; the `render_salience(...)` call `:987` → `:1028`; the scanner compile `:407`/`:422` → `:492`/`:515`; the `mode` import `:184` → `:198` and `__all__` `:196` → `:208`; `tests/test_booth.py:2643` → `:2739-2752` (cases `2742-2749`, def `2752`); `tests/test_booth.py:1658-1670` → `:2742-2749`; `tests/test_booth.py:2418` → `:2752`; `tests/test_booth.py:1928-1932` (id `:1931`) → `:2038-2041` (id `:2040`); `tests/test_booth.py:958`/`:960` (lineage `:663`) → `:1067`/`:1069` (test def `:1055`); and the three copy-shape pins `tests/test_booth.py:1191`/`:1246`/`:1129` → `:1520`/`:1238`/`:1362`.

*One row did **not** follow the arithmetic, and it is named rather than smoothed.* `R3-bracket-continuation-leak`'s recorded `:489-491` locates the attached-bracket rule at `:526-533`, which is **old+37** and not old+26: the extra movement belongs to the F09e parse-path change this register already records, so the located coordinate is the one that stands.

*Three rows in this section were never in this file.* `R3-empty-context-misstates-lap1` (`:454-455`), `R3-pit-flag-prose-unbounded` (`:475-485`) and `R3-salience-median-overflow` (`:414`, the review reported `:415`) are **salience** findings whose bare coordinates read as `booth.py`; their subjects are at `salience.py:453-454`, `salience.py:473-485` and `salience.py:414`, and searching them in `booth.py` finds only a docstring mention at `:966` and the call at `:1028`. The rows stay where they are and this note supplies the file, because relocating them silently would hide that a section titled *booth.py and its tests* has been carrying three rows about another module.

**F09h's three advisories, carried with owner and trigger; subjects located in the source because the harness returns no bodies.**

| Location | Ids observed there | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `README.md:67-86` | `R2-language-vocabulary-triple-duplication` (F09h review `review-6cf74ab2e4847bc4`, tier medium, two lenses `review-readability` + `review-reliability`, 6 files, **319** lines, candidate tree `733e2c80…`, **approved and burned**, `consumed_revision sha256:377e9325…`) | SUGGESTION, informational, no body returned | the next unit touching the commentary language | a change to the lexicon in any of its three homes — this README table, `booth.py`'s `_SPANISH_LANGUAGE_PROFILES` or `docs/ARCHITECTURE.md` | **OPEN** — the subject is located: the same vocabulary is stated in three places, and only the middle one is pinned by a test, so a change made in one home is invisible to the other two. Nothing is duplicated **wrongly** today, which is why this is a suggestion and why it opened no correction |
| `src/f1show/booth.py:977-987`, located at the `""` sentinel on `:981` | `R2-spanish-profile-blank-line-sentinel` (same lineage) | SUGGESTION, informational, no body returned | the next unit touching the prompt's `LANGUAGE:` block | any change to `language_instruction`'s tuple | **OPEN** — located in the source: the tuple's **first element is a literal empty string** whose entire job is the blank line that separates the block from the instruction above it. Nothing names that purpose; the boundary is asserted from the outside by the tests instead, so a later editor who deletes the element as noise changes the prompt's shape rather than its instruction |
| `src/f1show/booth.py:977`, located at the lookup on `:976` | `R3-exact-match-language-profile-lookup` (same lineage) | SUGGESTION, informational, no body returned | the next unit touching the language profiles | any change to `_SPANISH_LANGUAGE_PROFILES`' keys or to the configuration's language normalisation | **OPEN, and measured here**: the lookup is an **exact** dictionary match and the configuration **strips but does not case-fold** the value. Measured with the shipped fakes and an injected clock: `es-AR` builds a prompt that carries the `LANGUAGE:` block, while `ES-AR`, `es-ar` and `es_AR` all pass validation, reach the prompt as written and produce **no block at all** — a silent fallback to the free-form instruction, with the asked-for spelling still recorded as the transcript's `language` |

**Two changed files have no key and no row at all, which is a *different* gap from the one this register already names.** `src/f1show/config.py` and `tests/test_config.py` both changed in F09h — the language default is a **behaviour** change in the former — and a search of this whole file finds **no row, no key and no section** for either: `config.py` matches only rows about `tests/test_ci_config.py`, and `test_config` matches nothing. The procedural repair recorded above covers a unit that **creates** a module; these are long-lived files the routine never registered in the first place, because re-derivation only ever follows rows that already exist. There is nothing to re-derive here, so no key is invented for a file with no rows: the finding is that **a file can change behaviour repeatedly and never enter this register**, and it is left for whoever owns the next closure rather than repaired by ceremony.

**The column-count check needed a correction of its own, and the false alarm is the useful part.** Its first run reported `R2-config-with-none-trap` as a row with **nine** parts where its header has eight, and the report was **wrong**: that cell already escapes its pipe as `list[str] \| None`, which a Markdown renderer reads as a single cell, while a naive `count('|')` cannot tell an escaped separator from a real one. What settles it is the previous revision: the escape is **already present at `HEAD`**, so nothing was repaired and nothing needed to be. With the check taught to ignore an escaped pipe, this file is **clean — 11 tables, zero rows whose cell count disagrees with their header** — and that is recorded here because an instrument that reports a defect it invented is worse than no instrument at all.

**The F09i re-derivation, by SUBJECT, at `b0f5f32`** — a read-only explorer located every coordinate in this section against its own token before the unit's commit. **Every row located; none was missing.** The shift is **not constant again**, and this unit is why: the scanner gained a bare alternative and the walk gained the group branch, so subjects above the profile registry moved by **+45** while the parse path below it moved by more. Located: `_strip_non_blank` **`:291`** (validator `:289`); `_CITATION_SHAPED` **`:452`** (use `:471`, attempt `:560`); the accepted cost **`:76-82`** (token `:79`); the six-shape docstring **`:119`** with the *Shapes 5 and 6* anchor at `:150`; `R3-doc-stale-leak-placement` **`:118`**; `_has_attached_bracket` **`:553`** (comparison `:561`); the `scanner is None` branch **`:583`**; `_reference_scanner` **`:505`** with its compile at `:545`; the first-`=` cut **`:651`** and its comment block `:648-651`; the required `driver_directory` parameter **`:748`**; the duplicate-collapse pin **`:652-654`**; the `MULTIPLE_CITATION_LINES` return **`:644-645`**; `PRIORITY_EVENT_TYPES` **`:231`** with the `mode` import at `:200` and `__all__` at `:211`; `_prompt` **`:1041`** with the reference list `:1115`, the values heading `:1117` and the values `:1120-1123`; the salience call **`:1125`**; and in the tests `test_every_bound_must_be_in_range` **`:2985`** with its cases `:2975-2982`, the shape-5 `space` id **`:2273`** and the private-symbol access **`:1300`**/`:1302`.

**Two rows quote the scanner's shape in a premise that is now false while the claim they make still holds.** `R3-kept-refusal-coverage` says the `scanner is None` branch is unreachable through the public path *because "the collector's grammar never produces a reference without `<family>[<index>].<field>` structure"*. That reason stopped being true the moment a surface could be made of **bare identities**: it produced no scanner at all, which is exactly the fail-open an independent verifier measured and F09i closed. The branch is **still** unreachable end to end, but for a different reason — `_parse_answer` is only reached with a non-empty surface, and the scanner is now built whenever the surface is non-empty — so the claim stands and its stated cause does not. The subject block at `:375-377` likewise quotes "the compiled pattern" as one; it is a **three-alternative** pattern now.

**F09i's own two rows, added by the closure that created its module.**

| Location | Ids observed there | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `src/f1show/start.py` (`MINIMUM_START_MEMBERS`, `_is_lap_one`) | no review id: the module was created by F09i, so its rule is recorded here rather than found by a review | — | the next unit touching the start or the aggregation | any change to the member rule, to the minimum, or to where the group's turn sits | **NEW** — measured on the recorded session: **20** members at indices **25-43 and 1604**, so the group is **not** contiguous and its turn sits at the lowest member index; the last member is the null-timestamp orphan, which is why the rule is a scan rather than a prefix. The boundary rules are pinned by test: two members aggregate, one does not, `lap_number: True` is not a lap number, and a non-`LAP_COMPLETED` event carrying `lap_number: 1` is not a member |
| `src/f1show/booth.py`, the scanner's field alternative | the independent verifier's probe, folded into F09i's record; no review id | — | **the user**, because closing it costs a declared tolerance | any decision to close the bare non-empty bracket tolerance, or the next unit touching the scanner | **OPEN and PRE-EXISTING** — a bare token glued to a letter (`position[0][99].evil`) **airs on a field-reference surface**, measured on both the **pre-change** and the post-change bytes, so it is not a regression from F09i. The same shape is now **refused** on a bare-identity surface, because F09i's fix added the bare form there. Closing it everywhere means matching a bare non-empty bracket on **every** surface, which refuses ordinary prose such as `position [99]` inside a sentence, and that is the product trade the module documents as the user's to take |

**The START-block re-derivation, by SUBJECT, at `1d17b95`** — a read-only explorer located every coordinate in this section against its own token, never by arithmetic, and the exercise produced two conclusions before it produced a single number. **(1) This section's list was already stale at `HEAD` before this unit changed anything.** The F09i coordinates were taken **before** the review fixes that landed in the same unit's commit, so they place `_prompt` at `:1041` — a line that at `bfe8102` holds text from another method entirely, while `_prompt` actually sat at **`:1076`**. Every recorded coordinate is therefore an unverified claim about the past rather than a starting point, which is why the method is a search per row and not a shift. **(2) The shift this unit adds is not constant either.** `booth.py` went **1192 → 1213** lines and `tests/test_booth.py` **3546 → 3588**, and the insertion sits **inside** `_prompt` at `:1171`, so every subject below it moved and every subject above it did not. **Located:** `_strip_non_blank` and the persona validator `:289-295`; the two `repr` fallbacks `:713-715`; `_positive_seconds` `:727-736`; `_CITATION_SHAPED` `:456-459` (wrapper `:473-475`); the accepted cost `:76-83`; `_has_attached_bracket` `:566-573`; the six-shape docstring `:119-159` with its anchor at `:150`; the *placement* sentence `:118`; the `scanner is None` branch `:596-597` (its no-scanner case `:541-542`); the `cited_text` cut `:660-664`; the required `driver_directory` `:761`; `_prompt` `:1076`; the reference list `:1153`, the VALUES heading `:1154-1157`, the values `:1158-1161`; the `render_salience(...)` call `:1162-1163`; the `""` sentinel `:1117`; the exact language lookup `:1112`; `PRIORITY_EVENT_TYPES` `:231` (import `:200-201`, `__all__` `:214`); and in the tests `test_every_bound_must_be_in_range` `:3103-3116`, the shape-5 `space` id `:2404`, the private-symbol access `:1431`/`:1433`, and the three copy-shape pins `:1874-1884`, `:1846` and `:1714-1726`. **None was missing**, and the three bare numbers that read as this file — `:454-455`, `:475-485` and `:414` — are `salience.py` subjects, two of them at exactly their recorded coordinates there. **Two rows keep their subject and lose their description**: `:375-377` calls the scanner's compiled pattern *one* pattern when it is now two alternatives, three on a bare surface; and `:530-531` explains its branch by an odd collector shape when the guard is now an *empty* surface (`if not references: return None`) — the claim stands and its stated cause does not.

**This unit's one advisory, carried with an owner and a trigger rather than claimed closed.** The review approved and offered **no** correction transition, so nothing here reopens it; the harness returns ids, severities and locations and **never bodies**, so the subject is located by the parent in the source.

| Location | Ids observed there | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `src/f1show/booth.py:1182-1183` | `R3-001` (this unit's review `review-359d0bdc6387595c`, tier medium, one `review-reliability` lens, 3 files, **85** lines, candidate tree `393761158c…`, **approved and burned**, `consumed_revision sha256:3dbe18bd…`) | SUGGESTION, informational, no body returned | the next unit touching the START block | any change to the declaration sentence, or a start group that is not one row per car | **OPEN** — subject **located by the parent**: the declaration sentence's *"the first lap of the N cars listed above"*, where **N counts the group's rows**. The parent's own reading of the risk, carried as its own: the sentence states a count it has and calls those rows **cars**, which the group rule never checks — it admits every `LAP_COMPLETED` row whose own evidence says `lap_number == 1`, so it guarantees neither that two rows are different cars nor that every member resolves to a driver identity (an unresolved member is valued by the declared unknown name). Nothing measured so far contradicts the sentence, and the wording claims slightly more than the rule establishes |

## run.py — from the F10 review

F10 was reviewed and approved as `review-0114285928bfdd2d` (medium tier, one `review-reliability` lens),
and all four findings are non-blocking: none opened a correction and none reopens the review. The reviewer's
descriptions are **not recoverable** — the receipt carries ids, severities and locations only — so the
**subject of each row is the parent's reading of the location, and the owner and trigger are the parent's
inference, not the reviewer's words**. The location is the identity.

| Location | Ids | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `:158-161` | R3-001 | **WARNING** | the next corpus refresh (issue #3, or any re-recording) | a corpus file that does not parse: this is the branch that puts the decoder's own message into a `RecordedSourceError`, so its shape matters exactly when a truncated or half-written file exists | OPEN, body unknown |
| `:307-312` | R3-002 | SUGGESTION | F13 | the first live call: `main` builds the model client **before** it reads the corpus, so the gemini branch constructs a real SDK client ahead of a load that may fail | OPEN, body unknown |
| `:336-388` | R3-003 | SUGGESTION | F13 | the first live call: the gemini branch materializes the credential and builds the SDK client with a base URL and **no timeout**, so the same subject as the `gemini.py` row above sits on the F10 side too | OPEN, body unknown |
| `:204-207` | R3-004 | SUGGESTION | the first live call, or any change to the declared base URL | the `native_base_url` derivation: the trailing-segment rule is proved for the two declarations in use, so a third declaration shape is what would revisit it | OPEN, body unknown |

**Subjects at these locations, re-derived by subject at `d0b3cea`** (the file was **already** no longer unchanged when F09f added the driver-directory family, and U3b added the three championship families on top, so the derivation below has now moved **twice** and the original claim that these coordinates were current is **superseded**): `:158-161` the unreadable-JSON branch of `load_recorded_session`, the only place that puts a
decoder's own message into a `RecordedSourceError`; `:307-312` the client construction in `main`, which
happens **before** the corpus is read; `:336-388` the provider branches of `_model_client`, including the
gemini branch that materializes the credential and builds the SDK client with no timeout; `:204-207` the
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
globally, so it still reports in the other. Two rules fire in both trees and are therefore global, and **five**
rules inherited from the agent harness (`B008`, `SIM108`, `S311`, `S603`, `S607`) report **zero** here and
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

| Location | Ids observed there | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `.github/workflows/ci.yml`, the whole job block | R3-no-job-timeout = R4-CI-TIMEOUT (unit review) = R3-no-job-timeout, R4-001, R4-002, R2-report-step-enforces (integration review) | **WARNING ×4** + SUGGESTION | — | — | **CLOSED by F12b (`d0d7d5b`)**: `timeout-minutes` on all three jobs — tests 15, lint 10, register 10, where GitHub's default would have been **360 minutes** a job — so the trigger named here was answered by the very next commit touching the file, which is the same mechanism that carried the webhook back (see the coverage gap below) |
| `ruff.toml`, the obligation header | R2-register-obligation-unverifiable = R3-carried-register-unenforced (unit review) = R3-register-unenforced, R2-owner-label-drift (integration review) | **WARNING ×2** + SUGGESTION | — | — | **CLOSED by F12b (`d0d7d5b`)**: the obligation is now **enforced** — a `register` job fails, naming the rule, when an ignored rule has no row — and the owner-label drift closed with five labels in one form. What remains is not the obligation but the guard's **limits**, which are rows of their own below |
| `.github/workflows/ci.yml:113`, the substring check | R3-register-substring-match, R4-register-substring-pass (integration review) = R3-substring-guard (unit review) | **WARNING** + SUGGESTION | the next unit touching CI | that unit: a guard-precision change | **OPEN for the substring half only.** The guard checks that a rule code **appears** somewhere in this file, so a code mentioned **only inside a sentence** passes — re-measured by the parent's verifier, which got exit 0 with `register guard: all 1 ignored rules have a row: E501` on a prose-only mention. It is documented in two reader-reachable places (the workflow's own comment and this row), which is why it is a declared limit rather than a hidden one. **The other half — the missing-`[lint]` default — is CLOSED by F12c**, see the row below |
| `.github/workflows/ci.yml`, the missing-`[lint]` default | the fix that answers this row's previous half | — | — | — | **CLOSED by F12c (`081e2a` → integrated `8f405d4`)**: the guard now **fails with its own prefix** when `[lint]` is absent or when `ignore` is not in it, instead of defaulting to an empty list, and the behaviour is **pinned by a test** (`test_the_guard_refuses_a_config_without_an_ignore_key`), so it cannot regress silently. Verified independently three ways: the parent neutered the check and the test went red; the unit's own verifier did it with a different mutation; and the parent's verifier confirmed that **the readability assertions are the killer** — deleting just the `register guard:` prefix assertion lets the mutant survive, because a `KeyError` also exits non-zero |
| `.github/workflows/ci.yml:68-69`, the job name | R2-row-claim-overstates-check (integration review) = R2-register-name-overstates-check (unit review) | SUGGESTION | the same CI unit | same | OPEN — the job is named `every ignored rule has a register row` while it checks that the code **appears** in the file; the comment declares that limit, the name does not |
| `.github/workflows/ci.yml:108-119`, the guard's contract prose and its path | R3-register-external-dep, R2-dup-contract-prose, R2-hardcoded-register-path (integration review) | **WARNING** + SUGGESTION ×2 | the same CI unit | same | OPEN — the guard is coupled to `docs/CARRIED-FINDINGS.md` by a **hardcoded path**, and its contract is stated in more than one place |
| `.github/workflows/ci.yml:26`, the timeout values | R2-unexplained-timeout-values (integration review) | SUGGESTION | the same CI unit | same | OPEN — 15 / 10 / 10 are **unexplained**: a reader cannot tell whether they were measured or guessed |
| nothing catches these two | the guard's own correctness, and the timeouts | — | — | — | **CLOSED by F12c (`081e2a` → integrated `8f405d4`).** The gap, in its sharpest form: **before F12c the workflow and the guard were not repository code as far as the suite was concerned — you could delete them entirely and everything stayed green.** Now they are asserted surface: `tests/test_ci_config.py` mirrors the guard against this register, runs it in sandboxes, and asserts every job carries `timeout-minutes` — and the parent's verifier measured the closure **by deletion**: removing the whole `register` job now gives **exactly five reds**, neutering `if missing:` gives one, and deleting a `timeout-minutes` gives one naming the job |
| `tests/test_ci_config.py:133-144` | R3-job-scan-charset, R4-2 (F12c review) **and** the parent verifier's own probe | **WARNING** + SUGGESTION | — | — | **CLOSED by F12d (`8f405d4`)**: the scans now read keys **permissively by indentation** and a **test** rejects the charset, instead of a filter hiding the key. The defect was **reproduced on the parent commit by three parties with three different keys**: the parent planted `register_check` (3 reds after the fix), the peer planted it too, and the parent's verifier planted **its own** digit-initial `1st_job` and measured **10 passed, ZERO reds** on the parent against **3 reds** on the fixed revision. The two controls are **independent**: a malformed key with no timeout trips the charset and timeout tests, while a **conforming** key with no timeout trips **only** the timeout test |
| `tests/test_ci_config.py`, the mirror's own comparison | the parent verifier's m1 survivor | — | — | — | **CLOSED by F12d (`8f405d4`)**: neutering the comparison now **kills exactly one test**, `test_the_mirror_fails_when_an_ignored_rule_has_no_row` — reproduced by the parent (1 red), by the peer (1 red) and by the parent's verifier (1 red, one pytest process against a pristine control). The failure direction is **genuinely exercised** on planted texts, and the control half blocks a fail-everything mutant |
| `tests/test_ci_config.py:220-225` | R3-guard-output-contract (F12c review) | **WARNING** | the next unit touching the test | any change to the guard's message | OPEN — the test asserts against the guard's **messages**, so the two must change together |
| `tests/test_ci_config.py:193-194` | R2-assignment-context-leak (F12c review) | SUGGESTION | the next unit touching the test | any change to the sandbox helper | OPEN — a sandbox value leaks into the assertion's context |
| `tests/test_ci_config.py:64-75` | R3-heredoc-dedent-brittleness (F12c review) | SUGGESTION | the next unit touching the test | any change to the workflow's indentation | OPEN — the heredoc dedent is brittle; the parent's verifier measured the **consequence**: with 4-space job indentation the timeout scan reads **zero** jobs and passes **vacuously**, while only `test_the_workflow_declares_at_least_one_job` fails |
| `tests/test_ci_config.py:127-137` | R2-duplicated-job-scan (F12c review) | SUGGESTION | the next unit touching the test | any change to either job scan | OPEN — the `partition("\njobs:\n")` appears twice, so there are two places to keep correct |
| `tests/test_ci_config.py:111-117` | R2-config-with-none-trap (F12c review) = R2-misleading-ignore-none (unit review) | SUGGESTION | the next unit touching the test | any change to the sandbox helper's signature | OPEN — `ignore: list[str] \| None` where `None` and `[]` mean the same, and in the no-`[lint]` case the parameter is dead because `config_text` wins: two ways to say one thing and an unreachable branch, in the test itself |
| `.github/workflows/ci.yml:105-106` | R3-refusal-message-scope (F12c review) | SUGGESTION | the next ci.yml unit | any change to the guard's refusal message | OPEN |
| `tests/test_ci_config.py:26`, `:157` | R4-1, R4-3 (F12c review) | **WARNING** ×2 | the next unit touching the test | any change to those lines | OPEN — ids only; the bodies are unrecoverable, so the locations are the identity |
| `docs/CARRIED-FINDINGS.md:385-389`, this section's own prose | R2-harness-rule-count-mismatch = R3-docs-rule-count | **WARNING** + SUGGESTION | — | — | **CLOSED by correction in the same commit**: the sentence said "three" and then **listed five rule names**, and it was ungrammatical besides. The integration review caught a miscount **in the register's own text** — the same defect class this register exists to catch, caught by the gate that re-reviews everything, on itself |

## The recorded corpus, and the second session it now holds (F09j)

| Location | Ids observed there | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `fixtures/openf1/9655/`, ten families, 574,894 bytes | no review id: the corpus was captured and is verified by **measurement** | — | the next unit touching the corpus or the loader | any change to a recorded session, to its provenance, or to the loader's family list | **NEW, AND DELIBERATELY WITHOUT A NATIVE REVIEW** — the first `START` over the whole unit returned **`lens_context_budget_exceeded`** because 575 KB of single-line JSON cannot be turned into reviewer material, and it created **no authority**, so nothing was abandoned or repaired; the unit was split and the review covered the authored part instead. What stands in place of that review is measurement: every file's SHA256 and byte size, every record's `session_key`, the parent's own re-derivation of every pinned number (**1,708** events, the five-lap window's **114**, the start group's **20/29/19**, **1,689** turns and **19** excluded) and an independent verifier's six-claim pass, whose one finding is the row below |
| `tests/test_second_session.py` | the same closure: the module that pins those numbers | — | the next unit touching the corpus or its pins | any change to session 9655's fixtures or to the loader's family list | **NEW** — the module pins **only** measured numbers and imports nothing from session 9617's suite, because order, indices, null timestamps and seat consequences are session-specific: measured, **1,353** of 1,689 seats differ from strict alternation here against **1,023** of 1,629 on 9617 |
| `fixtures/openf1/PROVENANCE.md`, both pacing sentences | an independent verifier's finding, not a review's | — (fixed) | — | — | **CLOSED in the same unit** — the 9655 section compared `10 requests in 7.4 s` directly against the **per-minute** ceiling, which reads as about **81 per minute**, and the pre-existing 9617 sentence carried the same defect (`8 in 8.481 s`, about 57). Both now state the two different kinds of bound — **3/second** is an instantaneous rate, **30/minute** is a **count** — and both name the old arithmetic as wrong. Kept as a row because the older sentence predated this unit |
| `fixtures/openf1/9655/drivers.json` | a measured coincidence, no id | — | — | — | **OBSERVATION** — this file is **exactly 8,013 bytes**, the same size as session 9617's `drivers.json`, and the contents differ. Equal size is never equal content, and it is the provenance's SHA256 that tells them apart |

**Fixtures are keyed by their provenance, not by blob OIDs, and that is deliberate.** `PROVENANCE.md` records each family's byte size, record count, request URL, request time and SHA256, which is a stronger key than a blob row for data no reviewer reads; the F09j corpus alone would have needed ten rows of JSON nobody can review. Recorded here so a later closure does not "repair" the difference by inventing keys |

## The telemetry source question — evaluated, not adopted (2026-10-13)

| Location | Ids observed there | Severity | Owner | Trigger | Status |
| --- | --- | --- | --- | --- | --- |
| `docs/EXTERNAL-CONTRACTS.md`, the FastF1 section | an evaluation, not a review: no finding ids | — | **F06**, with F07 behind it | F06 or F07 being authorized | **OPEN as a decision, closed as an evaluation.** FastF1 brings the one thing this project has no field for — per-driver car data, position and weather — and it was measured in a throwaway environment: **347 MB installed**, **13.1 MB** of cache without telemetry for two races, **147.2 MB** with telemetry for **one** weekend against our whole **4.18 MB** corpus, lap counts matching exactly in one session and within one row in the other, results richer than ours, and **no mini-sector column** where ours has one. The decisive constraint is recorded with it: **its live path needs an F1TV subscription, its post-session path is free and unauthenticated**, so it offers no new door to the live data. Whoever authorizes F06 must decide three things this evaluation leaves open: the **volume**, whether a **second data path** beside the single sync writer is acceptable, and the **provenance** question — its cache holds parsed pickles, while this register's corpus rule records raw response bodies with SHA256. Nothing was installed in the repository and no code changed |

## Cross-cutting, from verification rather than from reviews

| Subject | Where recorded | Owner | Trigger | Status |
| --- | --- | --- | --- | --- |
| Five probe-only cases from F03c-3a: empty checkpoint from a distinct prior stamp, checkpoint-await cancellation, direct-await KI/SystemExit, no-prior-watermark write failure, drivers immutability/mixed-session refusal | issue #8 | issue #8 | promoting probe-only coverage | OPEN |
| The F03c-4 generation branch is unreachable through the public API | issue #8 | issue #8 | deciding to reach it or to delete it | OPEN |
| Race coverage in the session lifecycle is scripted, not real concurrency | issue #8 | issue #8 | any change to the lifecycle, or a decision that real concurrency is needed | OPEN |
| A retried POST may be sent more than once — an unverified provider assumption | issue #9 | issue #9 | any live call, or a decision to exclude POST from the retry set | OPEN |
| The declared Python 3.12 floor is proven runnable but nothing enforces it | issue #7 | — | — | **CLOSED** by F12 (`3a20032d`): the `tests` job runs a **3.12/3.14 matrix**, and the floor was proven **locally** rather than deferred to CI — 778 passed on cpython 3.12.13, reproduced independently by both the peer's verifier and the parent's |
| No lint configuration is committed, so every "clean" claim is scoped to an external harness file | issue #7 | — | — | **CLOSED** by F12 (`dbcd58c`): `ruff.toml` is committed with a pinned `0.17.0`, every silence is scoped and carries a row in the section above, and the **committed** configuration is now the yardstick. The agent harness's file remains a tool, not the measure |
| The live service, the real token exchange and real responses are unverified | issue #3 | F13 | a purchased subscription and an explicit grant | **PARTIALLY EXERCISED on the free path, still OPEN for the authenticated one.** A live test on 2026-10-11 drove the project's own HTTP boundary, its shared limiter and its collector against the **free** OpenF1 API for the most recent Grand Prix available - Singapore 2026, `session_key` **11388** - and derived **1,863 events** from live payloads it had never seen: position 396, laps 1,240, pit 25, stints 47, race_control 155, one event per in-scope record, **22 distinct drivers**, 1,816 timestamps known and **47 explicitly unknown** with the reason `family_carries_no_timestamp_field` (the stints family), and **no overtake event** (the enum has no such type, which is the declared non-claim). Six requests, ~6 s, ~1 req/s, paced by the project's own limiter. What stays unverified is the **authenticated/live** path: the token exchange, real-time streams and a real generation. |
| `sessions?year=2026` lists **scheduled rounds with no data yet** | the live free API, measured 2026-10-11 | the pilot/live path | any unit that selects a session by date, or the F13 pilot | **OPEN - found by the live test, not by a review.** The listing for 2026 returned 131 sessions and **25 rows named `Race`, of which 19 had a past `date_start` and 6 were in the future**. Selecting the most recent race by `max(date_start)` therefore picked **2026-12-06 (Abu Dhabi, `session_key` 11436)**, and all five collector families answered **404** for it. The collector handled that correctly - **zero events, nothing invented** - so the defect is in the **selection**, not in the collector: a date-based selector must filter to **past or completed** sessions, or tolerate the 404 explicitly. Not reachable from the recorded corpus, which holds one complete session |

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
