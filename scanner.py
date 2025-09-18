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


@dataclass
class FunctionInfo:
    name: str
    type: str
    language: str
    file_path: str
    line_number: int
    signature: Optional[str] = None
    module_source: Optional[str] = None


@dataclass
class ScanResult:
    total_files: int
    processed_files: int
    total_functions: int
    functions_by_language: Dict[str, int]
    functions: List[FunctionInfo]
    scan_time: float
    errors: List[str]


class LanguageParser:
    def __init__(self):
        self.file_extensions = set()
        self.language_name = ""

    def can_parse(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.file_extensions

    def parse_file(self, file_path: str, content: str) -> List[FunctionInfo]:
        raise NotImplementedError


class PythonParser(LanguageParser):

    def __init__(self):
        super().__init__()
        self.file_extensions = {'.py', '.pyw'}
        self.language_name = "Python"

    def parse_file(self, file_path: str, content: str) -> List[FunctionInfo]:
        functions = []
        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    signature = f"{node.name}({', '.join(arg.arg for arg in node.args.args)})"
                    functions.append(FunctionInfo(
                        name=node.name,
                        type='defined',
                        language=self.language_name,
                        file_path=file_path,
                        line_number=node.lineno,
                        signature=signature
                    ))

                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        functions.append(FunctionInfo(
                            name=alias.name,
                            type='imported',
                            language=self.language_name,
                            file_path=file_path,
                            line_number=node.lineno,
                            module_source=alias.name
                        ))

                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        functions.append(FunctionInfo(
                            name=alias.name,
                            type='imported',
                            language=self.language_name,
                            file_path=file_path,
                            line_number=node.lineno,
                            module_source=f"{module}.{alias.name}" if module else alias.name
                        ))

                elif isinstance(node, ast.AsyncFunctionDef):
                    signature = f"async {node.name}({', '.join(arg.arg for arg in node.args.args)})"
                    functions.append(FunctionInfo(
                        name=node.name,
                        type='defined',
                        language=self.language_name,
                        file_path=file_path,
                        line_number=node.lineno,
                        signature=signature
                    ))

        except SyntaxError:
            pass
        except Exception:
            pass

        return functions


class JavaScriptParser(LanguageParser):

    def __init__(self):
        super().__init__()
        self.file_extensions = {'.js', '.jsx', '.ts', '.tsx', '.mjs'}
        self.language_name = "JavaScript/TypeScript"

    def parse_file(self, file_path: str, content: str) -> List[FunctionInfo]:
        functions = []
        lines = content.split('\n')

        patterns = [
            r'^\s*function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(',
            r'^\s*(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*function\s*\(',
            r'^\s*(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*\([^)]*\)\s*=>\s*[{]',
            r'^\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:\s*function\s*\(',
            r'^\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^)]*\)\s*{',
            r'^\s*async\s+function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(',
        ]

        import_patterns = [
            r'import\s*{\s*([^}]+)\s*}\s*from\s*[\'"]([^\'"]+)[\'"]',
            r'import\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s+from\s*[\'"]([^\'"]+)[\'"]',
            r'(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    functions.append(FunctionInfo(
                        name=match.group(1),
                        type='defined',
                        language=self.language_name,
                        file_path=file_path,
                        line_number=line_num,
                        signature=line.strip()
                    ))

            for pattern in import_patterns:
                match = re.search(pattern, line)
                if match:
                    if '{' in pattern:
                        imports = [name.strip() for name in match.group(1).split(',')]
                        for imp in imports:
                            functions.append(FunctionInfo(
                                name=imp,
                                type='imported',
                                language=self.language_name,
                                file_path=file_path,
                                line_number=line_num,
                                module_source=match.group(2)
                            ))
                    else:
                        functions.append(FunctionInfo(
                            name=match.group(1),
                            type='imported',
                            language=self.language_name,
                            file_path=file_path,
                            line_number=line_num,
                            module_source=match.group(2)
                        ))

        return functions


class JavaParser(LanguageParser):

    def __init__(self):
        super().__init__()
        self.file_extensions = {'.java'}
        self.language_name = "Java"

    def parse_file(self, file_path: str, content: str) -> List[FunctionInfo]:
        functions = []
        lines = content.split('\n')

        method_pattern = r'^\s*(?:public|private|protected|static|\s)*\s*[\w<>,\s]+\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\('
        import_pattern = r'import\s+((?:[a-zA-Z_$][a-zA-Z0-9_$]*\.)*[a-zA-Z_$][a-zA-Z0-9_$]*)'

        for line_num, line in enumerate(lines, 1):
            if 'class ' not in line and '{' in line:
                match = re.search(method_pattern, line)
                if match and not line.strip().startswith('//'):
                    functions.append(FunctionInfo(
                        name=match.group(1),
                        type='defined',
                        language=self.language_name,
                        file_path=file_path,
                        line_number=line_num,
                        signature=line.strip()
                    ))

            match = re.search(import_pattern, line)
            if match and line.strip().startswith('import'):
                full_import = match.group(1)
                class_name = full_import.split('.')[-1]
                functions.append(FunctionInfo(
                    name=class_name,
                    type='imported',
                    language=self.language_name,
                    file_path=file_path,
                    line_number=line_num,
                    module_source=full_import
                ))

        return functions


class CppParser(LanguageParser):

    def __init__(self):
        super().__init__()
        self.file_extensions = {'.cpp', '.cc', '.cxx', '.c', '.h', '.hpp'}
        self.language_name = "C/C++"

    def parse_file(self, file_path: str, content: str) -> List[FunctionInfo]:
        functions = []
        lines = content.split('\n')

        function_pattern = r'^\s*(?:\w+\s+)*([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*[{;]'
        include_pattern = r'#include\s*[<"]([^>"]+)[>"]'

        for line_num, line in enumerate(lines, 1):
            if line.strip().startswith('//') or (line.strip().startswith('#') and 'include' not in line):
                continue
            match = re.search(function_pattern, line)
            if match and not any(keyword in line for keyword in ['if', 'for', 'while', 'switch']):
                functions.append(FunctionInfo(
                    name=match.group(1),
                    type='defined',
                    language=self.language_name,
                    file_path=file_path,
                    line_number=line_num,
                    signature=line.strip()
                ))

            match = re.search(include_pattern, line)
            if match:
                header = match.group(1)
                functions.append(FunctionInfo(
                    name=header,
                    type='imported',
                    language=self.language_name,
                    file_path=file_path,
                    line_number=line_num,
                    module_source=header
                ))

        return functions


class GoParser(LanguageParser):

    def __init__(self):
        super().__init__()
        self.file_extensions = {'.go'}
        self.language_name = "Go"

    def parse_file(self, file_path: str, content: str) -> List[FunctionInfo]:
        functions = []
        lines = content.split('\n')

        func_pattern = r'func\s+(?:\([^)]*\)\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        import_pattern = r'import\s+["\']([^"\']+)["\']'
        grouped_import_pattern = r'^\s*["\']([^"\']+)["\']'

        in_import_block = False

        for line_num, line in enumerate(lines, 1):
            match = re.search(func_pattern, line)
            if match:
                functions.append(FunctionInfo(
                    name=match.group(1),
                    type='defined',
                    language=self.language_name,
                    file_path=file_path,
                    line_number=line_num,
                    signature=line.strip()
                ))

            if 'import (' in line:
                in_import_block = True
                continue
            elif in_import_block and ')' in line:
                in_import_block = False
                continue
            elif in_import_block:
                match = re.search(grouped_import_pattern, line)
                if match:
                    import_path = match.group(1)
                    package_name = import_path.split('/')[-1]
                    functions.append(FunctionInfo(
                        name=package_name,
                        type='imported',
                        language=self.language_name,
                        file_path=file_path,
                        line_number=line_num,
                        module_source=import_path
                    ))

            match = re.search(import_pattern, line)
            if match and not in_import_block:
                import_path = match.group(1)
                package_name = import_path.split('/')[-1]
                functions.append(FunctionInfo(
                    name=package_name,
                    type='imported',
                    language=self.language_name,
                    file_path=file_path,
                    line_number=line_num,
                    module_source=import_path
                ))

        return functions


def _process_file_worker(file_path: str) -> Tuple[List[FunctionInfo], Optional[str]]:
    parsers = [
        PythonParser(),
        JavaScriptParser(),
        JavaParser(),
        CppParser(),
        GoParser()
    ]
    supported_extensions = set()
    for parser in parsers:
        supported_extensions.update(parser.file_extensions)

    def _is_text_file(file_path: str) -> bool:
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type.startswith('text'):
                return True
            ext = Path(file_path).suffix.lower()
            return ext in supported_extensions
        except Exception:
            return False

    def _get_parser(file_path: str) -> Optional[LanguageParser]:
        for parser in parsers:
            if parser.can_parse(file_path):
                return parser
        return None

    def _read_file_safely(file_path: str) -> Optional[str]:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception:
                return None

    if not _is_text_file(file_path):
        return [], None

    parser = _get_parser(file_path)
    if not parser:
        return [], None

    content = _read_file_safely(file_path)
    if content is None:
        return [], f"Could not read file: {file_path}"

    try:
        return parser.parse_file(file_path, content), None
    except Exception as e:
        return [], f"Error parsing {file_path}: {str(e)}"


class FunctionScanner:

    def __init__(self, max_workers: int = 4):
        self.parsers = [
            PythonParser(),
            JavaScriptParser(),
            JavaParser(),
            CppParser(),
            GoParser()
        ]
        self.max_workers = max_workers
        self.supported_extensions = set()
        for parser in self.parsers:
            self.supported_extensions.update(parser.file_extensions)

    def _get_parser(self, file_path: str) -> Optional[LanguageParser]:
        for parser in self.parsers:
            if parser.can_parse(file_path):
                return parser
        return None

    def _is_text_file(self, file_path: str) -> bool:
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type.startswith('text'):
                return True

            ext = Path(file_path).suffix.lower()
            return ext in self.supported_extensions
        except Exception:
            return False

    def _read_file_safely(self, file_path: str) -> Optional[str]:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception:
                return None

    def _scan_file(self, file_path: str) -> Tuple[List[FunctionInfo], Optional[str]]:
        if not self._is_text_file(file_path):
            return [], None

        parser = self._get_parser(file_path)
        if not parser:
            return [], None

        content = self._read_file_safely(file_path)
        if content is None:
            return [], f"Could not read file: {file_path}"

        try:
            return parser.parse_file(file_path, content), None
        except Exception as e:
            return [], f"Error parsing {file_path}: {str(e)}"

    def scan_directory(self, directory: str, exclude_dirs: Set[str] = None) -> ScanResult:
        if exclude_dirs is None:
            exclude_dirs = {'.git', '__pycache__', 'node_modules', '.vscode', '.idea', 'build', 'dist'}

        start_time = time.time()
        all_functions = []
        errors = []
        total_files = 0
        processed_files = 0

        files_to_process = []
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                file_path = os.path.join(root, file)
                if self._is_text_file(file_path):
                    files_to_process.append(file_path)
            total_files += len(files)

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(_process_file_worker, file_path): file_path
                            for file_path in files_to_process}

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    functions, error = future.result()
                    if functions:
                        all_functions.extend(functions)
                        processed_files += 1
                    if error:
                        errors.append(error)
                except Exception as e:
                    errors.append(f"Error processing {file_path}: {str(e)}")

        scan_time = time.time() - start_time
        functions_by_language = {}
        for func in all_functions:
            lang = func.language
            functions_by_language[lang] = functions_by_language.get(lang, 0) + 1

        return ScanResult(
            total_files=total_files,
            processed_files=processed_files,
            total_functions=len(all_functions),
            functions_by_language=functions_by_language,
            functions=all_functions,
            scan_time=scan_time,
            errors=errors
        )

    def scan_file(self, file_path: str) -> ScanResult:
        start_time = time.time()
        functions, error = _process_file_worker(file_path)
        scan_time = time.time() - start_time

        errors = [error] if error else []
        functions_by_language = {}
        for func in functions:
            lang = func.language
            functions_by_language[lang] = functions_by_language.get(lang, 0) + 1

        return ScanResult(
            total_files=1,
            processed_files=1 if functions else 0,
            total_functions=len(functions),
            functions_by_language=functions_by_language,
            functions=functions,
            scan_time=scan_time,
            errors=errors
        )


def format_output(result: ScanResult, output_format: str = 'text') -> str:
    if output_format == 'json':
        return json.dumps(asdict(result), indent=2, default=str)

    output = []
    output.append("Function Scanner Results")
    output.append("=" * 50)
    output.append(f"Total files: {result.total_files}")
    output.append(f"Processed files: {result.processed_files}")
    output.append(f"Total functions found: {result.total_functions}")
    output.append(f"Scan time: {result.scan_time:.2f} seconds")
    output.append("")

    if result.functions_by_language:
        output.append("Functions by language:")
        for lang, count in sorted(result.functions_by_language.items()):
            output.append(f"  {lang}: {count}")
        output.append("")

    if result.errors:
        output.append(f"Errors ({len(result.errors)}):")
        for error in result.errors[:10]:
            output.append(f"  {error}")
        if len(result.errors) > 10:
            output.append(f"  ... and {len(result.errors) - 10} more errors")
        output.append("")

    output.append("Functions:")
    output.append("-" * 30)

    functions_by_file = {}
    for func in result.functions:
        if func.file_path not in functions_by_file:
            functions_by_file[func.file_path] = []
        functions_by_file[func.file_path].append(func)

    for file_path, functions in sorted(functions_by_file.items()):
        output.append(f"\n{file_path}:")
        defined_funcs = [f for f in functions if f.type == 'defined']
        imported_funcs = [f for f in functions if f.type == 'imported']

        if defined_funcs:
            output.append("  Defined functions:")
            for func in sorted(defined_funcs, key=lambda x: x.line_number):
                output.append(f"    {func.name} (line {func.line_number})")

        if imported_funcs:
            output.append("  Imported functions/modules:")
            for func in sorted(imported_funcs, key=lambda x: x.line_number):
                source = f" from {func.module_source}" if func.module_source else ""
                output.append(f"    {func.name}{source} (line {func.line_number})")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description='Language-agnostic function scanner')
    parser.add_argument('target', help='File or directory to scan')
    parser.add_argument('--format', choices=['text', 'json'], default='text',
                       help='Output format (default: text)')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--workers', '-w', type=int, default=4,
                       help='Number of worker threads (default: 4)')
    parser.add_argument('--exclude', nargs='*', default=[],
                       help='Additional directories to exclude')

    args = parser.parse_args()

    scanner = FunctionScanner(max_workers=args.workers)

    if os.path.isfile(args.target):
        result = scanner.scan_file(args.target)
    elif os.path.isdir(args.target):
        exclude_dirs = {'.git', '__pycache__', 'node_modules', '.vscode', '.idea', 'build', 'dist'}
        exclude_dirs.update(args.exclude)
        result = scanner.scan_directory(args.target, exclude_dirs)
    else:
        print(f"Error: {args.target} is not a valid file or directory")
        return 1

    output = format_output(result, args.format)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Results written to {args.output}")
    else:
        print(output)

    return 0


if __name__ == '__main__':
    exit(main())