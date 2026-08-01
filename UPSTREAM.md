# Upstream adoption

The `orinoco-lite` branch continues the ordinary CON website history. It does
not merge or graft the complete `www-from-model` history. The clean mirror in
`con/www-from-model` remains at reviewed upstream commit
`6945272e5f3fcf353627b8e1c3e68bcaf76cc2ce`.

## Responsibility split

Milestone 1 deliberately combines four sources:

| Source | What the candidate uses |
| --- | --- |
| Legacy CON site | CON identity, wording, public compatibility URLs, visual values, logos, DataLad depiction, and Yaroslav's annexed portrait |
| `www-from-model` | Hugo/Congo scaffold, class taxonomies, metadata page-bundle pattern, related-record layouts, filterable lists, and the `qri` cache/list/inline/render pipeline |
| Pinned Orinoco components | Schema, ephemeral Dump Things validation, `dtc`, `qri`, and the separately maintained Things graph renderer |
| `dump-research-info` | Reviewed records, source evidence, and migration decisions only; it is not a build or deployment dependency |

The visual result is a CON adaptation rather than a copy of the
Psychoinformatics site. Exact paths and exact-versus-adapted classifications
are in `provenance/adopted-files.yaml`; tool and schema pins are in
`provenance/toolchain.yaml`.

## Retained upstream behavior and deliberate differences

| Upstream behavior | CON candidate behavior | Reason |
| --- | --- | --- |
| Read a changing `public` collection from the Psychoinformatics pool | Build an isolated `research_info` collection from repository YAML | No persistent service or independently changing production input |
| Validate and then generate through Dump Things and `qri` | Post the exact transient record streams with upstream `dtc`, then retain `qri cache`, `list`, `inline-records`, and `render-record` | Upstream validation and generation remain the publication path without a custom parallel validator |
| Generate class-specific `_index.md` term bundles | Generate every record with one generic template into an ignored build workspace | Adding a record must not require committed record pages or a new class-specific template |
| Native qualified relations drive inlining and taxonomy navigation | One generic temporary projection emits `links_out`/`links_in`, forward Hugo taxonomy terms, and raw source assertions before `qri` inlines them; Hugo `.Data.Pages` supplies reverse backlinks | The pinned LinkML/schema/service tuple cannot round-trip native relation subclasses; the displayed graph and reverse navigation still come from metadata |
| Large full-page graph supplied separately | Adapt `things-graph-renderer` commit `04f6241e37532fdb03b6f95d2dbe304e7171d504` into a compact side graph limited to the current record's immediate neighborhood | Preserve graph-guided navigation while keeping page content primary and Pages base paths safe |
| Root organization PID `xyzrins:.` | Root PID `ror:04tfhh831` | Stable reviewed CON identity |
| Root-relative assets and links | Hugo-relative links with a Pages-provided base URL | Fork project Pages must work below a path prefix |
| Live depiction registration from the pool | Repository page-bundle symlinks to reviewed legacy assets; Yaroslav's payload is retrieved by git-annex from `datasets.datalad.org` | Deterministic assets without a live metadata pool or replacing annex content with a Git blob |
| Forgejo runner deploy to `/www` | Fork-only GitHub Pages artifact deployment | Preview without production domain or DNS changes |

`scripts/project_records.py` is the only schema-compatibility projection. For
each configured relationship predicate it requires a target in the loaded
record pool, independent of whether that PID is a CURIE or URL, and applies
generic predicate rules; it has no CON PID, label, route, or asset table.
Taxonomy assignment follows the normalized edge direction, except that
symmetric `related_to` is assigned both ways. Each edge carries its unmodified
source, predicate, and target assertion so a later compatible upstream pin can
regenerate native relations without reverse-engineering the rendered site.

This is not a claim that native qualified relation containers already work.
The precise failure, source-role limitations, tested alternatives, and removal
condition are documented in `docs/upstream-schema-discriminator-issue.md` and
`provenance/schema-compatibility.yaml`.

## Synchronization policy

Review new component releases as a compatible tuple: schema, Dump Things
service and client, `qri`, and LinkML runtime. First run the recorded native
Association, Attribution, Generation, DOI, and ISSN fixtures. Only a tuple that
passes both the direct post and `qri` round trip replaces the current pins.
Then update the schema snapshot and generated results and remove the temporary
relationship normalization; do not add version-specific PID or field tables.

Review new `www-from-model` and Things graph renderer commits deliberately
against their recorded commits. Copy or cherry-pick only useful paths, update
the provenance classifications, and run `pixi run --locked test-milestone`
before changing a pin. Generally useful fixes belong on focused upstream
branches; CON metadata, content, policy, and presentation remain downstream.
