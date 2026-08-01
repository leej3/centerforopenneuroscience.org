#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

metadata_root=${METADATA_ROOT:-metadata}
build_dir=${BUILD_DIR:-build}
base_url=${BASE_URL:-http://127.0.0.1:1313/}
base_url=${base_url%/}/
port=${DUMPTHINGS_PORT:-8111}
service_url="http://127.0.0.1:${port}"

python scripts/prepare_build.py \
  --metadata-root "$metadata_root" \
  --build-dir "$build_dir"

service_log="$build_dir/dump-things.log"
dump-things-service \
  --host 127.0.0.1 \
  --port "$port" \
  --log-level WARNING \
  --config "$build_dir/store/config.yaml" \
  "$build_dir/store" >"$service_log" 2>&1 &
service_pid=$!
cleanup() {
  kill "$service_pid" 2>/dev/null || true
  wait "$service_pid" 2>/dev/null || true
}
trap cleanup EXIT

for attempt in {1..60}; do
  if curl --fail --silent "$service_url/openapi.json" >/dev/null; then
    break
  fi
  if ! kill -0 "$service_pid" 2>/dev/null; then
    cat "$service_log"
    exit 1
  fi
  if [[ "$attempt" == 60 ]]; then
    cat "$service_log"
    echo "Ephemeral Dump Things service did not become ready" >&2
    exit 1
  fi
  sleep 1
done

# Post the repository's exact YAML records through the upstream client and
# service. This is a validation write into an ephemeral incoming area; the
# entire store is discarded after the build.
validation_log="$build_dir/validation.log"
: >"$validation_log"
for stream in "$build_dir"/validation-jsonl/*.jsonl; do
  class_name=${stream##*/}
  class_name=${class_name%.jsonl}
  DTC_TOKEN=preview-validator dtc post-records \
    "$service_url" research_info "$class_name" \
    <"$stream" >>"$validation_log" 2>&1
done

export DTC_TOKEN=preview-reader
export DUMPTHINGS_APIURL="$service_url"
export DUMPTHINGS_TOKEN=preview-reader
export QRI_RECORD_CACHE="$build_dir/qri-raw-cache.json"

dtc get-records "$service_url" research_info \
  | tee "$build_dir/records.jsonl" \
  | qri cache >/dev/null

output_root="$build_dir/hugo/content"
graph_path="$build_dir/hugo/static/graph.json"
qri list \
  | python scripts/project_records.py \
      --site-config "$metadata_root/site.yaml" \
      --content-root "$output_root" \
      --base-url "$base_url" \
      --source-manifest "$build_dir/source-manifest.json" \
      --graph "$graph_path" \
      --report "$build_dir/projection-report.json" \
  | tee "$build_dir/projected-records.jsonl" \
  | QRI_RECORD_CACHE="$build_dir/qri-projected-cache.json" qri cache >/dev/null

# qri rewrites a cache when a process exits. A separate read cache avoids a
# truncate/read race between `list` and `inline-records` in one pipe.
cp "$build_dir/qri-projected-cache.json" "$build_dir/qri-inline-cache.json"
QRI_RECORD_CACHE="$build_dir/qri-projected-cache.json" qri list \
  | QRI_RECORD_CACHE="$build_dir/qri-inline-cache.json" qri inline-records \
      -p links_out -p links_in \
  | qri render-record page_templates/record.md.j2 '{output_path}'

# Build the base-path-aware adaptation of the pinned upstream Sigma renderer.
npm --prefix graph-renderer ci --ignore-scripts --no-audit --no-fund
graph_output=$(cd "$build_dir/hugo/static" && pwd)
npm --prefix graph-renderer run build -- --outDir "$graph_output"

hugo version | grep -q 'v0.154.5.*extended'
HUGO_RESOURCEDIR="$build_dir/hugo/resources" \
HUGO_STATICDIR="$build_dir/hugo/static" hugo \
  --minify \
  --cleanDestinationDir \
  --contentDir "$build_dir/hugo/content" \
  --destination "$build_dir/site" \
  --baseURL "$base_url"

python scripts/check_site.py "$build_dir/site" \
  --base-url "$base_url" \
  --projected-records "$build_dir/projected-records.jsonl" \
  --graph "$graph_path" \
  --manifest "$build_dir/site-manifest.sha256"
