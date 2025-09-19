#!/usr/bin/env python3

import os
import re
import json
import ast
import argparse
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import mimetypes
from collections import defaultdict


@dataclass
class FunctionInfo:
    name: str
    type: str
    language: str
    file_path: str
    line_number: int
    signature: Optional[str] = None
    module_source: Optional[str] = None
    original_name: Optional[str] = None
    import_alias: Optional[str] = None


@dataclass
class ImportInfo:
    imported_name: str
    source_module: str
    file_path: str
    line_number: int
    is_from_import: bool = False
    alias: Optional[str] = None


@dataclass
class DefinitionInfo:
    name: str
    file_path: str
    line_number: int
    language: str
    signature: Optional[str] = None


@dataclass
class Issue:
    type: str
    severity: str
    description: str
    file_path: str
    line_number: Optional[int] = None
    details: Optional[Dict] = None


@dataclass
class CircularDependency:
    cycle: List[str]
    description: str


@dataclass
class ScanResult:
    total_files: int
    processed_files: int
    total_functions: int
    total_imports: int
    total_definitions: int
    functions_by_language: Dict[str, int]
    functions: List[FunctionInfo]
    imports: List[ImportInfo]
    definitions: List[DefinitionInfo]
    issues: List[Issue]
    circular_dependencies: List[CircularDependency]
    scan_time: float
    errors: List[str]
    statistics: Dict[str, int]


class LanguageParser:
    def __init__(self):
        self.file_extensions = set()
        self.language_name = ""

    def can_parse(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.file_extensions

    def parse_file(
        self, file_path: str, content: str
    ) -> Tuple[List[FunctionInfo], List[ImportInfo], List[DefinitionInfo]]:
        raise NotImplementedError


class PythonParser(LanguageParser):
    def __init__(self):
        super().__init__()
        self.file_extensions = {".py", ".pyw"}
        self.language_name = "Python"

    def parse_file(
        self, file_path: str, content: str
    ) -> Tuple[List[FunctionInfo], List[ImportInfo], List[DefinitionInfo]]:
        functions = []
        imports = []
        definitions = []

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    signature = f"{'async ' if isinstance(node, ast.AsyncFunctionDef) else ''}{node.name}({', '.join(arg.arg for arg in node.args.args)})"

                    func_info = FunctionInfo(
                        name=node.name,
                        type="defined",
                        language=self.language_name,
                        file_path=file_path,
                        line_number=node.lineno,
                        signature=signature,
                    )
                    functions.append(func_info)

                    def_info = DefinitionInfo(
                        name=node.name,
                        file_path=file_path,
                        line_number=node.lineno,
                        signature=signature,
                        language=self.language_name,
                    )
                    definitions.append(def_info)

                elif isinstance(node, ast.ClassDef):
                    def_info = DefinitionInfo(
                        name=node.name,
                        file_path=file_path,
                        line_number=node.lineno,
                        signature=f"class {node.name}",
                        language=self.language_name,
                    )
                    definitions.append(def_info)

                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        import_name = alias.asname if alias.asname else alias.name
                        import_info = ImportInfo(
                            imported_name=import_name,
                            source_module=alias.name,
                            file_path=file_path,
                            line_number=node.lineno,
                            is_from_import=False,
                            alias=alias.asname,
                        )
                        imports.append(import_info)

                        func_info = FunctionInfo(
                            name=import_name,
                            type="imported",
                            language=self.language_name,
                            file_path=file_path,
                            line_number=node.lineno,
                            module_source=alias.name,
                            original_name=alias.name,
                            import_alias=alias.asname,
                        )
                        functions.append(func_info)

                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        if alias.name == "*":
                            import_info = ImportInfo(
                                imported_name="*",
                                source_module=module,
                                file_path=file_path,
                                line_number=node.lineno,
                                is_from_import=True,
                            )
                            imports.append(import_info)
                            continue

                        import_name = alias.asname if alias.asname else alias.name
                        full_source = f"{module}.{alias.name}" if module else alias.name

                        import_info = ImportInfo(
                            imported_name=import_name,
                            source_module=full_source,
                            file_path=file_path,
                            line_number=node.lineno,
                            is_from_import=True,
                            alias=alias.asname,
                        )
                        imports.append(import_info)

                        func_info = FunctionInfo(
                            name=import_name,
                            type="imported",
                            language=self.language_name,
                            file_path=file_path,
                            line_number=node.lineno,
                            module_source=full_source,
                            original_name=alias.name,
                            import_alias=alias.asname,
                        )
                        functions.append(func_info)

        except SyntaxError:
            pass
        except Exception:
            pass

        return functions, imports, definitions


class JavaScriptParser(LanguageParser):
    def __init__(self):
        super().__init__()
        self.file_extensions = {".js", ".jsx", ".ts", ".tsx", ".mjs"}
        self.language_name = "JavaScript/TypeScript"

    def parse_file(
        self, file_path: str, content: str
    ) -> Tuple[List[FunctionInfo], List[ImportInfo], List[DefinitionInfo]]:
        functions = []
        imports = []
        definitions = []
        lines = content.split("\n")

        function_patterns = [
            r"^\s*function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(",
            r"^\s*(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*function\s*\(",
            r"^\s*(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*\([^)]*\)\s*=>\s*[{]",
            r"^\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:\s*function\s*\(",
            r"^\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^)]*\)\s*{",
            r"^\s*async\s+function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(",
            r"^\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:\s*\([^)]*\)\s*=>\s*[{]",
            r"^\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*async\s*\([^)]*\)\s*=>\s*[{]",
        ]

        import_patterns = [
            (r'import\s*{\s*([^}]+)\s*}\s*from\s*[\'"]([^\'"]+)[\'"]', "named"),
            (
                r'import\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s+from\s*[\'"]([^\'"]+)[\'"]',
                "default",
            ),
            (
                r'import\s*\*\s*as\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s+from\s*[\'"]([^\'"]+)[\'"]',
                "namespace",
            ),
            (
                r'(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                "require",
            ),
            (
                r'(?:const|let|var)\s*{\s*([^}]+)\s*}\s*=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                "require_destructure",
            ),
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in function_patterns:
                match = re.search(pattern, line)
                if match and not line.strip().startswith("//"):
                    func_name = match.group(1)

                    func_info = FunctionInfo(
                        name=func_name,
                        type="defined",
                        language=self.language_name,
                        file_path=file_path,
                        line_number=line_num,
                        signature=line.strip(),
                    )
                    functions.append(func_info)

                    def_info = DefinitionInfo(
                        name=func_name,
                        file_path=file_path,
                        line_number=line_num,
                        signature=line.strip(),
                        language=self.language_name,
                    )
                    definitions.append(def_info)

            for pattern, import_type in import_patterns:
                match = re.search(pattern, line)
                if match and not line.strip().startswith("//"):
                    if import_type == "named" or import_type == "require_destructure":
                        imports_str = match.group(1)
                        module_name = match.group(2)
                        import_names = [name.strip() for name in imports_str.split(",")]

                        for import_name in import_names:
                            if " as " in import_name:
                                original, alias = import_name.split(" as ")
                                original = original.strip()
                                alias = alias.strip()
                            else:
                                original = import_name.strip()
                                alias = None

                            import_info = ImportInfo(
                                imported_name=alias if alias else original,
                                source_module=f"{module_name}.{original}",
                                file_path=file_path,
                                line_number=line_num,
                                is_from_import=True,
                                alias=alias,
                            )
                            imports.append(import_info)

                            func_info = FunctionInfo(
                                name=alias if alias else original,
                                type="imported",
                                language=self.language_name,
                                file_path=file_path,
                                line_number=line_num,
                                module_source=f"{module_name}.{original}",
                                original_name=original,
                                import_alias=alias,
                            )
                            functions.append(func_info)
                    else:
                        import_name = match.group(1)
                        module_name = match.group(2)

                        import_info = ImportInfo(
                            imported_name=import_name,
                            source_module=module_name,
                            file_path=file_path,
                            line_number=line_num,
                            is_from_import=(import_type != "require"),
                        )
                        imports.append(import_info)

                        func_info = FunctionInfo(
                            name=import_name,
                            type="imported",
                            language=self.language_name,
                            file_path=file_path,
                            line_number=line_num,
                            module_source=module_name,
                        )
                        functions.append(func_info)

        return functions, imports, definitions


class JavaParser(LanguageParser):
    def __init__(self):
        super().__init__()
        self.file_extensions = {".java"}
        self.language_name = "Java"

    def parse_file(
        self, file_path: str, content: str
    ) -> Tuple[List[FunctionInfo], List[ImportInfo], List[DefinitionInfo]]:
        functions = []
        imports = []
        definitions = []
        lines = content.split("\n")

        method_pattern = r"^\s*(?:public|private|protected|static|\s)*\s*[\w<>,\s]+\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\("
        class_pattern = (
            r"^\s*(?:public|private|protected|\s)*\s*class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)"
        )
        import_pattern = (
            r"import\s+((?:[a-zA-Z_$][a-zA-Z0-9_$]*\.)*[a-zA-Z_$][a-zA-Z0-9_$]*)"
        )

        for line_num, line in enumerate(lines, 1):
            if line.strip().startswith("//") or line.strip().startswith("/*"):
                continue
            if "class " not in line and "{" in line:
                match = re.search(method_pattern, line)
                if match:
                    method_name = match.group(1)

                    func_info = FunctionInfo(
                        name=method_name,
                        type="defined",
                        language=self.language_name,
                        file_path=file_path,
                        line_number=line_num,
                        signature=line.strip(),
                    )
                    functions.append(func_info)

                    def_info = DefinitionInfo(
                        name=method_name,
                        file_path=file_path,
                        line_number=line_num,
                        signature=line.strip(),
                        language=self.language_name,
                    )
                    definitions.append(def_info)
            match = re.search(class_pattern, line)
            if match:
                class_name = match.group(1)
                def_info = DefinitionInfo(
                    name=class_name,
                    file_path=file_path,
                    line_number=line_num,
                    signature=line.strip(),
                    language=self.language_name,
                )
                definitions.append(def_info)
            match = re.search(import_pattern, line)
            if match and line.strip().startswith("import"):
                full_import = match.group(1)
                class_name = full_import.split(".")[-1]

                import_info = ImportInfo(
                    imported_name=class_name,
                    source_module=full_import,
                    file_path=file_path,
                    line_number=line_num,
                    is_from_import=True,
                )
                imports.append(import_info)

                func_info = FunctionInfo(
                    name=class_name,
                    type="imported",
                    language=self.language_name,
                    file_path=file_path,
                    line_number=line_num,
                    module_source=full_import,
                )
                functions.append(func_info)

        return functions, imports, definitions


class GoParser(LanguageParser):
    def __init__(self):
        super().__init__()
        self.file_extensions = {".go"}
        self.language_name = "Go"

    def parse_file(
        self, file_path: str, content: str
    ) -> Tuple[List[FunctionInfo], List[ImportInfo], List[DefinitionInfo]]:
        functions = []
        imports = []
        definitions = []
        lines = content.split("\n")

        func_pattern = r"func\s+(?:\([^)]*\)\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
        import_pattern = r'import\s+["\']([^"\']+)["\']'
        grouped_import_pattern = r'^\s*["\']([^"\']+)["\']'

        in_import_block = False

        for line_num, line in enumerate(lines, 1):
            match = re.search(func_pattern, line)
            if match:
                func_name = match.group(1)

                func_info = FunctionInfo(
                    name=func_name,
                    type="defined",
                    language=self.language_name,
                    file_path=file_path,
                    line_number=line_num,
                    signature=line.strip(),
                )
                functions.append(func_info)

                def_info = DefinitionInfo(
                    name=func_name,
                    file_path=file_path,
                    line_number=line_num,
                    signature=line.strip(),
                    language=self.language_name,
                )
                definitions.append(def_info)
            if "import (" in line:
                in_import_block = True
                continue
            elif in_import_block and ")" in line:
                in_import_block = False
                continue
            elif in_import_block:
                match = re.search(grouped_import_pattern, line)
                if match:
                    import_path = match.group(1)
                    package_name = import_path.split("/")[-1]

                    import_info = ImportInfo(
                        imported_name=package_name,
                        source_module=import_path,
                        file_path=file_path,
                        line_number=line_num,
                        is_from_import=True,
                    )
                    imports.append(import_info)

                    func_info = FunctionInfo(
                        name=package_name,
                        type="imported",
                        language=self.language_name,
                        file_path=file_path,
                        line_number=line_num,
                        module_source=import_path,
                    )
                    functions.append(func_info)
            match = re.search(import_pattern, line)
            if match and not in_import_block:
                import_path = match.group(1)
                package_name = import_path.split("/")[-1]

                import_info = ImportInfo(
                    imported_name=package_name,
                    source_module=import_path,
                    file_path=file_path,
                    line_number=line_num,
                    is_from_import=True,
                )
                imports.append(import_info)

                func_info = FunctionInfo(
                    name=package_name,
                    type="imported",
                    language=self.language_name,
                    file_path=file_path,
                    line_number=line_num,
                    module_source=import_path,
                )
                functions.append(func_info)

        return functions, imports, definitions


class CrossReferenceAnalyzer:
    def __init__(self):
        self.definitions_by_name = defaultdict(list)
        self.imports_by_file = defaultdict(list)
        self.file_dependencies = defaultdict(set)
        self.module_to_file_map = {}

    def build_cross_reference_maps(
        self,
        all_definitions: List[DefinitionInfo],
        all_imports: List[ImportInfo],
        all_files: List[str],
    ):
        for definition in all_definitions:
            self.definitions_by_name[definition.name].append(definition)
        for import_info in all_imports:
            self.imports_by_file[import_info.file_path].append(import_info)
        for file_path in all_files:
            module_name = self._get_module_name_from_file(file_path)
            if module_name:
                self.module_to_file_map[module_name] = file_path

    def _get_module_name_from_file(self, file_path: str) -> str:
        path = Path(file_path)
        if path.suffix == ".py":
            parts = path.with_suffix("").parts
            filtered_parts = []
            for part in parts:
                if part not in {".", "..", "src", "lib", "app"}:
                    filtered_parts.append(part)
            return ".".join(filtered_parts)
        elif path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
            return str(path.with_suffix(""))
        elif path.suffix == ".java":
            return path.stem
        elif path.suffix == ".go":
            return path.parent.name
        return ""

    def find_missing_definitions(self, all_imports: List[ImportInfo]) -> List[Issue]:
        issues = []

        for import_info in all_imports:
            if self._is_standard_library_import(import_info.source_module):
                continue

            imported_name = import_info.imported_name
            source_module = import_info.source_module

            if imported_name not in self.definitions_by_name:
                module_parts = source_module.split(".")
                found_in_module = False

                for module_variant in self._get_module_variants(source_module):
                    if module_variant in self.module_to_file_map:
                        target_file = self.module_to_file_map[module_variant]
                        definitions_in_file = [
                            d
                            for d in self.definitions_by_name.get(imported_name, [])
                            if d.file_path == target_file
                        ]
                        if definitions_in_file:
                            found_in_module = True
                            break

                if not found_in_module:
                    issues.append(
                        Issue(
                            type="missing_definition",
                            severity="critical",
                            description=f"Function/class '{imported_name}' imported from '{source_module}' but definition not found",
                            file_path=import_info.file_path,
                            line_number=import_info.line_number,
                            details={
                                "imported_name": imported_name,
                                "source_module": source_module,
                                "import_type": "from_import"
                                if import_info.is_from_import
                                else "direct_import",
                            },
                        )
                    )

        return issues

    def find_orphaned_functions(
        self, all_definitions: List[DefinitionInfo], all_imports: List[ImportInfo]
    ) -> List[Issue]:
        issues = []
        imported_names = {imp.imported_name for imp in all_imports}

        for imp in all_imports:
            if hasattr(imp, "alias") and imp.alias:
                imported_names.add(imp.alias)

        for name, definitions in self.definitions_by_name.items():
            for definition in definitions:
                if self._is_special_function(name, definition.language):
                    continue

                if name not in imported_names:
                    issues.append(
                        Issue(
                            type="orphaned_function",
                            severity="warning",
                            description=f"Function/class '{name}' is defined but never imported or used",
                            file_path=definition.file_path,
                            line_number=definition.line_number,
                            details={
                                "function_name": name,
                                "language": definition.language,
                                "signature": definition.signature,
                            },
                        )
                    )

        return issues

    def find_circular_dependencies(
        self, all_imports: List[ImportInfo]
    ) -> List[CircularDependency]:
        dependencies = defaultdict(set)

        for import_info in all_imports:
            source_file = import_info.file_path
            target_module = import_info.source_module

            for module_variant in self._get_module_variants(target_module):
                if module_variant in self.module_to_file_map:
                    target_file = self.module_to_file_map[module_variant]
                    if target_file != source_file:
                        dependencies[source_file].add(target_file)
                    break
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node, path):
            if node in rec_stack:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in dependencies.get(node, []):
                dfs(neighbor, path.copy())

            rec_stack.remove(node)

        for file_path in dependencies:
            if file_path not in visited:
                dfs(file_path, [])
        circular_deps = []
        for cycle in cycles:
            circular_deps.append(
                CircularDependency(
                    cycle=cycle,
                    description=f"Circular dependency detected: {' → '.join(cycle)}",
                )
            )

        return circular_deps

    def _get_module_variants(self, module_path: str) -> List[str]:
        variants = [module_path]

        if "." in module_path and not module_path.endswith(".py"):
            variants.append(module_path.rsplit(".", 1)[0])

        variants.append(module_path.replace(".", "/"))
        variants.append(module_path.replace("/", "."))

        if "/" in module_path:
            parts = module_path.split("/")
            for i in range(len(parts)):
                variants.append("/".join(parts[i:]))

        return list(set(variants))

    def _is_standard_library_import(self, module_name: str) -> bool:
        python_stdlib = {
            "os",
            "sys",
            "json",
            "time",
            "datetime",
            "collections",
            "itertools",
            "functools",
            "operator",
            "re",
            "math",
            "random",
            "urllib",
            "http",
            "asyncio",
            "threading",
            "multiprocessing",
            "pathlib",
            "typing",
            "dataclasses",
            "abc",
            "contextlib",
            "concurrent",
            "concurrent.futures",
        }

        js_builtins = {
            "fs",
            "path",
            "util",
            "events",
            "stream",
            "crypto",
            "os",
            "url",
            "querystring",
            "buffer",
            "child_process",
            "cluster",
            "http",
            "https",
        }

        popular_libs = {
            "react",
            "lodash",
            "moment",
            "axios",
            "express",
            "jquery",
            "numpy",
            "pandas",
            "requests",
            "flask",
            "django",
            "sklearn",
        }

        module_root = module_name.split(".")[0]
        return (
            module_root in python_stdlib
            or module_root in js_builtins
            or module_root in popular_libs
        )

    def _is_special_function(self, name: str, language: str) -> bool:
        if language == "Python":
            return (name.startswith("__") and name.endswith("__")) or name == "main"
        elif language in ["JavaScript/TypeScript"]:
            return name in {"main", "index", "default"}
        elif language == "Java":
            return name in {"main", "toString", "equals", "hashCode"}
        elif language == "Go":
            return name in {"main", "init"}
        return False


def _process_file_worker(
    file_path: str,
) -> Tuple[List[FunctionInfo], List[ImportInfo], List[DefinitionInfo], Optional[str]]:
    parsers = [PythonParser(), JavaScriptParser(), JavaParser(), GoParser()]

    def _get_parser(file_path: str) -> Optional[LanguageParser]:
        for parser in parsers:
            if parser.can_parse(file_path):
                return parser
        return None

    def _is_text_file(file_path: str) -> bool:
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type.startswith("text"):
                return True

            supported_extensions = set()
            for parser in parsers:
                supported_extensions.update(parser.file_extensions)

            ext = Path(file_path).suffix.lower()
            return ext in supported_extensions
        except Exception:
            return False

    def _read_file_safely(file_path: str) -> Optional[str]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    return f.read()
            except Exception:
                return None

    if not _is_text_file(file_path):
        return [], [], [], None

    parser = _get_parser(file_path)
    if not parser:
        return [], [], [], None

    content = _read_file_safely(file_path)
    if content is None:
        return [], [], [], f"Could not read file: {file_path}"

    try:
        functions, imports, definitions = parser.parse_file(file_path, content)
        return functions, imports, definitions, None
    except Exception as e:
        return [], [], [], f"Error parsing {file_path}: {str(e)}"


class FunctionScanner:
    def __init__(self, max_workers: int = 4):
        self.parsers = [PythonParser(), JavaScriptParser(), JavaParser(), GoParser()]
        self.max_workers = max_workers
        self.supported_extensions = set()
        for parser in self.parsers:
            self.supported_extensions.update(parser.file_extensions)

        self.cross_ref_analyzer = CrossReferenceAnalyzer()

    def _is_text_file(self, file_path: str) -> bool:
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type.startswith("text"):
                return True

            ext = Path(file_path).suffix.lower()
            return ext in self.supported_extensions
        except Exception:
            return False

    def scan_directory(
        self, directory: str, exclude_dirs: Set[str] = None
    ) -> ScanResult:
        if exclude_dirs is None:
            exclude_dirs = {
                ".git",
                "__pycache__",
                "node_modules",
                ".vscode",
                ".idea",
                "build",
                "dist",
                "target",
            }

        start_time = time.time()
        all_functions = []
        all_imports = []
        all_definitions = []
        errors = []
        total_files = 0
        processed_files = 0

        files_to_process = []
        all_files = []

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                file_path = os.path.join(root, file)
                all_files.append(file_path)
                if self._is_text_file(file_path):
                    files_to_process.append(file_path)
            total_files += len(files)

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(_process_file_worker, file_path): file_path
                for file_path in files_to_process
            }

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    functions, imports, definitions, error = future.result()
                    if functions or imports or definitions:
                        all_functions.extend(functions)
                        all_imports.extend(imports)
                        all_definitions.extend(definitions)
                        processed_files += 1
                    if error:
                        errors.append(error)
                except Exception as e:
                    errors.append(f"Error processing {file_path}: {str(e)}")

        self.cross_ref_analyzer.build_cross_reference_maps(
            all_definitions, all_imports, all_files
        )

        issues = []
        issues.extend(self.cross_ref_analyzer.find_missing_definitions(all_imports))
        issues.extend(
            self.cross_ref_analyzer.find_orphaned_functions(
                all_definitions, all_imports
            )
        )

        circular_dependencies = self.cross_ref_analyzer.find_circular_dependencies(
            all_imports
        )

        for circular_dep in circular_dependencies:
            issues.append(
                Issue(
                    type="circular_import",
                    severity="warning",
                    description=circular_dep.description,
                    file_path=circular_dep.cycle[0],
                    details={"cycle": circular_dep.cycle},
                )
            )

        scan_time = time.time() - start_time
        functions_by_language = {}
        for func in all_functions:
            lang = func.language
            functions_by_language[lang] = functions_by_language.get(lang, 0) + 1

        statistics = {
            "critical_issues": len([i for i in issues if i.severity == "critical"]),
            "warnings": len([i for i in issues if i.severity == "warning"]),
            "missing_definitions": len(
                [i for i in issues if i.type == "missing_definition"]
            ),
            "orphaned_functions": len(
                [i for i in issues if i.type == "orphaned_function"]
            ),
            "circular_imports": len([i for i in issues if i.type == "circular_import"]),
        }

        return ScanResult(
            total_files=total_files,
            processed_files=processed_files,
            total_functions=len(all_functions),
            total_imports=len(all_imports),
            total_definitions=len(all_definitions),
            functions_by_language=functions_by_language,
            functions=all_functions,
            imports=all_imports,
            definitions=all_definitions,
            issues=issues,
            circular_dependencies=circular_dependencies,
            scan_time=scan_time,
            errors=errors,
            statistics=statistics,
        )

    def scan_file(self, file_path: str) -> ScanResult:
        start_time = time.time()
        functions, imports, definitions, error = _process_file_worker(file_path)
        scan_time = time.time() - start_time

        errors = [error] if error else []
        functions_by_language = {}
        for func in functions:
            lang = func.language
            functions_by_language[lang] = functions_by_language.get(lang, 0) + 1

        statistics = {
            "critical_issues": 0,
            "warnings": 0,
            "missing_definitions": 0,
            "orphaned_functions": 0,
            "circular_imports": 0,
        }

        return ScanResult(
            total_files=1,
            processed_files=1 if (functions or imports or definitions) else 0,
            total_functions=len(functions),
            total_imports=len(imports),
            total_definitions=len(definitions),
            functions_by_language=functions_by_language,
            functions=functions,
            imports=imports,
            definitions=definitions,
            issues=[],
            circular_dependencies=[],
            scan_time=scan_time,
            errors=errors,
            statistics=statistics,
        )


def format_output(result: ScanResult, output_format: str = "text") -> str:
    if output_format == "json":
        return json.dumps(asdict(result), indent=2, default=str)

    output = []
    output.append("FUNCTION ANALYSIS REPORT")
    output.append("=" * 50)
    output.append(f"DEFINED FUNCTIONS: {result.total_definitions}")
    output.append(f"IMPORTED FUNCTIONS: {result.total_imports}")
    output.append(f"MISSING DEFINITIONS: {result.statistics['missing_definitions']}")
    output.append(f"ORPHANED FUNCTIONS: {result.statistics['orphaned_functions']}")
    output.append(f"CIRCULAR IMPORTS: {result.statistics['circular_imports']}")
    output.append(f"SCAN TIME: {result.scan_time:.2f} seconds")
    output.append("")

    critical_issues = [i for i in result.issues if i.severity == "critical"]
    if critical_issues:
        output.append("CRITICAL ISSUES:")
        output.append("-" * 20)
        for issue in critical_issues[:10]:
            output.append(f"ERROR: {issue.description}")
            output.append(f"   FILE: {issue.file_path}:{issue.line_number or 'N/A'}")
        if len(critical_issues) > 10:
            output.append(
                f"   ... and {len(critical_issues) - 10} more critical issues"
            )
        output.append("")

    warnings = [i for i in result.issues if i.severity == "warning"]
    if warnings:
        output.append("WARNINGS:")
        output.append("-" * 12)
        for issue in warnings[:10]:
            output.append(f"WARNING: {issue.description}")
            output.append(f"   FILE: {issue.file_path}:{issue.line_number or 'N/A'}")
        if len(warnings) > 10:
            output.append(f"   ... and {len(warnings) - 10} more warnings")
        output.append("")

    if result.circular_dependencies:
        output.append("CIRCULAR DEPENDENCIES:")
        output.append("-" * 25)
        for circular_dep in result.circular_dependencies:
            output.append(f"CYCLE: {circular_dep.description}")
        output.append("")

    if result.functions_by_language:
        output.append("FUNCTIONS BY LANGUAGE:")
        output.append("-" * 26)
        for lang, count in sorted(result.functions_by_language.items()):
            output.append(f"  {lang}: {count}")
        output.append("")

    output.append("DETAILED ANALYSIS:")
    output.append("-" * 21)
    output.append(
        f"Total files processed: {result.processed_files}/{result.total_files}"
    )
    output.append(f"Functions found: {result.total_functions}")
    output.append(f"Import statements: {result.total_imports}")
    output.append(f"Function definitions: {result.total_definitions}")

    if result.errors:
        output.append("")
        output.append(f"ERRORS ({len(result.errors)}):")
        for error in result.errors[:5]:
            output.append(f"  {error}")
        if len(result.errors) > 5:
            output.append(f"  ... and {len(result.errors) - 5} more errors")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Language-agnostic function scanner with cross-reference analysis"
    )
    parser.add_argument("target", help="File or directory to scan")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Number of worker threads (default: 4)",
    )
    parser.add_argument(
        "--exclude", nargs="*", default=[], help="Additional directories to exclude"
    )

    args = parser.parse_args()

    scanner = FunctionScanner(max_workers=args.workers)

    if os.path.isfile(args.target):
        result = scanner.scan_file(args.target)
    elif os.path.isdir(args.target):
        exclude_dirs = {
            ".git",
            "__pycache__",
            "node_modules",
            ".vscode",
            ".idea",
            "build",
            "dist",
            "target",
        }
        exclude_dirs.update(args.exclude)
        result = scanner.scan_directory(args.target, exclude_dirs)
    else:
        print(f"Error: {args.target} is not a valid file or directory")
        return 1

    output = format_output(result, args.format)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Results written to {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    exit(main())
