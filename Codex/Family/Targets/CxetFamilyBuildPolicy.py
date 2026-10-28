"""Exact core-build exceptions for the CXET family ownership graph."""

from __future__ import annotations

from pathlib import Path

from CMake.Policy.CmakeFamilyBenchmarkRecipe import (
    BENCHMARK_TARGETS, benchmark_target_context,
)


_BENCH_NATIVE = "tools/Benchmarks/native"
_BENCH_RUNTIME = "apps/hft-parser/src/Runtime/include"
_BENCH_EXTRAS = {
    "cxet_bench_core": (_BENCH_NATIVE,),
    "cxet_bench_primitive_candidates": (_BENCH_NATIVE,),
    "parser-bench-session": (_BENCH_RUNTIME,),
    "parser-bench-native-fix": (_BENCH_RUNTIME,),
    "trading-core-bench-strategies": ("apps/trading-core/src/Strategy/include",),
    "trading-core-bench-delivery-strategy": ("apps/trading-core/src/Strategy/include",),
    "trader-bench-hot-trader": ("tools/Testing", _BENCH_RUNTIME),
    "trader-bench-native-lane": (_BENCH_RUNTIME, "tools/Testing"),
    "trader-bench-capacity": (_BENCH_RUNTIME, "tools/Testing"),
    "trader-bench-json-ws": (_BENCH_RUNTIME, "tools/Testing", "src/benchmarks"),
    "trader-bench-vstack": (
        _BENCH_RUNTIME, "apps/hft-parser/src/Process/include",
        "apps/trader/src/Process/src/Traderd/Strategy", "tools/Testing"),
}
BENCHMARK_INCLUDE_CONTRACTS = {
    target + suffix: (origin, (_BENCH_NATIVE, *_BENCH_EXTRAS.get(target, ())))
    for origin, targets in BENCHMARK_TARGETS.items()
    for target in targets for suffix in ("", "_traced")
}


def benchmark_instance_context(instance, target: str) -> bool:
    return (benchmark_target_context(instance.body, target) and
            benchmark_target_context(instance.evaluation, target))


OFFLINE_COMPILE_OPTION_RECIPES = {
    "cxet_offline_primitive_storage": (30, (
        "-fno-builtin-malloc", "-fno-builtin-aligned_alloc", "-fno-builtin-free")),
    **{target: (line, ("-fno-access-control",)) for target, line in (
        ("cxet_offline_optional_identity_primitives", 49),
        ("cxet_offline_optional_busy_poll", 58),
        ("cxet_offline_native_trade_identity", 96),
        ("cxet_offline_terminal_attempt_time", 323),
        ("cxet_offline_transport", 361),
        ("cxet_offline_twime_transport", 368),
        ("cxet_offline_simba_transport", 376),
        ("cxet_offline_ws_cold_admission", 454),
    )},
}
PARSER_OFFLINE_COMPILE_OPTION_RECIPES = {
    target: (line, ("-fno-access-control",)) for target, line in (
        ("hftp_offline_native_account_publication", 206),
        ("hftp_offline_private_subscription_prerequisites", 249),
        ("hftp_offline_private_subscription_plan", 257),
    )
}
_RESIDENT_FIXTURE_SYMBOLS = (
    "sched_getaffinity", "opendir", "readdir", "closedir", "mlock", "syscall")
PARSER_OFFLINE_LINK_OPTION_RECIPES = {
    target: (line, tuple("-Wl,--wrap=" + symbol for symbol in _RESIDENT_FIXTURE_SYMBOLS))
    for target, line in (
        ("hftp_offline_cases", 277),
        ("hftp_offline_capture_subscription", 280),
        ("hftp_offline_public_market_catalog", 283),
        ("hftp_offline_selected_wire_config", 286),
        ("hftp_offline_private_subscription_plan", 289),
        ("hftp_offline_kernel_handoff", 292),
        ("hftp_offline_source_recovery", 295),
        ("hftp_offline_cold_reservoir", 298),
        ("hftp_offline_source_recovery_warm", 301),
        ("hftp_offline_native_account_publication", 304),
        ("hftp_offline_native_order_variants", 307),
    )
}
_TRADER_USER_FIXTURE_SYMBOLS = (
    "_ZN4cxet3api4user16startUserSessionERKNS_21UnifiedRequestBuilderERKNS0_12ObjectConfigER13MessageBufferS9_RKNS1_22UserSessionLaneOptionsE",
    "_ZN4cxet3api4user15stopUserSessionERKNS_21UnifiedRequestBuilderERKNS1_22UserSessionLaneOptionsE",
    "_ZN4cxet3api4user18queryUserRaceStateERKNS_18UnifiedRequestSpecEPNS1_13UserRaceStateERKNS1_22UserSessionLaneOptionsE",
    "_ZN4cxet3api4user22bindUserOwnerEventSinkERKNS1_18UserOwnerEventSinkE",
    "_ZN4cxet3api4user24unbindUserOwnerEventSinkEjmPv",
    "_ZN4cxet3api4user25progressUserSessionEventsERKNS_21UnifiedRequestBuilderERKNS0_12ObjectConfigERKNS1_22UserSessionLaneOptionsEPNS1_15UserFrameTimingE",
)
TRADER_OFFLINE_LINK_OPTION_RECIPES = {
    target: (line, tuple("-Wl,--wrap=" + symbol for symbol in symbols))
    for target, line, symbols in (
        ("trader_offline_cases", 15, ("clock_gettime", *_RESIDENT_FIXTURE_SYMBOLS)),
        ("trader_offline_private_cut", 45, _RESIDENT_FIXTURE_SYMBOLS),
        ("trader_offline_finam_full_path", 67,
         (*_RESIDENT_FIXTURE_SYMBOLS, "send", *_TRADER_USER_FIXTURE_SYMBOLS)),
        ("trader_offline_tbank_full_path", 94,
         (*_RESIDENT_FIXTURE_SYMBOLS, *_TRADER_USER_FIXTURE_SYMBOLS)),
        ("trader_offline_strategy_runtime", 126, _RESIDENT_FIXTURE_SYMBOLS),
        ("trader_offline_service_admission", 164, ("clock_gettime",)),
        ("trader_offline_alert_facts", 179, ("fsync",)),
        ("trader_offline_parallel_pipeline_recovery", 250, ("clock_gettime",)),
    )
}
DIAGNOSTIC_OFFLINE_LINK_OPTION_RECIPES = {
    "diagnostic_offline_market": (
        14, tuple("-Wl,--wrap=" + symbol for symbol in _RESIDENT_FIXTURE_SYMBOLS)),
}
OFFLINE_LINK_OPTION_RECIPES = {
    target: (line, tuple("-Wl,--wrap=" + symbol for symbol in symbols))
    for target, line, symbols in (
        ("cxet_offline_resident_memory", 5, (
            "mmap", "munmap", "mlock", "sched_getaffinity", "sched_setaffinity", "sysconf",
            "opendir", "readdir", "closedir", "syscall")),
        ("cxet_offline_primitive_storage", 28, ("malloc", "aligned_alloc", "free")),
        ("cxet_offline_optional_busy_poll", 59, (
            "setsockopt", "accept", "fcntl", "close", "io_uring_register_napi", "io_uring_enter2")),
        ("cxet_offline_private_contract_lowering", 103, (
            "_ZN4cxet7network2ws9WsRuntime12releaseFrameERKNS1_11WsFrameViewE",
            *_RESIDENT_FIXTURE_SYMBOLS)),
        ("cxet_offline_finam_private_contracts", 295, _RESIDENT_FIXTURE_SYMBOLS),
        ("cxet_offline_terminal_attempt_time", 324, ("send", *_RESIDENT_FIXTURE_SYMBOLS)),
        ("cxet_offline_general_json", 337, ("_ZnamRKSt9nothrow_t",)),
        ("cxet_offline_transport", 356, _RESIDENT_FIXTURE_SYMBOLS),
        ("cxet_offline_twime_transport", 369, ("send", "recv")),
        ("cxet_offline_simba_transport", 377, ("socket", "setsockopt", "bind", "recvmsg", "close")),
        ("cxet_offline_tls_terminal", 385, ("send", *_RESIDENT_FIXTURE_SYMBOLS)),
        ("cxet_offline_crypto_primitives", 391, ("malloc", "calloc", "realloc", "free", "getrandom")),
        ("cxet_offline_core_api", 402, ("socket", "connect", "sendto", "recvfrom", "poll",
                                          *_RESIDENT_FIXTURE_SYMBOLS)),
        ("cxet_offline_grpc_buffered_poll", 429, (
            "recv", "send", "socket", "connect", "setsockopt", "close", "poll", "getsockopt",
            *_RESIDENT_FIXTURE_SYMBOLS)),
        ("cxet_offline_market_preparation", 432, _RESIDENT_FIXTURE_SYMBOLS),
        ("cxet_offline_account_query_runtime", 438, _RESIDENT_FIXTURE_SYMBOLS),
        ("cxet_offline_ws_cold_admission", 449, _RESIDENT_FIXTURE_SYMBOLS),
        ("cxet_offline_order_lifecycle", 460, _RESIDENT_FIXTURE_SYMBOLS),
        ("cxet_offline_order_correlation", 468, _RESIDENT_FIXTURE_SYMBOLS),
        ("cxet_offline_tls_records", 524, _RESIDENT_FIXTURE_SYMBOLS),
        ("cxet_offline_tls_handshake", 527, _RESIDENT_FIXTURE_SYMBOLS),
        ("cxet_offline_market_continuity", 531, _RESIDENT_FIXTURE_SYMBOLS),
    )
}
OFFLINE_LIBURING_INCLUDE = "$<TARGET_PROPERTY:liburing::uring,INTERFACE_INCLUDE_DIRECTORIES>"
_OFFLINE_INCLUDE_RECIPES = {
    "cxet_offline_optional_busy_poll": (53, (
        "tools/Testing", "src/src/Core/src", OFFLINE_LIBURING_INCLUDE)),
    "cxet_offline_terminal_attempt_time": (327, (
        "src/src/Core/src", OFFLINE_LIBURING_INCLUDE)),
    "cxet_offline_transport": (359, (OFFLINE_LIBURING_INCLUDE,)),
    "cxet_offline_tls_terminal": (382, ("tools/Testing", "src/src/Core/src")),
    "cxet_offline_crypto_primitives": (386, (
        "tools/Testing", "src/src/Core/src/Crypto", "extra/mbedtls-cold/library")),
}


def exact_offline_options(instance, command: str, recipes, *, owner="CXETCPP") -> bool:
    from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    tokens = [value for group in instance.token_groups for value in group]
    if not tokens or tokens[0] not in recipes:
        return False
    target = tokens[0]
    line, values = recipes[target]
    expected = [target, "PRIVATE", *values]
    registration = offline_registration(instance, target)
    origin = ("src/tests/offline/CMakeLists.txt" if owner == "CXETCPP" else
              f"apps/{owner}/tests/offline/CMakeLists.txt")
    return (registration is not None and registration.owner == owner and
            registration.relative == origin and
            instance.body.command.name == command and
            instance.body.command.line == line and
            cmake_list_words(instance.body.command.body) == expected and tokens == expected)


def registered_offline_include_roots(instance, target: str) -> tuple[str, ...]:
    """Only the validated helper's explicit PRIVATE include recipe grants roots."""
    import posixpath
    from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    registration = offline_registration(instance, target)
    if registration is None or instance.body.command.name != "target_include_directories":
        return ()
    values = ("${CMAKE_SOURCE_DIR}/tools/Testing", *registration.includes)
    if cmake_list_words(instance.body.command.body) != [target, "PRIVATE", *values]:
        return ()
    root = Path(__file__).resolve().parents[4]
    source = root / Path(registration.relative).parent
    result = []
    for value in values:
        expanded = value.replace("${CMAKE_SOURCE_DIR}", root.as_posix()).replace(
            "${CMAKE_CURRENT_SOURCE_DIR}", source.as_posix())
        if any(marker in expanded for marker in ("${", "$ENV{", "$CACHE{", "$<", ";", "\\")):
            return ()
        path = Path(posixpath.normpath(expanded))
        if not path.is_absolute():
            path = Path(posixpath.normpath((source / path).as_posix()))
        try:
            result.append(path.relative_to(root).as_posix())
        except ValueError:
            return ()
    actual = [value for group in instance.token_groups for value in group]
    expected = [target, "PRIVATE", *(value.replace("${CMAKE_SOURCE_DIR}", root.as_posix()).replace(
        "${CMAKE_CURRENT_SOURCE_DIR}", Path(registration.relative).parent.as_posix()) for value in values)]
    if actual != expected:
        return ()
    return tuple(result)


def exact_offline_include_roots(instance, target: str) -> tuple[str, ...]:
    from CMake.Policy.CmakeFamilyOfflineRecipe import offline_instance_context
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    recipe = _OFFLINE_INCLUDE_RECIPES.get(target)
    if recipe is None or not offline_instance_context(instance, target):
        return ()
    line, roots = recipe
    raw = [target, "PRIVATE", *(root if root == OFFLINE_LIBURING_INCLUDE else
                               "${CMAKE_SOURCE_DIR}/" + root for root in roots)]
    return roots if (instance.body.command.name == "target_include_directories" and
                     instance.body.command.line == line and
                     cmake_list_words(instance.body.command.body) == raw) else ()


_OFFLINE_EXTERNAL_LIBRARIES = {
    "cxet_offline_private_contract_lowering": (100, ("cxet::cxet_lib", "OpenSSL::SSL")),
    "cxet_offline_tls_terminal": (382, (
        "OpenSSL::SSL", "cxet::cxet_lib", "cxet_native_tls", "liburing::uring")),
    "cxet_offline_tls_handshake": (396, ("cxet_native_tls", "OpenSSL::SSL")),
    "cxet_offline_grpc_buffered_poll": (427, ("cxet::cxet_lib", "OpenSSL::SSL")),
    "cxet_offline_queue_threads": (479, ("cxet::read_only_contracts", "Threads::Threads")),
}


def exact_offline_external_link(instance, target: str, dependency: str) -> bool:
    from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
    registration = offline_registration(instance, target)
    recipe = _OFFLINE_EXTERNAL_LIBRARIES.get(target)
    return bool(registration is not None and recipe is not None and
                dependency in recipe[1] and registration.libraries == recipe[1] and
                exact_offline_options(instance, "target_link_libraries", _OFFLINE_EXTERNAL_LIBRARIES))


def offline_liburing_include_context(instance, target: str, registry, instances) -> bool:
    """Prove the finite private carrier through its registered native provider."""
    from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
    from CMake.Flow.CmakeFamilyFlow import bounded_merge, paths_cover
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    registration = offline_registration(instance, target)
    expected_libraries = {
        "cxet_offline_optional_busy_poll": ("cxet::cxet_lib",),
        "cxet_offline_terminal_attempt_time": ("cxet::cxet_lib",),
        "cxet_offline_transport": ("cxet::cxet_lib", "cxet_crypto"),
    }.get(target)
    if (registration is None or expected_libraries is None or registry is None or
            registration.libraries != expected_libraries or
            OFFLINE_LIBURING_INCLUDE not in exact_offline_include_roots(instance, target)):
        return False
    declaration = registry.context_for_use(target, instance)
    if declaration is None or offline_registration(declaration, target) is not registration:
        return False
    core = registry.resolve("cxet_lib", instance, require_prior=True, report=False)
    imported = registry.exact_prior_imported("liburing::uring", instance)
    if not core or not imported:
        return False
    evidence = []
    for candidate in instances:
        if (candidate.body.command.name != "target_link_libraries" or
                candidate.body.command.line != declaration.body.command.line or
                offline_registration(candidate, target) is not registration):
            continue
        expected = [target, "PRIVATE", *expected_libraries]
        if (cmake_list_words(candidate.body.command.body) == expected and
                [value for group in candidate.token_groups for value in group] == expected and
                registry.resolve("cxet_lib", candidate, require_prior=True, report=False)):
            evidence.append(candidate.path_alternatives)
    failures: list[str] = []
    coverage = bounded_merge(failures, "offline liburing include provider", *evidence)
    return not failures and paths_cover(universe=instance.path_alternatives, evidence=coverage)


ROOT = Path(__file__).resolve().parents[4]
_LIBURING_INSTALL = (
    "__CXET_CMAKE_BINARY__/src/src/_deps/liburing/install")


def exact_target_alias(instance) -> bool:
    tokens = [value for group in instance.token_groups for value in group]
    return (
        instance.body.command.name in {"add_library", "add_executable"} and
        len(tokens) == 3 and tokens[1] == "ALIAS"
    )


def exact_liburing_import(instance, targets: list[str], tail: set[str]) -> bool:
    tokens = [
        value for group in instance.token_groups for value in group]
    return (
        instance.body.relative == "src/src/CMakeLists.txt" and
        instance.evaluation.source_base == Path("src/src") and
        instance.evaluation.binary_base == Path("src/src") and
        instance.body.command.name == "add_library" and
        targets == ["liburing::uring"] and
        tokens == ["liburing::uring", "STATIC", "IMPORTED", "GLOBAL"]
    )


def target_declaration_errors(
    instance,
    targets: list[str],
    tail: set[str],
    approved_external_items: frozenset[str],
) -> list[str]:
    exact_external = exact_liburing_import(instance, targets, tail)
    result: list[str] = []
    tokens = [
        value for group in instance.token_groups for value in group]
    upper = [value.upper() for value in tokens]
    if "ALIAS" in upper and not exact_target_alias(instance):
        result.append(
            f"malformed target alias declaration {tokens}; ALIAS must be the "
            "exact second token")
    if "IMPORTED" in upper and not exact_external:
        result.append(
            f"unapproved first-party imported target declaration {targets}")
    external = [
        target for target in targets if target in approved_external_items
    ]
    if external and not exact_external:
        result.append(
            "first-party declaration/alias occupies approved external "
            "spelling(s): " + ", ".join(external))
    return result


def exact_liburing_property(instance, mutation) -> bool:
    expected = {
        "IMPORTED_LOCATION": (
            _LIBURING_INSTALL + "/lib/liburing.a",
        ),
        "INTERFACE_INCLUDE_DIRECTORIES": (
            _LIBURING_INSTALL + "/include",
        ),
    }
    return (
        instance.body.relative == "src/src/CMakeLists.txt" and
        instance.evaluation.source_base == Path("src/src") and
        instance.evaluation.binary_base == Path("src/src") and
        instance.body.command.name == "set_target_properties" and
        mutation.target == "liburing::uring" and
        mutation.name in expected and
        not mutation.append and
        mutation.values == expected[mutation.name]
    )


def exact_liburing_imported_property(instance, mutation) -> bool:
    """Compatibility name for older callers; value provenance stays exact."""
    return (
        mutation.name == "IMPORTED_LOCATION" and
        exact_liburing_property(instance, mutation)
    )


def approved_cxet_build_dependency(value: str) -> bool:
    return value == "secp256k1"


def approved_cxet_include(value: str) -> bool:
    own_roots = {
        f"$<BUILD_INTERFACE:{(ROOT / 'src/src/Core/include').as_posix()}>",
        f"$<BUILD_INTERFACE:{(ROOT / 'src/src/Contracts/include').as_posix()}>",
        f"$<BUILD_INTERFACE:{(ROOT / 'src/src/Core/src').as_posix()}>",
        f"$<BUILD_INTERFACE:{(ROOT / 'src/src/Core/src/Private').as_posix()}>",
        "$<INSTALL_INTERFACE:include>",
        "$<BUILD_INTERFACE:$<TARGET_PROPERTY:liburing::uring,"
        "INTERFACE_INCLUDE_DIRECTORIES>>",
    }
    if value in own_roots:
        return True
    return value == (
        "$<$<BOOL:" + _LIBURING_INSTALL + ">:" +
        _LIBURING_INSTALL + "/include>")


def ownership_sensitive_property_error(
    canonical_target: str,
    mutation,
) -> str | None:
    if (canonical_target == "cxet_lib" and mutation.name in {
            "INCLUDE_DIRECTORIES", "INTERFACE_INCLUDE_DIRECTORIES"}):
        bad = [
            value for value in mutation.values
            if not approved_cxet_include(value)
        ]
        return f"unapproved cxet_lib include carriers {bad}" if bad else None
    if (canonical_target == "cxet_lib" and
            mutation.name == "MANUALLY_ADDED_DEPENDENCIES"):
        bad = [
            value for value in mutation.values
            if not approved_cxet_build_dependency(value)
        ]
        return f"unapproved cxet_lib property dependencies {bad}" if bad else None
    if "LINK" in mutation.name or "PRECOMPILE_HEADERS" in mutation.name:
        return f"unsupported ownership-sensitive property {mutation.name}"
    return None
