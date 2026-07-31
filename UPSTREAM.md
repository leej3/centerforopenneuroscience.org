# Upstream adoption

The `orinoco-lite` branch continues the ordinary CON website history. It does
not merge or graft the complete `www-from-model` history. The clean mirror in
`con/www-from-model` remains at reviewed upstream commit
`6945272e5f3fcf353627b8e1c3e68bcaf76cc2ce`.

Exact paths, commits, and current exact-versus-adapted classifications are in
`provenance/adopted-files.yaml`; all tool and schema pins are in
`provenance/toolchain.yaml`.

## Milestone 1 divergences

| Upstream behavior | CON candidate behavior | Reason |
| --- | --- | --- |
| Read changing `public` collection from the Psychoinformatics pool | Build an isolated `research_info` collection from repository YAML | No persistent service or independently changing production input |
| Root organization PID `xyzrins:.` | Root PID `ror:04tfhh831` | Stable reviewed CON identity |
| Derive content paths directly from PIDs | Explicit reviewed PID-to-path adapter | DOI URLs and Pages subpaths are not safe implicit slugs |
| Inject and inline native graph relations through qri | Cache/list/render with qri; temporarily interpret validated string-valued attributes | Pinned validator/type-designator incompatibility documented in `provenance/schema-compatibility.yaml` |
| Root-relative assets and links | Hugo-relative links with a Pages-provided base URL | Fork project Pages must work below a path prefix |
| Forgejo runner deploy to `/www` | Fork-only GitHub Pages artifact deployment | Preview without production domain or DNS changes |
| Live depiction registration and git-annex | Reviewed assets committed as normal Git objects | Self-contained static build and unavailable legacy annex payloads |

The relationship compatibility mapping is CON-specific and is not presented as
a reusable upstream fix. Native qualified relations must be restored after a
compatible pinned schema/service path is proven.

## Synchronization policy

Review new upstream commits deliberately against the recorded commit. Copy or
cherry-pick only the useful paths, update provenance classifications, and run
`scripts/test-milestone.sh` before changing a pin. Develop generally useful
fixes on focused branches in `con/www-from-model` and offer them upstream
separately from CON metadata, content, policy, or presentation.
