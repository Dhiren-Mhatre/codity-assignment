# Function Scanner

Language-agnostic tool for discovering functions in repositories. Supports Python, JavaScript/TypeScript, Java, C/C++, Go with multiprocessing for high performance.

## Supported Languages

| Language | Extensions | Detection Method |
|----------|------------|------------------|
| Python | `.py`, `.pyw` | AST-based parsing |
| JavaScript/TypeScript | `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs` | Regex patterns |
| Java | `.java` | Regex patterns |
| C/C++ | `.c`, `.cpp`, `.cc`, `.cxx`, `.h`, `.hpp` | Regex patterns |
| Go | `.go` | Regex patterns |

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

| Option | Description | Default |
|--------|-------------|---------|
| `--format` | Output format (`text` or `json`) | `text` |
| `--output`, `-o` | Save output to file | stdout |
| `--workers`, `-w` | Number of worker processes | 4 |
| `--exclude` | Additional directories to exclude | None |

### Performance Testing

**Real-World Repository Tests:**

1. **ScanCode Toolkit (Multi-language repository)(685.41 MiB):**
   ```bash
   # Clone ScanCode Toolkit repository
   git clone  https://github.com/nexB/scancode-toolkit.git

   # Basic scan
   python3 scanner.py scancode-toolkit

   # Performance test with all languages
   python3 scanner.py scancode-toolkit --workers 8 --format json --output scancode_functions.json

   # Analyze language distribution
   python3 scanner.py scancode-toolkit --format json | jq '.functions_by_language'
   ```

## Verification

### Test on Comprehensive Repository

The distribution includes a comprehensive test repository with all 5 supported languages:

1. **Test the comprehensive repository:**
   ```bash
   # Basic scan
   python3 scanner.py test-multiple-langs

   # JSON output with function analysis
   python3 scanner.py test-multiple-langs --format json | jq '.functions_by_language'

   # Get total function count
   python3 scanner.py test-multiple-langs --format json | jq '.total_functions'

   # Performance test
   time python3 scanner.py test-multiple-langs --workers 4
   ```

2. **Expected output:**
   ```
   Function Scanner Results
   ==================================================
   Total files: 5
   Processed files: 5
   Total functions found: 124
   Scan time: 0.03 seconds

   Functions by language:
     C/C++: 24
     Go: 38
     Java: 29
     JavaScript/TypeScript: 16
     Python: 17
   ```
