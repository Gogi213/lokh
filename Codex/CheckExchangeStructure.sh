#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exchange_source_root="$repo_root/src/src/Core/src/Exchanges"
exchange_include_root="$repo_root/src/src/Core/include/cxet/Exchanges"
network_source_root="$repo_root/src/src/Core/src/Network"
network_include_root="$repo_root/src/src/Core/include/cxet/Network"
exchange_roots=("$exchange_source_root" "$exchange_include_root")
network_roots=("$network_source_root" "$network_include_root")
register_all="$exchange_source_root/RegisterAll.cpp"
failed=0

for required_root in "${exchange_roots[@]}" "${network_roots[@]}"; do
  [[ -d "$required_root" ]] || {
    echo "missing source root: $required_root" >&2
    exit 2
  }
done
[[ -r "$register_all" ]] || { echo "missing registrar: $register_all" >&2; exit 2; }

for exchange_root in "${exchange_roots[@]}"; do
  for legacy_tree in parse transform sbe; do
    if [[ -e "$exchange_root/$legacy_tree" ]]; then
      echo "legacy exchange ownership tree is forbidden: $exchange_root/$legacy_tree" >&2
      failed=1
    fi
  done
done

for network_root in "${network_roots[@]}"; do
  for legacy_network_tree in \
    "$network_root/grpc/request" \
    "$network_root/rest/request" \
    "$network_root/rest/transport" \
    "$network_root/ws/request"; do
    if [[ -d "$legacy_network_tree" ]] &&
       find "$legacy_network_tree" -type f -print -quit | rg -q .; then
      echo "venue-owned wire tree is forbidden under network: $legacy_network_tree" >&2
      failed=1
    fi
  done
done

intentional_product_root_file() {
  case "$(basename "$1")" in
    Config.cpp | Config.hpp | EndpointProfiles.hpp | TradingControlAccount.hpp | *FastOrder.hpp | \
    *PrivateProfile.hpp | KucoinTimestamp.hpp)
      return 0
      ;;
  esac
  return 1
}

while IFS= read -r product_dir; do
  while IFS= read -r root_file; do
    if ! intentional_product_root_file "$root_file"; then
      echo "exchange product root file has no facade/config role: $root_file" >&2
      failed=1
    fi
  done < <(find "$product_dir" -maxdepth 1 -type f | LC_ALL=C sort)
done < <(
  find "${exchange_roots[@]}" -mindepth 2 -maxdepth 2 -type d \
    \( -iname fapi -o -iname spot -o -iname swap -o -iname uta -o \
       -iname usdt -o -iname futures -o -iname inverse -o -iname linear -o \
       -iname margin -o -iname usdm -o -iname linear_swap \) |
    LC_ALL=C sort
)

while IFS= read -r header; do
  if [[ "$(awk 'NF { ++count } END { print count + 0 }' "$header")" -eq 2 ]] &&
     rg -q '^#pragma once$' "$header" &&
     rg -q '^#include "exchanges/.+"$' "$header"; then
    echo "exchange forwarding header is forbidden: $header" >&2
    failed=1
  fi
done < <(find "${exchange_roots[@]}" -type f -name '*.hpp' | LC_ALL=C sort)

while IFS= read -r register_source; do
  venue="$(basename "$(dirname "$register_source")")"
  function="register${venue^}"
  header="$exchange_include_root/$venue/$(basename "${register_source%.cpp}").hpp"
  if [[ ! -f "$header" ]]; then
    echo "missing registrar declaration: $header" >&2
    failed=1
  fi
  count="$( { rg -o "\\b${function}\\s*\\(" "$register_all" || true; } | wc -l)"
  if [[ "$count" -ne 1 ]]; then
    echo "$venue registrar must appear exactly once in RegisterAll.cpp; got $count" >&2
    failed=1
  fi
done < <(find "$exchange_source_root" -mindepth 2 -maxdepth 2 -type f \
            -name 'Register*.cpp' | LC_ALL=C sort)

while IFS= read -r config_source; do
  config_relative="${config_source#"$exchange_source_root/"}"
  config_header="$exchange_include_root/${config_relative%.cpp}.hpp"
  if [[ ! -f "$config_header" ]]; then
    echo "missing config declaration: $config_header" >&2
    failed=1
  fi
done < <(find "$exchange_source_root" -type f -name Config.cpp | LC_ALL=C sort)

if find "${exchange_roots[@]}" -type f \
    \( -iname '*placeholder*' -o -iname '*skeleton*' \) -print | rg -q .; then
  find "${exchange_roots[@]}" -type f \
    \( -iname '*placeholder*' -o -iname '*skeleton*' \) -print
  echo "placeholder/skeleton exchange file is forbidden" >&2
  failed=1
fi

if find "${exchange_roots[@]}" -type f \
    \( -iname '*.def' -o -iname '*.inc' \) -print | rg -q .; then
  find "${exchange_roots[@]}" -type f \
    \( -iname '*.def' -o -iname '*.inc' \) -print
  echo "legacy exchange .def/.inc fragment is forbidden; use .ipp" >&2
  failed=1
fi

declare -A first_path_by_hash=()
while IFS= read -r record; do
  hash="${record%% *}"
  path="${record#*  }"
  previous="${first_path_by_hash[$hash]:-}"
  if [[ -z "$previous" ]]; then
    first_path_by_hash["$hash"]="$path"
    continue
  fi
  echo "unexpected exact exchange duplicate:" >&2
  echo "  $previous" >&2
  echo "  $path" >&2
  failed=1
done < <(
  find "${exchange_roots[@]}" -type f \
    \( -name '*.hpp' -o -name '*.ipp' -o -name '*.cpp' \) \
    -size +0c -print0 |
    xargs -0 sha256sum |
    LC_ALL=C sort
)

exit "$failed"
