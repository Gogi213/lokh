"""Focused self-check cases for the CXET family C/C++ source lexer."""

from __future__ import annotations

from Family.Sources.CxetFamilyCppPolicy import cpp_include_syntax


def validate_cpp_syntax_microcases(errors: list[str]) -> None:
    """Pin accepted literals and fail-closed source carriers."""
    for sample in (
        b'#include <vector>\n#include "local.hpp" // comment\n',
        b'#include<vector>\n%:include"local.hpp"\n',
        b'#inc\\\nlude<vector>\n',
        b'#inc\\\nlude "local.hpp"\n',
        b'\v#\finclude\v"local.hpp"\n',
        b'/**/ #include "local.hpp"\n',
        b'/* leading\ncomment */ #include "local.hpp"\n',
        b'#/**/include "local.hpp"\n',
        b'#pragma message("include")\n#define MESSAGE "define private"\n',
        b'%:include "local.hpp"\n',
        b'const char* module_text = "import foreign.private_module;";\n',
        b'int imported = 0;\n#error import failed\n'
        b'#pragma message(import value)\n',
        b'void f(){ important(); imported_value = 0; }\n',
        b'struct Spec { std::string module; };\n'
        b'void f(){ spec.module=value; use(spec.module); spec.module.clear(); }\n',
        b'void f(){ for(const auto& module : catalog) use(module.name); }\n',
        b'void f(){ use(spec->module); use(model::module); module.inspect(); }\n',
        b'int import=0; const char* module=nullptr;\n',
        b'bool import(Lane& lane, Bytes key) noexcept { return true; }\n'
        b'void f(){ import(lane, key); }\n',
        b'void f(){ import\\\ned_value = 0; }\n',
        b"auto n=1'000; /* #include HEADER */\n",
        b"char8_t c=u8'a';\n",
        b'// R"tag(unclosed\n#include "local.hpp"\n',
        b'/* R"tag(unclosed */\n#include "local.hpp"\n',
        b'// continued comment \\\nR"tag(unclosed\n'
        b'#include "local.hpp"\n',
        b'/\\\n/ R"tag(unclosed\n#include "local.hpp"\n',
        b'// import foreign.private_module;\n',
        b'auto text = R"tag(\n#include "not-a-directive.hpp"\n)tag";\n',
        b'asm volatile("" : "+r"(value) : "r"(operation) : "memory");\n',
        b'__asm__ __volatile__("pause" ::: "memory");\n',
        b'asm("rep " "movsb" : "+D"(dst) : : "memory");\n',
        b'#define SAFE_PASTE(name) fixed_prefix_##name##_fixed_suffix\n',
        b'#define HASH_TEXT "##"\n#define MODULE_TEXT "module"\n',
        b'const char* concat_text = "__CONCAT"; // __CONCAT1\n',
    ):
        _, _, failures = cpp_include_syntax(sample)
        if failures:
            errors.append(
                "verification include self-check rejected literal baseline: " +
                "; ".join(failures))

    for label, sample in (
        ("macro", b"#include HEADER\n"),
        ("include_next", b"#include_next <header.hpp>\n"),
        ("clang import", b'#import "foreign.cpp"\n'),
        ("BOM access macro", b"\xef\xbb\xbf#define private public\n"),
        ("C++ header-unit import", b'import "foreign.hpp";\n'),
        ("C++ adjacent header-unit import", b'import"foreign.hpp";\n'),
        ("C++ adjacent angle import", b'import<foreign.hpp>;\n'),
        ("exported header-unit import", b'export import <foreign.hpp>;\n'),
        ("named module import", b'import foreign.private_module;\n'),
        ("named module declaration", b'module foreign.private_module;\n'),
        ("global module fragment", b'module;\n'),
        ("private module fragment", b'module :private;\n'),
        ("exported module declaration", b'export module foreign.private_module;\n'),
        ("module macro carrier", b'#define MODULE_KEYWORD module\n'),
        ("import macro carrier", b'#define BODY import foreign.module;\n'),
        ("module macro argument", b'IDENTITY(import) foreign.module;\n'),
        ("module declaration macro argument", b'IDENTITY(module) foreign;\n'),
        ("opaque global module prefix", b'PREFIX module;\n'),
        ("opaque partition module prefix", b'PREFIX module:private;\n'),
        ("erased builtin module prefix", b'#define int\nint module;\n'),
        ("erased auto module prefix", b'#define auto\nauto module:private;\n'),
        ("module token paste", b'#define BAD im##port\n'),
        ("pragma module import", b'#pragma clang module import ForeignPrivate\n'),
        ("pragma operator module import",
         b'_Pragma("clang module import ForeignPrivate")\n'),
        ("partition import", b'import:partition;\n'),
        ("dollar named module import", b'import $foreign;\n'),
        ("newline named module import", b'import\nforeign.module;\n'),
        ("numeric-separator module import",
         b"auto n=1'000; import foreign.module;\n"),
        ("character after keyword hides include",
         b"switch(x){case'a':\n#include HEADER\n}\n"),
        ("digit character after keyword hides include",
         b"switch(x){case'0':\n#include HEADER\n}\n"),
        ("Objective-C module import", b'@import ForeignPrivate;\n'),
        ("dollar Objective-C module import", b'@import $Foreign;\n'),
        ("newline Objective-C module import", b'@import\nForeignPrivate;\n'),
        ("trigraph-text followed by module import",
         b'const char* s="??/";\nimport foreign.module;\n'),
        ("comment trigraph followed by macro include",
         b'// ??/\n#include HEADER\n'),
        ("digraph access rewrite", b'%:define private public\n'),
        ("raw phase-two splice", b'auto s=R"tag(line\\\nline)tag";\n'),
        ("BOM raw phase-two splice",
         b'\xef\xbb\xbfR"tag(line\\\nline)tag";\n'),
        ("identifier-suffixed fake raw", (
            b'#define FOOR\nconst char* a = FOOR"(";\n'
            b'#define HEADER "foreign.hpp"\n#include HEADER\n'
            b'const char* b = ")";\n')),
        ("access rewrite", b"#define private public\n"),
        ("obscured access rewrite", b"#/**/define private public\n"),
        ("leading-comment access rewrite", b"/**/ #define private public\n"),
        ("preprocessor embed", b'#embed "foreign.bin"\n'),
        ("digraph embed", b'%:embed "foreign.bin"\n'),
        ("phase-spliced embed", b'#em\\\nbed "foreign.bin"\n'),
        ("quoted file probe", b'#if __has_include("foreign.hpp")\n#endif\n'),
        ("angle file probe", b'#if __has_include(<foreign.hpp>)\n#endif\n'),
        ("next file probe", b'#if __has_include_next(<foreign.hpp>)\n#endif\n'),
        ("embed file probe", b'#if __has_embed("foreign.bin")\n#endif\n'),
        ("spliced file probe",
         b'#if __has_in\\\nclude("foreign.hpp")\n#endif\n'),
        ("lone-CR include", b'int x;\r#include "foreign.hpp"\r'),
        ("lone-CR access macro", b'int x;\r#define private public\r'),
        ("lone-CR embed", b'int x;\r#embed "foreign.bin"\r'),
        ("NUL-obscured include", b'#\0include "foreign.hpp"\n'),
        ("NUL-obscured access macro", b'#\0define private public\n'),
        ("NUL-obscured embed", b'#\0embed "foreign.bin"\n'),
        ("trigraph include", b'??=include "foreign.hpp"\n'),
        ("trigraph access macro", b'??=define private public\n'),
        ("trigraph embed", b'??=embed "foreign.bin"\n'),
        ("inline asm include", b'asm(".include \\"foreign.s\\"");\n'),
        ("inline asm incbin", b'__asm__(".incbin data.bin");\n'),
        ("adjacent inline asm include", b'asm(".in" "clude x");\n'),
        ("raw inline asm template", b'asm(R"(.include x)");\n'),
        ("escaped inline asm template", b'asm("\\x2einclude x");\n'),
        ("macro inline asm template", b'asm(ASM_PAYLOAD);\n'),
        ("preprocessor asm carrier", b'#define ASM_KEYWORD asm\n'),
        ("phase-spliced asm keyword", b'a\\\nsm(".include x");\n'),
        ("generic asm token paste", b'#define CAT(a, b) a##b\n'),
        ("fixed asm token paste", b'#define BAD __as##m__\n'),
        ("digraph asm token paste", b'#define CAT(a, b) a %:%: b\n'),
        ("runner friend token paste",
         b'#define MAKE(x) StrategyRunnerRuntimeFamilyVerification##x\n'),
        ("trader friend token paste",
         b'#define MAKE(x) StrategyInstanceFamilyVerification##x\n'),
        ("retired friend macro token paste",
         b'#define MAKE(x) CXET_FAMILY_DIFFERENTIAL_##x\n'),
        ("file probe token paste", b'#define MAKE(x) __has_##x\n'),
        ("external concat invocation", b'__CONCAT(as, m)("pause");\n'),
        ("external concat1 invocation", b'__CONCAT1(as, m)("pause");\n'),
        ("external concat alias", b'#define CAT __CONCAT\n'),
        ("external concat manufacture", b'#define MAKE __CON##CAT\n'),
    ):
        _, _, failures = cpp_include_syntax(sample)
        if not failures:
            errors.append(
                f"verification include self-check accepted {label} include")
