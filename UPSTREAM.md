# Clean-migration upstream policy

The `codex/clean-migration` branch is a downstream site profile based directly on `www-from-model` commit `5b401e0c478a4409442b3a8a285bd3efd5d30e05`.
This history choice intentionally supersedes the earlier prototype policy that kept the website on the legacy CON ancestry.
The legacy branches and tag remain unchanged and available as migration evidence.

## Overlay boundary

The clean migration keeps upstream-owned presentation and automation paths unchanged.
CON-specific configuration is a Hugo environment under `config/con/`, and all metadata, editorial content, assets, provenance, and committed static projection files are isolated under `profiles/con/`.

The profile consumes the upstream layouts, page templates, graph projection, and Congo theme without copying or modifying them.
It does not include a vendored schema, LinkML fork, generic relationship bridge, custom renderer, Pages workflow, or persistent metadata service.

The committed projection is a reviewable static snapshot, not a second canonical metadata source.
Its records, Markdown, graph, and digest are regenerated from the canonical YAML with the component revisions in `profiles/con/profile.yaml`.

## Synchronization policy

Upstream synchronization is deliberate:

1. Record and review the new `www-from-model` commit.
2. Rebase the two downstream commits onto that exact commit.
3. Confirm that the rebase did not change upstream `content/`, `layouts/`, `page_templates/`, or workflow files.
4. Regenerate only `profiles/con/projection/` with the pinned source schema, Dump Things, `qri`, and upstream graph implementation.
5. Verify the projection digest, native-CURIE validation, Hugo build, and `git range-diff` before updating the reviewed commit in the profile.

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
