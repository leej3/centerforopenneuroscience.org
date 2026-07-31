# Center for Open Neuroscience — Orinoco Lite preview

This branch proves a repository-native path from reviewed CON metadata to a
deterministic static website. It is a Milestone 1 preview: the production
domain and the legacy `master` deployment remain unchanged.

The pre-migration site is preserved on `legacy-site` and by the annotated tag
`legacy-site-2026-07-31`.

## Edit the preview

Canonical research records are individual YAML files under
`metadata/records/<ClassName>/`. Editorial pages live in `content/`, assets in
`assets/` and `static/`, and presentation overrides in `layouts/` and `config/`.
Generated Markdown, JSONL, caches, validation stores, and public HTML stay in
ignored `build*` directories.

When editing a record:

1. Keep its stable `pid` and exact class directory.
2. Update reciprocal internal links when a selected relationship changes.
3. Run the complete publication contract below.
4. Review both the YAML diff and the generated page diff before opening a pull
   request.

The selected slice uses a documented temporary relationship compatibility
mapping because the pinned upstream validator rejects native qualified
relationship containers and typed DOI/ISSN identifiers. Read
`provenance/schema-compatibility.yaml` before changing those fields. The
semantic gate still enforces target existence, expected classes, reciprocity,
connectivity, and DOI/ISSN formats.

## Build and test

Prerequisites are Git and uv `0.7.19`. Congo is a pinned submodule. Hugo
Extended `0.154.5` is downloaded into `.tools/` with a verified checksum when a
matching local binary is unavailable.

```shell
git submodule update --init --recursive
scripts/test-milestone.sh
```

The test runs two byte-for-byte comparison builds and a third build with a
temporary canonical metadata edit. It proves that:

- all five records pass the ephemeral Dump Things validation endpoint;
- schema-invalid and dangling-target records stop publication;
- qri consumes transient JSONL and renders the metadata pages;
- Hugo produces a base-path-safe site with the selected assets and legacy
  compatibility routes; and
- the same inputs reproduce identical output while a metadata change changes
  its page.

For one build, run:

```shell
BASE_URL=http://127.0.0.1:1313/ scripts/build.sh
```

The output is `build/site/`. Dump Things listens only on localhost while the
script runs and is terminated automatically; the built site has no metadata
service dependency.

## Preview deployment

`.github/workflows/pages-preview.yml` publishes only pushes to `orinoco-lite`
in `leej3/centerforopenneuroscience.org`. It uses the base URL returned by the
fork's GitHub Pages configuration and never includes the production `CNAME`.
Pull requests to `master` run the same publication contract without deploying.

Production cutover, complete metadata migration, action/template extraction,
and DNS changes are later milestones.

## Provenance and licensing

- `provenance/imports.yaml` identifies the legacy, upstream scaffold, and
  migration-input commits.
- `provenance/adopted-files.yaml` distinguishes exact upstream copies from CON
  adaptations.
- `provenance/toolchain.yaml` records immutable build pins and the vendored
  schema checksum.
- `provenance/legacy/` records representative deployed output, URLs, and design
  values.

The existing website design derives from Buddycloud's Apache-2.0 design; new
CON content is released under CC BY 3.0 as documented by the legacy project.
The vendored schema is MIT-licensed and its notice is retained beside the
snapshot.
