#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

metadata_root=${METADATA_ROOT:-metadata}
build_dir=${BUILD_DIR:-build}
base_url=${BASE_URL:-http://127.0.0.1:1313/}
port=${DUMPTHINGS_PORT:-8111}
service_url="http://127.0.0.1:${port}"

uv sync --locked --quiet
uv run python scripts/prepare_build.py \
  --metadata-root "$metadata_root" \
  --build-dir "$build_dir"

service_log="$build_dir/dump-things.log"
uv run dump-things-service \
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

records_root="$metadata_root/records"
uv run python scripts/validate_records.py "$records_root" \
  --service-url "$service_url" \
  --report "$build_dir/validation-report.json"
uv run python scripts/test_validation_gate.py \
  --build-dir "$build_dir" \
  --service-url "$service_url"
uv run python scripts/check_relationships.py "$records_root" \
  --report "$build_dir/relationship-report.json"
uv run python scripts/test_relationship_gate.py \
  --records-root "$records_root" \
  --build-dir "$build_dir"

export DTC_TOKEN=preview-reader
export DUMPTHINGS_APIURL="$service_url"
export DUMPTHINGS_TOKEN=preview-reader
export QRI_RECORD_CACHE="$build_dir/qri-cache.json"

uv run dtc get-records "$service_url" research_info \
  | tee "$build_dir/records.jsonl" \
  | uv run qri cache >/dev/null
[[ "$(wc -l < "$build_dir/records.jsonl" | tr -d ' ')" == 5 ]]

output_root="$build_dir/hugo/content"
uv run qri list --pid ror:04tfhh831 \
  | uv run python scripts/enrich_projection.py --output-root "$output_root" \
  | uv run qri render-record page_templates/homepage.md.j2 '{output_path}'
uv run qri list --class xyzri:XYZPerson \
  | uv run python scripts/enrich_projection.py --output-root "$output_root" \
  | uv run qri render-record page_templates/person.md.j2 '{output_path}'
uv run qri list --class xyzri:XYZProject \
  | uv run python scripts/enrich_projection.py --output-root "$output_root" \
  | uv run qri render-record page_templates/project.md.j2 '{output_path}'
uv run qri list --class xyzri:XYZPublication \
  | uv run python scripts/enrich_projection.py --output-root "$output_root" \
  | uv run qri render-record page_templates/publication.md.j2 '{output_path}'
uv run qri list --class xyzri:XYZInstrument \
  | uv run python scripts/enrich_projection.py --output-root "$output_root" \
  | uv run qri render-record page_templates/instrument.md.j2 '{output_path}'

if [[ -n "${HUGO_BIN:-}" ]]; then
  hugo_bin=$HUGO_BIN
elif command -v hugo >/dev/null 2>&1 && hugo version | grep -q 'v0.154.5'; then
  hugo_bin=$(command -v hugo)
else
  hugo_bin=$(scripts/install-hugo.sh)
fi
"$hugo_bin" version | grep -q 'v0.154.5.*extended'
"$hugo_bin" \
  --minify \
  --cleanDestinationDir \
  --contentDir "$build_dir/hugo/content" \
  --destination "$build_dir/site" \
  --baseURL "$base_url"

uv run python scripts/check_site.py "$build_dir/site" \
  --base-url "$base_url" \
  --manifest "$build_dir/site-manifest.sha256"
