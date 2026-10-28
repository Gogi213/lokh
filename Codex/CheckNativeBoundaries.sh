#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
canonical_cpp_suffixes=(
  ".asm"
  ".nasm"
  ".c"
  ".c++"
  ".c++m"
  ".cc"
  ".ccm"
  ".cpp"
  ".cppm"
  ".cxx"
  ".cxxm"
  ".def"
  ".h"
  ".hh"
  ".hpp"
  ".hxx"
  ".inc"
  ".inl"
  ".ipp"
  ".ixx"
  ".m"
  ".mm"
  ".mpp"
  ".s"
  ".tcc"
  ".tpp"
)
canonical_cpp_globs=()
for suffix in "${canonical_cpp_suffixes[@]}"; do
  canonical_cpp_globs+=(--iglob "*${suffix}")
done
production_roots=(
  "$repo_root/src/src/Contracts/include"
  "$repo_root/src/src/Contracts/src"
  "$repo_root/src/src/Core/include"
  "$repo_root/src/src/Core/src"
  "$repo_root/src/tests"
  "$repo_root/apps/hft-parser/src/Runtime"
  "$repo_root/apps/hft-parser/src/Process"
  "$repo_root/apps/hft-parser/src/Clients/include"
  "$repo_root/apps/hft-parser/src/Contracts/include"
  "$repo_root/apps/trading-core/src/Core/include"
  "$repo_root/apps/trading-core/src/Strategy/include/strategy"
  "$repo_root/apps/trading-core/src/Core/src"
)
libc_roots=(
  "$repo_root/src/src/Contracts/include"
  "$repo_root/src/src/Contracts/src"
  "$repo_root/src/src/Core/include"
  "$repo_root/src/src/Core/src"
  "$repo_root/apps/hft-parser/src/Runtime"
  "$repo_root/apps/hft-parser/src/Process"
  "$repo_root/apps/hft-parser/src/Clients/include"
  "$repo_root/apps/hft-parser/src/Contracts/include"
  "$repo_root/apps/trading-core/src/Core/include"
  "$repo_root/apps/trading-core/src/Strategy/include/strategy"
  "$repo_root/apps/trading-core/src/Core/src"
)
build_roots=(
  "$repo_root/CMakeLists.txt"
  "$repo_root/src/src/CMakeLists.txt"
  "$repo_root/apps/hft-parser/CMakeLists.txt"
  "$repo_root/apps/hft-parser/compile.sh"
  "$repo_root/apps/trading-core/CMakeLists.txt"
  "$repo_root/apps/trading-core/compile.sh"
  "$repo_root/apps/hft-backtest/CMakeLists.txt"
  "$repo_root/apps/hft-backtest/compile.sh"
  "$repo_root/apps/trader/CMakeLists.txt"
  "$repo_root/apps/trader/compile.sh"
  "$repo_root/apps/vetron/CMakeLists.txt"
  "$repo_root/apps/vetron/compile.sh"
)

# Missing retired/optional roots are not scan inputs. Existing unreadable roots
# remain inputs so rg/find failures cannot be promoted to a clean boundary.
root_is_present() {
  /usr/bin/python3 -I -S -c '
import os, sys
try:
    os.lstat(sys.argv[1])
except FileNotFoundError:
    sys.exit(1)
except OSError as error:
    print("native boundary scan failed: cannot inspect root: " + str(error), file=sys.stderr)
    sys.exit(2)
' "$1"
}

keep_existing_roots() {
  local -n values="$1"
  local root status
  local kept=()
  for root in "${values[@]}"; do
    if root_is_present "$root"; then
      kept+=("$root")
    else
      status=$?
      ((status == 1)) || return "$status"
    fi
  done
  values=("${kept[@]}")
}
for roots in production_roots libc_roots build_roots; do
  keep_existing_roots "$roots"
done

failed=0

check_source_forbidden() {
  local label="$1" pattern="$2" scan_status=0
  shift 2
  (( $# > 0 )) || return 0
  rg -n --hidden --no-ignore "${canonical_cpp_globs[@]}" \
      --glob '!**/.git/**' --glob '!**/build*/**' \
      --glob '!**/build-cxet-runtime/**' --glob '!**/extra/**' \
      "$pattern" "$@" || scan_status=$?
  if ((scan_status == 0)); then
    echo "native boundary violation: $label" >&2
    failed=1
  elif ((scan_status != 1)); then
    echo "native boundary scan failed: $label (rg exit $scan_status)" >&2
    failed=1
  fi
}

check_build_forbidden() {
  local label="$1" pattern="$2" scan_status=0
  shift 2
  (( $# > 0 )) || return 0
  rg -n "$pattern" "$@" || scan_status=$?
  if ((scan_status == 0)); then
    echo "native boundary violation: $label" >&2
    failed=1
  elif ((scan_status != 1)); then
    echo "native boundary scan failed: $label (rg exit $scan_status)" >&2
    failed=1
  fi
}

scan_matches() {
  local scan_status=0
  rg "$@" || scan_status=$?
  if ((scan_status > 1)); then
    echo "native boundary scan failed (rg exit $scan_status)" >&2
    return "$scan_status"
  fi
}

check_stale_source_root() {
  local label="$1"
  local root="$2"
  local find_status=0
  local hit=""

  if root_is_present "$root"; then
    :
  else
    local status=$?
    if ((status != 1)); then
      failed=1
    fi
    return
  fi
  if [[ -L "$root" || ! -d "$root" ]]; then
    echo "native boundary violation: stale source root is not a physical directory: $label" >&2
    failed=1
    return
  fi

  hit="$(
    find "$root" -mindepth 1 \( -type f -o -type l \) -print -quit
  )" || find_status=$?
  if ((find_status != 0)); then
    echo "native boundary violation: stale source root cannot be traversed: $label" >&2
    failed=1
    return
  fi
  if [[ -n "$hit" ]]; then
    printf '%s\n' "$hit"
    echo "native boundary violation: stale source root reintroduced: $label" >&2
    failed=1
  fi
}

check_stale_source_root "apps/hft-trader/strategy" \
  "$repo_root/apps/hft-trader/strategy"
check_stale_source_root "apps/hft-trader/strategy_profiles" \
  "$repo_root/apps/hft-trader/strategy_profiles"
check_stale_source_root "apps/hft-trader/src/Core/include/hft_trader/api" \
  "$repo_root/apps/hft-trader/src/Core/include/hft_trader/api"
check_stale_source_root "apps/hft-trader/src/Core/include/hft_trader/core" \
  "$repo_root/apps/hft-trader/src/Core/include/hft_trader/core"
check_stale_source_root "apps/hft-trader/src/Core/include/hft_trader/market" \
  "$repo_root/apps/hft-trader/src/Core/include/hft_trader/market"

check_source_forbidden "simdjson dependency" \
  'simdjson|SIMDJSON|toPaddedView|kSimdjsonPadding' \
  "${production_roots[@]}"
check_build_forbidden "simdjson build dependency" \
  'simdjson|SIMDJSON|toPaddedView|kSimdjsonPadding' \
  "${build_roots[@]}"
check_source_forbidden "Boost dependency" \
  '#include[[:space:]]*[<"]boost/|\bboost::|\bBoost::|find_package[[:space:]]*\([[:space:]]*Boost' \
  "${production_roots[@]}"
check_build_forbidden "Boost build dependency" \
  '\bBoost::|find_package[[:space:]]*\([[:space:]]*Boost' \
  "${build_roots[@]}"
check_source_forbidden "std::string_view borrowed text" \
  '#include[[:space:]]*<string_view>|\bstd::string_view\b' \
  "${production_roots[@]}"

legacy_fragment_hits=""
if ((${#production_roots[@]})); then
  legacy_fragment_hits="$(find "${production_roots[@]}" -type f \
    \( -iname '*.def' -o -iname '*.inc' \) -print)" || {
      echo 'native boundary scan failed: legacy fragments' >&2
      failed=1
    }
fi
if [[ -n "$legacy_fragment_hits" ]]; then
  printf '%s\n' "$legacy_fragment_hits"
  echo "native boundary violation: legacy .def/.inc fragment; use .ipp" >&2
  failed=1
fi

# Project primitives are the explicit libc implementation boundary.
libc_hits=""
if ((${#libc_roots[@]})); then
  libc_hits="$(scan_matches -n --hidden --no-ignore "${canonical_cpp_globs[@]}" \
    --glob '!**/.git/**' --glob '!**/build*/**' \
    --glob '!**/build-cxet-runtime/**' --glob '!**/extra/**' \
    '(?:\bstd::|::|\b)(?:memcpy|memmove|memset|memcmp|memchr|strlen|strnlen|strcmp|strncmp|strchr|strrchr|strstr|strcpy|strncpy|strcat|strncat)\s*\(' \
    "${libc_roots[@]}")" || failed=1
  if [[ -n "$libc_hits" ]]; then
    filter_status=0
    libc_hits="$(printf '%s\n' "$libc_hits" | rg -v '/Primitives/Buf/(AsmPrimitives|CStringPrimitives)\.hpp:')" || filter_status=$?
    if ((filter_status > 1)); then
      echo 'native boundary scan failed: libc exclusions' >&2
      failed=1
    fi
  fi
fi
if [[ -n "$libc_hits" ]]; then
  printf '%s\n' "$libc_hits"
  echo "native boundary violation: direct libc string/memory primitive" >&2
  failed=1
fi

virtual_roots=(
  "$repo_root/src/src/Contracts/include" "$repo_root/src/src/Contracts/src"
  "$repo_root/src/src/Core/include" "$repo_root/src/src/Core/src"
  "$repo_root/apps/trading-core/src/Core/include"
  "$repo_root/apps/trading-core/src/Strategy/include/strategy"
  "$repo_root/apps/trading-core/src/Core/src"
)
keep_existing_roots virtual_roots
virtual_hits=""
if ((${#virtual_roots[@]})); then
  virtual_hits="$(scan_matches -n --hidden --no-ignore "${canonical_cpp_globs[@]}" \
    --glob '!**/.git/**' --glob '!**/build*/**' \
    --glob '!**/build-cxet-runtime/**' --glob '!**/extra/**' \
    '^[[:space:]]*virtual[[:space:]]|\bdynamic_cast\b|\btypeid\s*\(' \
    "${virtual_roots[@]}")" || failed=1
fi
if [[ -n "$virtual_hits" ]]; then
  printf '%s\n' "$virtual_hits"
  echo "native boundary violation: virtual/RTTI in native source" >&2
  failed=1
fi

exit "$failed"
