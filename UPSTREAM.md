# Full CON migration upstream policy

The `codex/full-con-migration` branch continues the accepted clean-migration site profile on `www-from-model` commit `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8`.
The reviewed upstream range from `5b401e0` contains one CI-only workflow change and no presentation change.

The accepted `codex/clean-migration` branch remains an unchanged checkpoint.
The legacy branches and tag also remain unchanged and available as migration evidence.

## Overlay boundary

The clean migration keeps upstream-owned presentation and automation paths unchanged.
CON-specific configuration is a Hugo environment under `config/con/`, and all metadata, editorial content, assets, provenance, and committed static projection files are isolated under `profiles/con/`.

The profile consumes the upstream layouts, page templates, graph projection, and Congo theme without copying or modifying them.
It does not include a vendored schema, LinkML fork, generic relationship bridge, custom renderer, Pages workflow, or persistent metadata service.

The committed projection is a reviewable static snapshot, not a second canonical metadata source.
Its records, Markdown, graph, and digest are regenerated from the canonical YAML with the component revisions in `profiles/con/profile.yaml`.

## Successor history policy

The two rebased clean-migration commits preserve the accepted experiment.
New work uses ordinary, reviewable commits:

1. a stable full-migration profile and validation commit;
2. hand-authored content batches organized by a coherent migration scope; and
3. one terminal generated-projection commit.

Before adding another content batch, remove the terminal projection commit, make and review the hand-authored change, and regenerate a new terminal snapshot.
Generated conflicts are never resolved by hand during an upstream rebase.

## Synchronization policy

Upstream synchronization is deliberate:

1. Record and review the new `www-from-model` commit.
2. Preserve the old downstream range and remove the terminal projection commit from the working branch.
3. Rebase the profile and hand-authored content commits onto that exact upstream commit.
4. Confirm that the rebase did not change upstream `content/`, `layouts/`, `page_templates/`, or workflow files.
5. Regenerate only `profiles/con/projection/` with the pinned source schema, Dump Things, `qri`, and upstream graph implementation.
6. Create a new terminal projection commit.
7. Verify the projection digest, native-CURIE validation, Hugo build, browser acceptance, and `git range-diff` before updating the parent gitlink.

Generated upstream content is never merged into the CON profile.
Likewise, CON projection files never replace upstream content paths.
This separation confines normal rebase conflicts to the small profile and transport layer.

## Source boundaries

- `www-from-model` supplies the Git base, layouts, templates, graph code, and Hugo structure.
- `dump-research-info` commit `1c7e99ec6f296d5e6cb6a61e3b786227190802da` supplies reviewed migration evidence only.
- The legacy CON site commit `e6e9200a0987a65097afff896105ff838be1659e` supplies editorial and asset provenance only.
- The source-form Things schema at commit `d26ea4135e28c25b134c64de1cdc15d15cd2f9f0` is the validation source.
- Deployment remains static and does not read a changing metadata pool.

The exact inputs, outputs, and non-rendered reference records are declared in the profile manifests.
