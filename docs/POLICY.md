# Policy

Back to docs index: `docs/README.md`

## Support Model

This repository is provided as-is.
No warranty, maintenance SLA, or guaranteed support is provided.

## Community Input Status

Not accepted:
- Pull requests
- Issues
- Discussions
- Suggestions

If you need different behavior, fork the repository and maintain your own variant.

## Private Reporting Channel

Security, vulnerability, and legal concerns are accepted by private email only:
`reap.change_0x@icloud.com`

Do not include sensitive details in public channels.

## Dependency Update Policy

Routine Dependabot version-update PRs are disabled to reduce maintenance noise.
Automatic Dependabot security-update PRs are also disabled. Dependabot alerts and
the fail-closed `pip-audit` check remain enabled as the preferred triggers for
manual dependency review.

Accept dependency updates when they:
- address a security advisory affecting the locked dependency set,
- fix an observed repo bug,
- improve CI or setup reliability, or
- provide a clear functionality gain for this tool.

Defer routine "new version available" updates when there is no repo-specific justification.

When static evidence proves that an advisory's vulnerable code path is absent,
record a narrowly scoped `pip-audit` exception with its rationale and dismiss the
matching Dependabot alert with the same rationale. Do not change dependency
versions solely to silence a non-applicable advisory.

## Intended Use

- Personal and internal noncommercial workflows.
- Craig export folder transcription with OpenAI whisper-1.

See `LICENSE` for legal terms.
