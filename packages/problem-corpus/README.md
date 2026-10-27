# Problem corpus

Curated, version-controlled Python interview problems and remediation exercises. These files
are the source of truth; `pnpm db:seed` synchronizes their database projection.

```text
taxonomy.yaml            topics and capability slugs (never rename a slug)
problems/<topic>/*.yaml  one problem per file; file name == slug
exercises/<topic>.yaml   recall / recognition / explain / trace / debug items
```

Validate:

```bash
pnpm corpus:validate            # schema + lint + execute every reference and known-wrong solution
pnpm corpus:report              # coverage by topic, role, difficulty, capability type, transfer group
```

Current coverage: 86 problems across 17 topics (each with recognition/canonical/boundary/
transfer roles where the pattern supports them), 74 exercises, 106 capabilities with no
uncovered capability. All content is `status: development` — it has **not** passed Human
Gate 2 review (see `docs/human-gates/gate-2-review.md`).

Problems declare curriculum membership with `collections`. The corpus currently preserves the
original 32-problem `core` track and covers all 75 problems in the `blind-75` track.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the authoring and review workflow.
