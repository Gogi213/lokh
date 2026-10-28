"""Static cache profiles emitted by the canonical owner drivers, never presets.

Python expressions are interpreted through a small data-only AST grammar. The
checker never imports or runs the build/test drivers and cannot bootstrap tools.
"""
from __future__ import annotations

import ast
import json
import os
import re
from itertools import product
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from CMake.Policy.CmakeFamilyConditionPolicy import validate_condition_policy_microcases
from CMake.Flow.CmakeFamilyFlowMicrocases import validate_message_terminal_microcases
from CMake.Flow.CmakeFamilyExecutionIdentity import (
    reviewed_file_identity, unsymlinked_regular_path,
)
from CMake.Root.CmakeFamilyRootDialect import (
    RootDialectEvidence, RootProfileEvidence, validate_root_dialect_microcases,
)

ROOT = Path(__file__).resolve().parents[4]
OWNER_DRIVER = "tools/Build/CompileTargets.py"
OFFLINE_DRIVER = "tools/Testing/RunOffline.py"
_REQUIRED_OWNERS = frozenset(("CXETCPP", "hft-parser", "trading-core",
    "hft-backtest", "trader", "vetron", "hft-recorder", "hft-compressor",
    "diagnostic", "TestExchangesHelper"))
_REQUIRED_SANITIZERS = {"release": "none", "address-undefined": "address-undefined",
    "thread": "thread", "fuzz": "address-undefined"}
_ROOT = PurePosixPath("__CXET_REPOSITORY_ROOT__")
_PREPARED_RECIPES = ("cmake/CxetToolchain.cmake", "tools/Toolchain/BootstrapEmscripten.py")
_HOT_FEATURES = {
    'identity-tags': 'CXET_HFT_SIMD_IDENTITY_TAGS',
    'pmadd': 'CXET_HFT_PMADD_DIGITS',
    'pclmul': 'CXET_HFT_PCLMUL_JSON',
    'shuffle': 'CXET_HFT_SHUFFLE_CLASSIFY',
    'reciprocal': 'CXET_HFT_RECIPROCAL_DIVISION',
    'identity-specialized': 'CXET_HFT_IDENTITY_HASH_SPECIALIZED',
    'identity-xxh3': 'CXET_HFT_IDENTITY_HASH_XXH3',
    'napi': 'CXET_ENABLE_NAPI_BUSY_POLL',
}
_PARSER_HOT_FEATURES = frozenset(('pmadd', 'pclmul', 'shuffle', 'reciprocal'))


class ProfileError(ValueError):
    pass


def _wasm_contract(root: Path):
    """Read the reviewed recipe's conditional output identity, not readiness."""
    for relative in _PREPARED_RECIPES:
        path = root / relative
        if (not reviewed_file_identity(relative) or
                not unsymlinked_regular_path(path, root) or
                path.read_bytes() != (ROOT / relative).read_bytes()):
            raise ProfileError(f"unreviewed recipe {relative}")
    contract = (root / _PREPARED_RECIPES[0]).read_text(encoding="utf-8")
    pins = {}
    for name, pattern in (
            ("CXET_EMSCRIPTEN_VERSION", r"[0-9]+\.[0-9]+\.[0-9]+"),
            ("CXET_EMSCRIPTEN_RELEASE_HASH", r"[0-9a-f]{40}"),
            ("CXET_EMSDK_NODE_VERSION", r"[0-9]+\.[0-9]+\.[0-9]+"),
            ("CXET_EMSDK_SOURCE_ARCHIVE_SHA256", r"[0-9a-f]{64}")):
        matches = re.findall(rf'set\({name} "({pattern})"\)', contract)
        if len(matches) != 1:
            raise ProfileError(f"nonunique root pin {name}")
        pins[name] = matches[0]
    return pins


def prepared_wasm_selection(root: Path, errors: list[str]) -> str | None:
    """Select the pinned path from regular install data, never execute tools.

    Absence is distinct from a present but unsupported installation. This does
    not prove the em++/Node version queries performed by validate_install, nor
    does it authorize an arbitrary retained CMake cache or compiler preseed.
    Static source profiles use _wasm_contract independently of install state.
    """
    try:
        pins = _wasm_contract(root)
        version = pins["CXET_EMSCRIPTEN_VERSION"]
        node_version = pins["CXET_EMSDK_NODE_VERSION"]
        release = pins["CXET_EMSCRIPTEN_RELEASE_HASH"]
        prefix = root / "build/toolchains" / f"emsdk-{version}"
        for directory in (root, root / "build", prefix.parent, prefix):
            if directory.is_symlink():
                raise ProfileError(f"symlinked install directory {directory}")
        if not prefix.exists():
            return None
        if not prefix.is_dir():
            raise ProfileError(f"non-directory install prefix {prefix}")
        emxx = prefix / "upstream/emscripten/em++"
        executables = (emxx, prefix / "upstream/emscripten/emcc",
                       prefix / f"node/{node_version}_64bit/bin/node")
        for path in (*executables,
                     prefix / f"node/{node_version}_64bit/lib/node_modules/npm/bin/npm-cli.js"):
            if not unsymlinked_regular_path(path, root):
                raise ProfileError(f"missing/nonregular/symlinked install file {path}")
        if any(not os.access(path, os.X_OK) for path in executables):
            raise ProfileError("prepared compiler/Node is not executable")
        expected = {
            "emsdk_source_archive_sha256": pins["CXET_EMSDK_SOURCE_ARCHIVE_SHA256"],
            "emsdk_source_archive_url": f"https://codeload.github.com/emscripten-core/emsdk/tar.gz/refs/tags/{version}",
            "emscripten_release_hash": release,
            "emscripten_version": version,
            "node_version": node_version,
        }
        def read(relative):
            path = prefix / relative
            if not unsymlinked_regular_path(path, root):
                raise ProfileError(f"missing/nonregular/symlinked install data {path}")
            return path.read_text(encoding="utf-8").strip()
        metadata = json.loads(read(".cxet-emscripten.json"))
        if metadata != expected:
            raise ProfileError("install metadata differs from the root pin")
        for relative, wanted in (
                ("upstream/emscripten/emscripten-version.txt", json.dumps(version)),
                ("upstream/.emsdk_version", f"releases-{release}-64bit"),
                (f"node/{node_version}_64bit/.emsdk_version", f"node-{node_version}-64bit")):
            if read(relative) != wanted:
                raise ProfileError(f"install stamp differs from the root pin: {relative}")
        config = {
            f"NODE_JS = '$CFGDIR/node/{node_version}_64bit/bin/node'",
            "LLVM_ROOT = '$CFGDIR/upstream/bin'", "BINARYEN_ROOT = '$CFGDIR/upstream'",
            "EMSCRIPTEN_ROOT = '$CFGDIR/upstream/emscripten'",
        }
        if set(read(".emscripten").splitlines()) != config:
            raise ProfileError("install configuration differs from the pinned workspace layout")
        return str(emxx)
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError) as exc:
        errors.append(f"unsupported prepared WASM selection: {exc}")
        return None


def _tree(text: str, origin: str):
    try:
        return ast.parse(text, filename=origin)
    except SyntaxError as exc:
        raise ProfileError(f"{origin}: invalid Python: {exc}") from exc


def _literal(tree, name: str):
    entries = [node.value for node in tree.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == name
                       for target in node.targets)]
    if len(entries) != 1:
        raise ProfileError(f"expected exactly one literal {name} authority")
    try:
        return ast.literal_eval(entries[0])
    except (ValueError, TypeError) as exc:
        raise ProfileError(f"non-literal {name} authority") from exc


def _function(tree, name: str):
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == name]
    if len(nodes) != 1:
        raise ProfileError(f"expected exactly one driver function {name}")
    return nodes[0]


def _expression(node, values):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id in values:
        return values[node.id]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_expression(item, values) for item in node.elts]
    if isinstance(node, ast.Dict):
        return {_expression(key, values): _expression(value, values)
                for key, value in zip(node.keys, node.values)}
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "args":
        return getattr(values["args"], node.attr)
    if isinstance(node, ast.Subscript):
        return _expression(node.value, values)[_expression(node.slice, values)]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str" and len(node.args) == 1 and not node.keywords:
        return str(_expression(node.args[0], values))
    if isinstance(node, ast.BinOp):
        left, right = _expression(node.left, values), _expression(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Div) and isinstance(left, PurePosixPath):
            return left / right
    if isinstance(node, ast.IfExp):
        return _expression(node.body if _expression(node.test, values) else node.orelse, values)
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        left, right = _expression(node.left, values), _expression(node.comparators[0], values)
        if isinstance(node.ops[0], ast.Eq):
            return left == right
        if isinstance(node.ops[0], ast.NotEq):
            return left != right
        if (isinstance(node.ops[0], ast.IsNot)
                and isinstance(node.comparators[0], ast.Constant)
                and node.comparators[0].value is None):
            return left is not None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _expression(node.operand, values)
    raise ProfileError("unreviewed dynamic configure expression: " + ast.dump(node))


def _assignment(function, name: str):
    assignments = [node for node in ast.walk(function) if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    if len(assignments) != 1 or assignments[0] not in function.body or not isinstance(assignments[0].value, ast.List):
        raise ProfileError(f"configure must have one literal-list {name} assignment")
    found = assignments[0].value
    emitter = "run" if name == "argv" else "command"
    emitted = [node for node in function.body if isinstance(node, ast.Expr)
               and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
               and node.value.func.id == emitter and len(node.value.args) == 1
               and isinstance(node.value.args[0], ast.Name) and node.value.args[0].id == name]
    if (len(emitted) != 1 or emitted[0].value.keywords or
            emitted[0].lineno < assignments[0].lineno or function.decorator_list):
        raise ProfileError(f"{name} must reach one unconditional canonical configure emitter")
    for node in ast.walk(function):
        if isinstance(node, ast.Return) and node.lineno < emitted[0].lineno:
            raise ProfileError(f"early return can bypass {name} configure emission")
        if isinstance(node, (ast.AugAssign, ast.AnnAssign)) and isinstance(node.target, ast.Name) and node.target.id == name:
            raise ProfileError(f"unreviewed {name} reassignment")
    # Compile mutations are checked as an exact AST sequence by _compile_extras;
    # the offline vector must reach its emitter without mutation.
    for node in ast.walk(function):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == name):
            continue
        if (node.func.attr not in ({"append", "extend"} if name == "argv" else {"extend"}) or
                node.lineno < assignments[0].lineno):
            raise ProfileError(f"unreviewed {name} mutation")
    return found


def _compile_extras(function):
    """Fence the input bindings and actual cold append producer as data."""
    assignment = next(node for node in function.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "argv"
                              for target in node.targets))
    index = function.body.index(assignment)
    prefix = ast.Module(body=function.body[:index], type_ignores=[])
    reviewed_prefix = ast.parse("""
def configure(root, build, owner, portable, *, tests, jobs=1, force=False, benchmarks=False,
              hot_features=(), hft_magic=True, exchanges="all", exchange_profile="all", low=False,
              trader_diagnostic=None, toolchain_profile='pinned', deployment_profile=None, lto=None):
    if deployment_profile is None and lto is not None:
        raise BuildError('explicit LTO selection requires a deployment profile')
    deployment_options = {}
    if deployment_profile is not None:
        if (deployment_profile != 'diagnostic' or owner != 'diagnostic' or tests or force or benchmarks or
                low or not portable or hot_features != () or hft_magic or toolchain_profile != 'pinned' or
                lto not in ('off', 'full')):
            raise BuildError('invalid Diagnostic deployment product configuration')
        deployment_options = {'deployment_profile': deployment_profile, 'lto': lto}
    if toolchain_profile == 'system-diagnostic':
        if owner != 'diagnostic' or tests or force or benchmarks or low:
            raise BuildError('system-diagnostic permits only the cold Diagnostic product/tests without LTO or benchmarks')
        require_system_diagnostic_tree(root, build, BuildError)
        hot_features, hft_magic = (), False
    if benchmarks and (not tests or owner not in BENCHMARK_OWNERS):
        raise BuildError('benchmarks require the supported owner all stage')
    if trader_diagnostic is None:
        trader_diagnostic = owner != 'trader' or tests
    validate_build_profile(build, portable, force, hot_features=hot_features, hft_magic=hft_magic,
                           exchange_profile=exchange_profile, toolchain_profile=toolchain_profile, root=root,
                           **deployment_options)
    profile = os.environ.get('CXET_FAMILY_PROFILE', 'essential')
    if profile not in ('essential', 'full'):
        raise BuildError('CXET_FAMILY_PROFILE must be essential or full')
    if toolchain_profile == 'system-diagnostic' and profile != 'essential':
        raise BuildError('system-diagnostic requires CXET_FAMILY_PROFILE=essential')
    if deployment_profile is not None and profile != 'essential':
        raise BuildError('Diagnostic deployment requires CXET_FAMILY_PROFILE=essential')
    query = build / '.cmake/api/v1/query'
    query.mkdir(parents=True, exist_ok=True)
    for kind in ('codemodel-v2', 'cmakeFiles-v1', 'cache-v2', 'toolchains-v1'):
        (query / kind).touch()
""").body[0]
    if (ast.dump(function.args) != ast.dump(reviewed_prefix.args) or
            function.returns is not None or
            ast.dump(prefix) != ast.dump(ast.Module(body=reviewed_prefix.body, type_ignores=[]))):
        raise ProfileError("unreviewed configure input binding/profile guard prefix")
    tail = ast.Module(body=function.body[index + 1:], type_ignores=[])
    reviewed = ast.parse("""
argv.append('-DCXET_HOT_FEATURE_PROFILE=' + hot_feature_profile(hot_features))
argv.extend('-D' + variable + '=' + ('ON' if hot_features is not None and feature in hot_features else 'OFF')
            for feature, variable in HOT_FEATURES.items()
            if hot_features is not None or feature not in PARSER_HOT_FEATURES)
for kind in ('EXE', 'SHARED', 'MODULE', 'STATIC'):
    flags = '-fuse-ld=lld -Wl,--threads=1' if low and kind != 'STATIC' else ''
    argv.extend(['-DCMAKE_' + kind + '_LINKER_FLAGS=' + flags,
                 '-DCMAKE_' + kind + '_LINKER_FLAGS_RELEASE='])
argv.extend(_offline.compiler_launcher_arguments())
if owner == 'vetron':
    script = root / 'tools/Toolchain/BootstrapEmscripten.py'
    try:
        emxx = run([sys.executable, script, '--print-emxx'], capture=True).strip()
    except BuildError:
        run([sys.executable, script])
        emxx = run([sys.executable, script, '--print-emxx'], capture=True).strip()
    argv.append('-DVETRON_EMXX_EXECUTABLE=' + emxx)
run(argv)
""")
    if ast.dump(tail) != ast.dump(reviewed):
        raise ProfileError("unreviewed hot feature/linker reset/Vetron compiler append producer")
    return tail.body[2].body[1].value.args[0], tail.body[4].body[-1].value.args[0]


def _hot_feature_contract(tree):
    """Review helper semantics without evaluating any driver call or generator."""
    if _literal(tree, "HOT_FEATURES") != _HOT_FEATURES:
        raise ProfileError("canonical hot feature inventory changed")
    parser = [node for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == "PARSER_HOT_FEATURES"
                      for target in node.targets)]
    reviewed_parser = ast.parse(
        "PARSER_HOT_FEATURES = frozenset(('pmadd', 'pclmul', 'shuffle', 'reciprocal'))").body[0]
    if len(parser) != 1 or ast.dump(parser[0]) != ast.dump(reviewed_parser):
        raise ProfileError("canonical parser hot feature inventory changed")
    reviewed_helper = ast.parse('''
def hot_feature_profile(features):
    """None means CPU-admitted parser defaults; an empty tuple means baseline."""
    if features is None:
        return 'default'
    if (not isinstance(features, (tuple, list)) or len(set(features)) != len(features)
            or any(name not in HOT_FEATURES for name in features)
            or {'identity-specialized', 'identity-xxh3'}.issubset(features)):
        raise BuildError('invalid hot feature profile')
    return '+'.join(sorted(features)) or 'none'
''').body[0]
    if ast.dump(_function(tree, "hot_feature_profile")) != ast.dump(reviewed_helper):
        raise ProfileError("unreviewed hot feature profile producer")


def _offline_prefix(function, tree):
    """Prove the emitted LTO value is the reviewed CLI binding, not a preseed."""
    assignment = next(node for node in function.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "configure"
                              for target in node.targets))
    index = function.body.index(assignment)
    reviewed = ast.parse('''
toolchain_profile = getattr(args, "toolchain_profile", "pinned")
toolchain_options = {} if toolchain_profile == "pinned" else {"toolchain_profile": toolchain_profile}
if toolchain_profile == "system-diagnostic":
    if (args.owner not in SYSTEM_DIAGNOSTIC_OWNERS or args.profile != "release" or
            getattr(args, "lto", None) not in (None, "off")):
        raise OfflineError("system-diagnostic requires release/LTO off CXETCPP/trading-core/diagnostic tests")
    require_system_diagnostic_tree(ROOT, directory, OfflineError, tests=True)
    require_system_diagnostic_tools(OfflineError)
else:
    pinned_toolchain()
if args.owner == "vetron":
    tsc = ROOT / "apps/vetron/frontend/node_modules/typescript/bin/tsc"
    if not tsc.is_file():
        raise OfflineError(f"existing frontend TypeScript compiler missing: {tsc}; no npm install attempted")
requested = getattr(args, "target", [])
prepare_only = getattr(args, "prepare_only", False)
lto = getattr(args, "lto", None) or "off"
cache(directory, args.owner, args.profile, required=bool(requested) and not prepare_only, lto=lto,
      **toolchain_options)
''')
    prefix = ast.Module(body=function.body[:index], type_ignores=[])
    following = ast.Module(body=function.body[index + 1:index + 4], type_ignores=[])
    reviewed_following = ast.parse('''
if toolchain_profile == "system-diagnostic":
    configure.extend(["-DCXET_PORTABLE_BUILD=OFF", "-DCXET_ENABLE_HFT_MAGIC=OFF",
                      "-DCXET_DISABLE_HFT_MAGIC=OFF", "-DCXET_HOT_FEATURE_PROFILE=none",
                      "-DCXET_LOCAL_BENCHMARKS=OFF", "-DCXET_BUILD_REPLAY=OFF",
                      "-DCXET_CLANG24_LIFETIME_PROFILE=off"])
configure.extend(compiler_launcher_arguments())
command(configure)
''')
    if (ast.dump(prefix) != ast.dump(reviewed) or
            ast.dump(following) != ast.dump(reviewed_following)):
        raise ProfileError("unreviewed offline configure input binding/emitter prefix")
    def mutations(node):
        return sorted(ast.dump(call) for call in ast.walk(node)
                      if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                      and isinstance(call.func.value, ast.Name) and call.func.value.id == 'configure')
    if mutations(function) != mutations(reviewed_following):
        raise ProfileError("unreviewed offline configure mutation outside its reviewed emitter prefix")
    main = _function(tree, "main")
    branches = [node for node in main.body if isinstance(node, ast.If)
                and ast.dump(node.test) == ast.dump(ast.parse(
                    'args.mode == "codegen"', mode="eval").body)]
    reviewed_tests = ast.parse('''
args.lto = args.lto or "off"
if args.lto == "full" and args.profile != "release":
    parser.error("--lto full requires --profile release; sanitizer profiles retain LTO off")
''')
    if (main.decorator_list or len(branches) != 1 or
            ast.dump(ast.Module(body=branches[0].orelse, type_ignores=[])) !=
            ast.dump(reviewed_tests)):
        raise ProfileError("unreviewed offline tests LTO default/sanitizer guard")


def _cache(arguments, expected, origin):
    if [str(value) for value in arguments[:7]] != ["cmake", "-S", str(_ROOT), "-B", str(_ROOT / "build/static-profile"), "-G", "Unix Makefiles"]:
        raise ProfileError(f"{origin}: configure must select canonical root and Unix Makefiles")
    result = {}
    for argument in arguments[7:]:
        if not isinstance(argument, str) or not argument.startswith("-D") or "=" not in argument:
            raise ProfileError(f"{origin}: unreviewed configure argument {argument!r}")
        key, value = argument[2:].split("=", 1)
        if key in result:
            raise ProfileError(f"{origin}: duplicate cache writer {key}")
        if key in {"CMAKE_C_COMPILER", "CMAKE_CXX_COMPILER", "CMAKE_PROJECT_INCLUDE",
                   "CMAKE_PROJECT_INCLUDE_BEFORE", "CMAKE_PROJECT_TOP_LEVEL_INCLUDES"}:
            raise ProfileError(f"{origin}: compiler/project injection {key}")
        result[key] = value
    expected = {"CMAKE_BUILD_TYPE": "Release", "CXET_TOOLCHAIN_PROFILE": "pinned",
                "CXET_COMPILE_JOBS": "1",
                "CMAKE_TOOLCHAIN_FILE": str(_ROOT / "cmake/CxetToolchain.cmake"),
                "CXET_FULL_BUILD": "OFF", "CXET_FAMILY_SOURCE_GRAPH": "OFF",
                **expected}
    for key, value in expected.items():
        if result.get(key) != value:
            raise ProfileError(f"{origin}: {key} must equal {value!r}, found {result.get(key)!r}")
    if ("VETRON_EMXX_EXECUTABLE" in result and
            result["VETRON_EMXX_EXECUTABLE"] != expected.get("VETRON_EMXX_EXECUTABLE")):
        raise ProfileError(f"{origin}: unreviewed prepared compiler/cache preseed")
    retired = {"CXET_PGO_GENERATE", "CXET_PGO_USE", "CXET_HFT_TRADER_FULL_BUILD",
               "HFT_TRADER_FULL_BUILD", "HFT_TRADER_HOT_MONO_CLOCK_CANDIDATE",
               "CXET_HFT_TRADER_EVENT_LOG_BUILD", "HFT_TRADER_EVENT_LOG_BUILD",
               "CXET_RAW_EXCHANGE_LOG_BUILD", "CXET_OFFLINE_BENCHMARKS",
               "CXET_BENCHHELLO_ONLY"}
    for key in retired:
        if result.get(key, "OFF").upper() not in {"", "OFF", "NO", "FALSE", "N", "0", "IGNORE", "NOTFOUND"}:
            raise ProfileError(f"{origin}: removed diagnostics switch {key} cannot be enabled")
    unexpected = sorted(result.keys() - expected.keys())
    if unexpected:
        raise ProfileError(f"{origin}: unreviewed configure cache writers {unexpected!r}")
    return result


def resolve_root_profile_caches(driver_text: str, errors: list[str], *,
                                offline_text: str | None = None,
                                owners_text: str | None = None,
                                root: Path = ROOT):
    """Extract configure writes and the reviewed static compiler selection.

    Compile evidence covers all exchanges with canonical CPU-admitted parser
    defaults, explicit baseline-none, and CPU-default with HFT magic disabled.
    Custom hot-feature combinations and restricted exchange selections are
    outside this bounded static profile universe; no powerset is inferred.
    This bounded family evidence remains the pinned compiler universe. The
    separate system-Diagnostic and diagnostic deployment branches are exact
    AST-reviewed admission and isolated CMake contracts; neither is selected
    in this profile universe or confers production compiler evidence.
    Offline entries describe fresh caches only. The runtime retained-cache
    compiler guard does not make retained-cache authority part of this model.
    Vetron's compiler path describes the reviewed recipe's output conditional
    on successful validation. Local installation state is not an input to this
    source model. No prepared install, successful Bootstrap query, build, or
    generated WASM is inferred here; prepared_wasm_selection is separate.
    """
    try:
        if offline_text is None:
            offline_text = (root / OFFLINE_DRIVER).read_text()
        if owners_text is None:
            owners_text = (root / "tools/Build/ActiveBuild.py").read_text()
        owners = _literal(_tree(owners_text, "tools/Build/ActiveBuild.py"), "OWNERS")
        if not isinstance(owners, (tuple, list)) or len(owners) != len(set(owners)) or set(owners) != _REQUIRED_OWNERS:
            raise ProfileError("canonical compile owner inventory changed")
        driver_tree = _tree(driver_text, OWNER_DRIVER)
        _hot_feature_contract(driver_tree)
        driver = _function(driver_tree, "configure")
        expression = _assignment(driver, "argv")
        linker_reset, compiler_append = _compile_extras(driver)
        offline_tree = _tree(offline_text, OFFLINE_DRIVER)
        budgets = _literal(offline_tree, "BUDGETS")
        sanitizers = _literal(offline_tree, "SANITIZERS")
        if not isinstance(budgets, dict) or not set(budgets) <= set(owners) or not budgets or any(type(v) is not int or v <= 0 for v in budgets.values()):
            raise ProfileError("offline owners/budgets must be positive canonical owner entries")
        if sanitizers != _REQUIRED_SANITIZERS:
            raise ProfileError("offline sanitizer profile mapping changed")
        offline_function = _function(offline_tree, "run_owner")
        offline = _assignment(offline_function, "configure")
        _offline_prefix(offline_function, offline_tree)
        pins = _wasm_contract(root)
        selected = str(_ROOT / "build/toolchains" /
                       f"emsdk-{pins['CXET_EMSCRIPTEN_VERSION']}" /
                       "upstream/emscripten/em++")
        profiles = {}
        hot_profiles = ((None, True, ""), ((), True, ":hot-none"),
                        (None, False, ":no-magic"))
        for owner, portable, force, tests, family, hot in product(
                owners, (False, True), (False, True), (False, True),
                ("essential", "full"), hot_profiles):
            hot_features, hft_magic, suffix = hot
            hot_profile = "default" if hot_features is None else "none"
            values = dict(root=_ROOT, build=_ROOT / "build/static-profile", owner=owner,
                          portable=portable, force=force, tests=tests, jobs=1, profile=family,
                          toolchain_profile='pinned', deployment_profile=None, lto=None,
                          low=False, flags='',
                          trader_diagnostic=owner != 'trader' or tests,
                          hot_features=hot_features, hft_magic=hft_magic,
                          exchanges="all", exchange_profile="all",
                          benchmarks=tests and owner in {"CXETCPP", "hft-parser", "trading-core", "trader"})
            expected = {"CXET_BUILD_OWNER": owner, "CXET_FAMILY_PROFILE": family,
                        "CXET_LOCAL_TESTS": "ON" if tests else "OFF",
                        "CXET_LOCAL_BENCHMARKS": "ON" if values['benchmarks'] else "OFF",
                        "CXET_PORTABLE_BUILD": "ON" if portable else "OFF",
                        "CXET_LTO": "ON" if force else "OFF", "CXET_SANITIZER_PROFILE": "none",
                        "CXET_DIAGNOSTIC_DEPLOY": "OFF",
                        "CXET_EXCHANGES": "all", "CXET_EXCHANGE_PRESET": "",
                        "CXET_BUILD_REPLAY": "OFF", "CXET_SAFETY_BUILD": "OFF",
                        "CXET_NO_EXCEPTIONS_RTTI": "OFF", "CMAKE_C_FLAGS": "",
                        "CMAKE_CXX_FLAGS": "-stdlib=libstdc++",
                        "CXET_CLANG24_LIFETIME_PROFILE": "off", "CXET_MACHINE_SAFETY_AUDIT": "OFF",
                        "CXET_DISABLE_HFT_MAGIC": "OFF", "CXET_ENABLE_HFT_MAGIC": "ON" if hft_magic else "OFF",
                        "CXET_SECP256K1_NATIVE_OPT": "OFF" if portable else "ON",
                        "CXET_HOT_FEATURE_PROFILE": hot_profile}
            enabled_diagnostic = "ON" if values['trader_diagnostic'] else "OFF"
            expected.update(CXET_TRADER_DIAGNOSTIC=enabled_diagnostic,
                            CXET_TRADER_EXTERNAL_OUTPUTS=enabled_diagnostic,
                            HFT_PARSER_CANDLE_HISTORY=enabled_diagnostic,
                            TRADING_CORE_STRATEGY_SELECTION='all' if values['trader_diagnostic'] else
                                'delivery_sum_signal,pair_api_probe')
            arguments = _expression(expression, values)
            # The exact generator/helper AST was reviewed above. Interpret its
            # two supported selections as data rather than executing either.
            arguments.append("-DCXET_HOT_FEATURE_PROFILE=" + hot_profile)
            for feature, variable in _HOT_FEATURES.items():
                if hot_features is not None or feature not in _PARSER_HOT_FEATURES:
                    expected[variable] = "OFF"
                    arguments.append("-D" + variable + "=OFF")
            for kind in ("EXE", "SHARED", "MODULE", "STATIC"):
                expected[f"CMAKE_{kind}_LINKER_FLAGS"] = ""
                expected[f"CMAKE_{kind}_LINKER_FLAGS_RELEASE"] = ""
                arguments.extend(_expression(linker_reset, dict(values, kind=kind)))
            for language in ('C', 'CXX'):
                expected[f'CMAKE_{language}_COMPILER_LAUNCHER'] = ''
                arguments.append(f'-DCMAKE_{language}_COMPILER_LAUNCHER=')
            if owner == "vetron":
                arguments.append(_expression(compiler_append, dict(values, emxx=selected)))
                expected["VETRON_EMXX_EXECUTABLE"] = selected
            name = f"compile:{owner}:{family}:{int(portable)}:{int(force)}:{int(tests)}{suffix}"
            profiles[name] = _cache(arguments, expected, OWNER_DRIVER)
        for owner, profile in product(budgets, sanitizers):
            for lto in (("off", "full") if profile == "release" else ("off",)):
                values = dict(cmake="cmake", ROOT=_ROOT, directory=_ROOT / "build/static-profile",
                              args=SimpleNamespace(owner=owner, profile=profile, jobs=1),
                              lto=lto, SANITIZERS=sanitizers, toolchain_profile='pinned')
                expected = {"CXET_BUILD_OWNER": owner, "CXET_FAMILY_PROFILE": "essential",
                            "CXET_LOCAL_TESTS": "ON", "CXET_SANITIZER_PROFILE": sanitizers[profile],
                            "CXET_LTO": "ON" if lto == "full" else "OFF",
                            "CMAKE_EXE_LINKER_FLAGS": "-fuse-ld=lld -Wl,--threads=1",
                            "FETCHCONTENT_FULLY_DISCONNECTED": "ON"}
                suffix = ":full" if lto == "full" else ""
                arguments = _expression(offline, values)
                for language in ('C', 'CXX'):
                    expected[f'CMAKE_{language}_COMPILER_LAUNCHER'] = ''
                    arguments.append(f'-DCMAKE_{language}_COMPILER_LAUNCHER=')
                profiles[f"offline:{owner}:{profile}{suffix}"] = _cache(
                    arguments, expected, OFFLINE_DRIVER)
        return profiles
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors.append(f"owner profile contract: {exc}")
        return {}


def validate_root_profile_evidence_microcases(errors: list[str]) -> None:
    """Self-check EOF direction and prohibit evidence union across profiles."""
    validate_condition_policy_microcases(errors)
    validate_message_terminal_microcases(errors)
    validate_root_dialect_microcases(errors)
    # Prove that the source-root binding cannot be removed or redirected to
    # bypass the native cache compiler guard. Parse source as data only.
    try:
        driver_text = (ROOT / OWNER_DRIVER).read_text()
        function = _function(_tree(driver_text, OWNER_DRIVER), 'configure')
        _compile_extras(function)
        for mutation in ('remove', 'rebind'):
            function = _function(_tree(driver_text, OWNER_DRIVER), 'configure')
            guards = [node for node in ast.walk(function)
                      if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                      and node.func.id == 'validate_build_profile']
            if len(guards) != 1:
                raise ProfileError('native cache guard must have one source-root binding')
            bindings = [keyword for keyword in guards[0].keywords if keyword.arg == 'root']
            if len(bindings) != 1:
                raise ProfileError('native cache guard must bind root exactly once')
            if mutation == 'remove':
                guards[0].keywords.remove(bindings[0])
            else:
                bindings[0].value = ast.Name(id='build', ctx=ast.Load())
            try:
                _compile_extras(function)
            except ProfileError as exc:
                if 'configure input binding/profile guard prefix' not in str(exc):
                    errors.append('root-profile self-check cache root ' + mutation + ': wrong rejection')
            else:
                errors.append('root-profile self-check cache root ' + mutation + ': mutation accepted')
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        errors.append('root-profile self-check native cache root: ' + str(exc))
    # Deployment admission remains exact even though deployment itself is
    # outside the enumerated pinned ordinary/offline evidence universe.
    try:
        driver_text = (ROOT / OWNER_DRIVER).read_text()
        selection = ast.parse('deployment_profile is not None', mode='eval').body
        for value, expected in ((None, False), ('diagnostic', True)):
            if _expression(selection, {'deployment_profile': value}) is not expected:
                errors.append('root-profile self-check deployment None selection: wrong result')
        try:
            _expression(ast.parse('deployment_profile is not owner', mode='eval').body,
                        {'deployment_profile': None, 'owner': 'diagnostic'})
        except ProfileError:
            pass
        else:
            errors.append('root-profile self-check deployment identity: non-None comparison accepted')
        for mutation, message in (
                ('admission', 'invalid Diagnostic deployment product configuration'),
                ('family', 'Diagnostic deployment requires CXET_FAMILY_PROFILE=essential'),
                ('cache binding', None)):
            function = _function(_tree(driver_text, OWNER_DRIVER), 'configure')
            if message is not None:
                guards = [node for node in ast.walk(function) if isinstance(node, ast.If)
                          and any(isinstance(statement, ast.Raise)
                                  and isinstance(statement.exc, ast.Call)
                                  and statement.exc.args
                                  and isinstance(statement.exc.args[0], ast.Constant)
                                  and statement.exc.args[0].value == message
                                  for statement in node.body)]
                if len(guards) != 1:
                    raise ProfileError('deployment must have one ' + mutation + ' guard')
                guards[0].test = ast.Constant(value=False)
            else:
                bindings = [keyword for node in ast.walk(function)
                            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == 'validate_build_profile'
                            for keyword in node.keywords if keyword.arg is None]
                if len(bindings) != 1:
                    raise ProfileError('deployment must have one cache options binding')
                bindings[0].value = ast.Dict(keys=[], values=[])
            try:
                _compile_extras(function)
            except ProfileError as exc:
                if 'configure input binding/profile guard prefix' not in str(exc):
                    errors.append('root-profile self-check deployment ' + mutation + ': wrong rejection')
            else:
                errors.append('root-profile self-check deployment ' + mutation + ': mutation accepted')
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        errors.append('root-profile self-check deployment guards: ' + str(exc))
    all_paths = ((),)
    late_fatal = RootProfileEvidence("late-fatal", {1: all_paths}, ())
    if late_fatal.covers(1):
        errors.append(
            "root-profile self-check late fatal: pre-fatal command covered "
            "an empty successful-EOF universe")

    split = RootDialectEvidence(frozenset({1, 2}), {
        "left": RootProfileEvidence("left", {1: all_paths}, all_paths),
        "right": RootProfileEvidence("right", {2: all_paths}, all_paths),
    })
    if any(
            split.profile_covers_all(profile, (1, 2))
            for profile in split.profiles):
        errors.append(
            "root-profile self-check split profile: disjoint profile "
            "evidence was combined")

    a0 = ((('A', 0),),)
    a1 = ((('A', 1),),)
    partial = RootProfileEvidence(
        "partial", {1: a0}, (a0[0], a1[0]))
    if partial.covers(1):
        errors.append(
            "root-profile self-check partial path: one branch covered the "
            "whole successful-EOF universe")


def validate_required_profiles_live(
    evidence: RootDialectEvidence,
    relative: str,
    errors: list[str],
) -> None:
    for profile_name in evidence.profiles:
        profile = evidence.profiles.get(profile_name)
        if profile is None or not profile.live_eof_paths:
            errors.append(
                f"{relative}: exact {profile_name} profile has no successful "
                "root EOF path")


def require_profile_command(
    evidence: RootDialectEvidence,
    profile_name: str,
    offset: int,
    origin: str,
    description: str,
    errors: list[str],
) -> None:
    profile = evidence.profiles.get(profile_name)
    if profile is None or not profile.covers(offset):
        errors.append(
            f"{origin}: required {description} is not covered by successful "
            f"EOF paths of exact {profile_name} profile")
