# Function Scanner

Language-agnostic tool for discovering functions in repositories. Supports Python, JavaScript/TypeScript, Java, Go with multiprocessing for performance.

## Features

### Function Analysis

- **Missing Function Detection** - Identifies functions imported but not defined (prevents runtime errors)
- **Orphaned Function Detection** - Finds functions defined but never used (dead code detection)
- **Circular Dependency Detection** - Identifies problematic import cycles

### Performance

- **Parallel Processing** - Multi-core utilization with configurable worker threads
- **Memory Efficient** - Optimized for large repositories
- **Smart Filtering** -  excludes build directories and non-code files
- **Large Scale** - Handles many files efficiently

### Multi-Language Support

- **4 Programming Languages** - Python, JavaScript/TypeScript, Java, Go
- **Language-Specific Parsing** - AST-based for Python, optimized regex for others
- **Import Detection** - Supports all major import syntaxes (import, require, use, include)
- **Unified Reporting** - Single analysis across all languages

### Reporting

- **Text Format** - Human-readable with issue categorization
- **JSON Format** - Machine-readable for CI/CD integration
- **Issue Severity** - Critical issues (runtime errors) vs warnings (code quality)
- **Performance Metrics** - Scan time, file counts, language breakdown

### Production Ready

- **Zero Dependencies** - Pure Python standard library
- **CI/CD Integration** - JSON output perfect for automation
- **Error Handling** - failure recovery and detailed error reporting

## Supported Languages

| Language              | Extensions                           | Detection Method  |
| --------------------- | ------------------------------------ | ----------------- |
| Python                | `.py`, `.pyw`                        | AST-based parsing |
| JavaScript/TypeScript | `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs` | Regex patterns    |
| Java                  | `.java`                              | Regex patterns    |
| Go                    | `.go`                                | Regex patterns    |

## Installation

### Prerequisites

- Python 3.7 or higher
- No external dependencies (uses only Python standard library)

### Setup

1. # Make executable:

   ```bash
   chmod +x scanner.py
   ```

2. Verify installation:
   ```bash
   python3 scanner.py --help
   ```

## Usage

### Basic Commands

```bash
# Scan current directory
python3 scanner.py .

# Scan specific directory
python3 scanner.py /path/to/repository

# Scan single file
python3 scanner.py /path/to/file.py

# JSON output format
python3 scanner.py /path/to/repository --format json

# Save results to file (text format)
python3 scanner.py /path/to/repository --output results.txt

# Save results to file (JSON format)
python3 scanner.py /path/to/repository --format json --output results.json

# Use multiple worker processes (recommended for large repos)
python3 scanner.py /path/to/repository --workers 8

# Comprehensive scan with all options
python3 scanner.py /path/to/repository --workers 8 --format json --output output.json --exclude build dist cache

# Exclude specific directories
python3 scanner.py /path/to/repository --exclude build dist cache node_modules

```

### Command-Line Options

| Option            | Description                       | Default |
| ----------------- | --------------------------------- | ------- |
| `--format`        | Output format (`text` or `json`)  | `text`  |
| `--output`, `-o`  | Save output to file               | stdout  |
| `--workers`, `-w` | Number of worker processes        | 4       |
| `--exclude`       | Additional directories to exclude | None    |

### Test Repository

The distribution includes a test repository with multiple languages:

```bash
# Basic scan
python3 scanner.py test-multiple-langs

# JSON output with function analysis
python3 scanner.py test-multiple-langs --format json | jq '.functions_by_language'

# Get total function count
python3 scanner.py test-multiple-langs --format json | jq '.total_functions'
```


### Running Against scancode Repository

```bash
# Clone a sample repository
git clone https://github.com/aboutcode-org/scancode-toolkit.git
cd scancode-toolkit/

# Basic function analysis
python3 scanner.py scancode-toolkit/

# Detailed analysis with JSON output
python3 scanner.py scancode-toolkit/ --format json --output analysis.json

# Performance scan with multiple workers
python3 scanner.py scancode-toolkit/ --workers 8 --format json

# Exclude build directories and vendor folders
python3 scanner.py scancode-toolkit/ --exclude build dist vendor node_modules --format json
```

### Sample Verification Output

When running against the test repository, you should see:

```bash
$ python3 scanner.py test-multiple-langs

FUNCTION ANALYSIS REPORT
==================================================
DEFINED FUNCTIONS: 66
IMPORTED FUNCTIONS: 37
MISSING DEFINITIONS: 22
ORPHANED FUNCTIONS: 62
CIRCULAR IMPORTS: 0
SCAN TIME: 0.03 seconds

CRITICAL ISSUES:
--------------------
ERROR: Function/class 'context' imported from 'context' but definition not found
   FILE: test-multiple-langs/server.go:4
ERROR: Function/class 'json' imported from 'encoding/json' but definition not found
   FILE: test-multiple-langs/server.go:5
ERROR: Function/class 'fmt' imported from 'fmt' but definition not found
   FILE: test-multiple-langs/server.go:6
ERROR: Function/class 'log' imported from 'log' but definition not found
   FILE: test-multiple-langs/server.go:7
ERROR: Function/class 'http' imported from 'net/http' but definition not found
   FILE: test-multiple-langs/server.go:8
ERROR: Function/class 'strconv' imported from 'strconv' but definition not found
   FILE: test-multiple-langs/server.go:9
ERROR: Function/class 'sync' imported from 'sync' but definition not found
   FILE: test-multiple-langs/server.go:10
ERROR: Function/class 'mux' imported from 'github.com/gorilla/mux' but definition not found
   FILE: test-multiple-langs/server.go:13
ERROR: Function/class 'websocket' imported from 'github.com/gorilla/websocket' but definition not found
   FILE: test-multiple-langs/server.go:14
ERROR: Function/class 'v8' imported from 'github.com/go-redis/redis/v8' but definition not found
   FILE: test-multiple-langs/server.go:15
   ... and 12 more critical issues

WARNINGS:
------------
WARNING: Function/class 'NewUserService' is defined but never imported or used
   FILE: test-multiple-langs/server.go:34
WARNING: Function/class 'GetAllUsers' is defined but never imported or used
   FILE: test-multiple-langs/server.go:41
WARNING: Function/class 'GetUserByID' is defined but never imported or used
   FILE: test-multiple-langs/server.go:47
WARNING: Function/class 'CreateUser' is defined but never imported or used
   FILE: test-multiple-langs/server.go:59
WARNING: Function/class 'UpdateUser' is defined but never imported or used
   FILE: test-multiple-langs/server.go:68
WARNING: Function/class 'DeleteUser' is defined but never imported or used
   FILE: test-multiple-langs/server.go:76
WARNING: Function/class 'NewUserHandler' is defined but never imported or used
   FILE: test-multiple-langs/server.go:87
WARNING: Function/class 'HandleGetUsers' is defined but never imported or used
   FILE: test-multiple-langs/server.go:91
WARNING: Function/class 'HandleGetUser' is defined but never imported or used
   FILE: test-multiple-langs/server.go:103
WARNING: Function/class 'HandleCreateUser' is defined but never imported or used
   FILE: test-multiple-langs/server.go:122
   ... and 52 more warnings

FUNCTIONS BY LANGUAGE:
--------------------------
  Go: 38
  Java: 29
  JavaScript/TypeScript: 17
  Python: 17

DETAILED ANALYSIS:
---------------------
Total files processed: 4/5
Functions found: 101
Import statements: 37
Function definitions: 66

$ python3 scanner.py test-multiple-langs --format json
{
  "total_files": 5,
  "processed_files": 4,
  "total_functions": 101,
  "total_imports": 37,
  "total_definitions": 66,
  "functions_by_language": {
    "Go": 38,
    "Python": 17,
    "Java": 29,
    "JavaScript/TypeScript": 17
  },
  "functions": [
    {
      "name": "context",
      "type": "imported",
      "language": "Go",
      "file_path": "test-multiple-langs/server.go",
      "line_number": 4,
      "signature": null,
      "module_source": "context",
      "original_name": null,
      "import_alias": null
    },
    {
      "name": "json",
      "type": "imported",
      "language": "Go",
      "file_path": "test-multiple-langs/server.go",
      "line_number": 5,
      "signature": null,
      "module_source": "encoding/json",
      "original_name": null,
      "import_alias": null
    },
  ]
```
 