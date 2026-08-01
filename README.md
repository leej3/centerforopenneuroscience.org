# Center for Open Neuroscience — Orinoco Lite preview

This branch proves a metadata-first path from reviewed CON records to a
deterministic static website. It is a Milestone 1 preview: the production
domain and the legacy `master` deployment remain unchanged. The pre-migration
site is preserved on `legacy-site` and by the annotated tag
`legacy-site-2026-07-31`.

## What drives the site

Canonical research information is stored as one YAML record per entity under
`metadata/records/<ClassName>/`. The build posts those records directly through
the pinned upstream `dtc post-records`/Dump Things validation path, reads them
back with `dtc`, and uses the upstream `qri cache`, `qri list`,
`qri inline-records`, and `qri render-record` stages.

The resulting record pages are generated `_index.md` page bundles below
`build/hugo/content/`; they are not maintained in Git. A configured
relationship assertion assigns the target's taxonomy term to the source page.
The target term's Hugo `.Data.Pages` collection then supplies its reverse
backlinks without requiring a reciprocal assertion. Only symmetric
`related_to` edges assign terms in both directions. The same directed edges
produce related-record lists and `graph.json`. The graph appears as a compact
side panel on the homepage and record pages and links each visible node to its
record page.

The version-controlled files such as `content/projects/_index.md` are only
human-authored collection labels, display settings, and short editorial
introductions. They do not enumerate projects, people, publications, or their
relationships. Ordinary editorial pages and legacy redirects also remain in
`content/`, while depictions live beside their eventual generated page bundle
as symlinks to assets.

One temporary boundary, `scripts/project_records.py`, translates
string-valued relationship assertions accepted by the pinned schema into a
generic site graph. Every configured relationship predicate must name a target
in the loaded record pool, whether the PID is a CURIE, DOI URL, or another
syntax. The boundary contains class-to-section rules, but no CON PID, label,
route, or asset lookup table. Every normalized edge retains its original
source/predicate/target assertion. The upstream incompatibility, options, and
the condition for deleting this normalization are documented in
`docs/upstream-schema-discriminator-issue.md` and
`provenance/schema-compatibility.yaml`.

The remaining repository scripts each have one build-boundary role:

| Script | Purpose |
| --- | --- |
| `build.sh` | Orchestrate the ephemeral upstream service, `dtc`/`qri`, locked graph bundle, and Hugo build |
| `prepare_build.py` | Create a disposable store and content workspace without modifying canonical records or editorial files |
| `project_records.py` | Implement the one temporary generic schema boundary and emit routes, links, taxonomies, and graph data |
| `check_site.py` | Check the rendered site's pages, backlinks, assets, base-path links, and deterministic manifest; it does not revalidate metadata |
| `test-milestone.sh` | Exercise reproducibility and the schema-invalid, dangling-link, and sixth-record acceptance cases |
| `reproduce_schema_discriminator.py` | Reproduce the upstream LinkML issue independently of the publication pipeline |

The earlier custom record validator, fixed enrichment script, individual gate
test scripts, and Hugo installer have been removed.

## Edit the preview

When editing metadata:

1. Edit or add an individual YAML record under `metadata/records/` and keep its
   stable `pid` in the appropriate class directory.
2. Express internal relationships with the configured PID-valued predicates.
   Their targets must be records in the same pool. Forward taxonomies, reverse
   backlinks, lists, and graph edges are generated; do not hand-edit them or
   add reciprocal assertions solely for display.
3. Run the complete publication contract below.
4. Review the YAML diff and the generated page in `build/site/`.

The checked-in Milestone 1 slice has five records: CON, Yaroslav Halchenko,
DataLad as a project and output, and the selected DataLad publication. Full CON
metadata migration is deliberately deferred.

## Build and test

Once annex content is hydrated, Git and Pixi `0.73.0` are the only build
prerequisites. Pixi is the sole environment manager: its lock supplies Python,
Hugo Extended, Node, Dump Things, `dtc`, `qri`, and all Python dependencies.
Hugo is not downloaded by a repository script.

```shell
git submodule update --init --recursive
pixi install --locked
```

The required Yaroslav image remains a git-annex object with its legacy key.
The GitHub workflows fetch it from the read-only `datasets.datalad.org` remote
before building. Linux CI receives git-annex from Pixi. Conda-forge does not
currently supply git-annex for `osx-arm64`, so a fresh macOS checkout needs a
system git-annex only for that one-time hydration; the build itself remains in
Pixi. Exact remote, key, and checksums are in `provenance/assets.yaml`.

On a fresh checkout, hydrate that payload once before testing (use the same
commands with a system git-annex on macOS):

```shell
pixi run --locked git annex init orinoco-lite
git remote add datasets.datalad.org https://datasets.datalad.org/centerforopenneuroscience/con.org/.git/
git fetch datasets.datalad.org git-annex:refs/remotes/datasets.datalad.org/git-annex
pixi run --locked git annex enableremote datasets.datalad.org
pixi run --locked git annex get --from datasets.datalad.org assets/img/yaroslav-halchenko.jpg
pixi run --locked git annex fsck --fast assets/img/yaroslav-halchenko.jpg
pixi run --locked test-milestone
```

For one build, run:

```shell
BASE_URL=http://127.0.0.1:1313/ pixi run --locked build
```

The output is `build/site/`. Dump Things listens only on localhost while the
build runs and is terminated automatically; the deployed site has no metadata
service dependency. The Sigma renderer is built with `npm ci` from its checked
in lockfile inside the Pixi Node environment.

The milestone test proves that:

- the five canonical records pass the direct upstream Dump Things post;
- a schema-invalid record stops at that upstream gate;
- a dangling target on any configured relationship predicate stops at the
  generic projection boundary, regardless of PID syntax;
- two identical inputs produce byte-identical site manifests;
- a temporary sixth metadata record produces a sixth page and graph node
  without a template, route, index, or code change; and
- the generated taxonomies, reverse navigation, filterable lists, compact
  graph, base-path links, assets, and legacy compatibility routes are present.

## Preview deployment

`.github/workflows/pages-preview.yml` publishes only pushes to `orinoco-lite`
in `leej3/centerforopenneuroscience.org`. It uses the base URL returned by the
fork's GitHub Pages configuration and never includes the production `CNAME`.
Pull requests to `master` run the same publication contract without deploying.

Production cutover, complete metadata migration, reusable action/template
extraction, and DNS changes are later milestones.

## Provenance and licensing

- `UPSTREAM.md` defines what came from the legacy CON site, `www-from-model`,
  Orinoco components, and the migration repository.
- `provenance/adopted-files.yaml` distinguishes exact upstream copies,
  adaptations, and local boundaries.
- `provenance/toolchain.yaml` records immutable build pins and the vendored
  schema checksum.
- `provenance/assets.yaml` records legacy asset origins and annex availability.
- `provenance/legacy/` records representative deployed output, URLs, and design
  values.

The existing website design derives from Buddycloud's Apache-2.0 design; new
CON content is released under CC BY 3.0 as documented by the legacy project.
The vendored schema and adapted Things graph renderer are MIT-licensed.
