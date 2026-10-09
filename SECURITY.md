# Security policy

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository: open the **Security**
tab and choose **Report a vulnerability**. That opens a private channel visible only to
the maintainers, and it is the preferred route for anything that should not be public.

If private reporting is unavailable, open a normal issue that describes the *kind* of
problem and asks for a private channel — without the details. Do not open a public issue
containing an exploit, a working attack, or anything copied out of a credential store.

## What is in scope

This project handles credentials, so the interesting classes of problem are:

- **Secret leakage.** Anything that lets a credential reach a log sink, an exception
  message, a traceback, a transcript, a snapshot artifact or a committed file.
- **Credential handling.** Storage, redaction, or lifecycle mistakes in the
  configuration and logging layers.
- **Untrusted input.** This project consumes a third-party HTTP API. Parsing mistakes
  that let a hostile or corrupted response cause code execution, unbounded memory or
  disk growth, or a denial of service are in scope.
- **The local store.** Ways to corrupt it, or to make one session's data appear under
  another's identity.

## What is not in scope

- **The upstream data sources.** Problems in OpenF1, in the historical archive, or in
  the Gemini API belong with those providers; report them there.
- **The commentary text itself.** A language model saying something wrong, dull or
  imprecise is a quality issue, not a vulnerability. It is worth an issue, not a
  private report.
- **Anything requiring a paid subscription the project does not hold.** The repository
  does not ship live credentials.

## How this project is meant to hold credentials

By design, **no credential is committed and no credential has a default**. Secrets are
supplied at runtime and held as `SecretStr`, so they cannot surface through `repr`,
`str`, `model_dump`, or `model_dump_json`. A logging filter redacts registered secret
values from log records, including through `%`-style arguments, nested containers and
exception traces, and it is installed on the handlers rather than only on the logger,
because a filter on a logger does not see records propagated from a child logger.

If you find a path that gets around any of that, it is exactly the kind of report this
policy exists for.

## Response

This is a small project maintained on a best-effort basis. There is **no response-time
commitment and no bug-bounty programme**, and this policy deliberately does not promise
either. Reports are read, and anything confirmed is fixed and credited unless you ask
otherwise.

## Supported versions

The project is pre-release: there is no supported release line yet, and fixes land on
`main`.
