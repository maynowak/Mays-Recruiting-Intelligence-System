#!/usr/bin/env python3
"""
Build script for Lambda deployment package.

This script creates a deployment package for AWS Lambda.
"""

import os
import sys
import zipfile
import argparse
from pathlib import Path


def build_zip(source_dir: str, output_file: str, include_files: bool = True):
    """
    Build a Lambda deployment package.
    
    Args:
        source_dir: Directory containing source code
        output_file: Output zip file path
        include_files: Whether to include non-Python files
    """
    source_path = Path(source_dir)
    output_path = Path(output_file)
    
    if not source_path.exists():
        print(f"Error: Source directory {source_dir} does not exist")
        sys.exit(1)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_path.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(source_path)
                
                # Skip __pycache__ and .pyc files
                if '__pycache__' in str(file_path) or file_path.suffix == '.pyc':
                    continue
                
                # Include files if requested, or always include Python files
                if file_path.suffix in ['.py', '.txt', '.md', 'requirements.txt'] or include_files:
                    zf.write(file_path, relative_path)
                    print(f"Added: {relative_path}")
    
    print(f"\nCreated deployment package: {output_file}")
    print(f"Size: {output_path.stat().st_size / 1024:.2f} KB")


def validate_package(zip_path: str) -> bool:
    """
    Validate the deployment package.
    
    Args:
        zip_path: Path to the zip file
        
    Returns:
        True if valid, False otherwise
    """
    path = Path(zip_path)
    
    if not path.exists():
        print(f"Error: File {zip_path} does not exist")
        return False
    
    with zipfile.ZipFile(path, 'r') as zf:
        # Check for required files
        files = zf.namelist()
        print(f"Package contains {len(files)} files")
        
        # Check for common structure
        if 'handler.py' not in files:
            print("Warning: handler.py not found in package")
        
        return True


def main():
    parser = argparse.ArgumentParser(description='Build Lambda deployment package')
    parser.add_argument('--source', '-s', default='lambda',
                        help='Source directory (default: lambda)')
    parser.add_argument('--output', '-o', default='lambda.zip',
                        help='Output zip file (default: lambda.zip)')
    parser.add_argument('--validate', '-v', action='store_true',
                        help='Validate the built package')
    parser.add_argument('--bundle', choices=['agent', 'reader', 'all'],
                        default=None,
                        help='Deterministic RIS bundle(s): agent -> terraform/lambda.zip, '
                             'reader -> lambda/dist/orders-reader.zip, all -> both. '
                             'Impliziert validen, reproduzierbaren Inhalt (s. build_bundle).')

    args = parser.parse_args()

    if args.bundle in ("agent", "all"):
        info = build_agent_bundle()
        print(f"Built agent bundle: {info['output']} "
              f"({info['files']} files, sha256 {info['sha256'][:16]}...)")
    if args.bundle in ("reader", "all"):
        info = build_reader_bundle()
        print(f"Built reader bundle: {info['output']} "
              f"({info['files']} files, sha256 {info['sha256'][:16]}...)")
    if args.bundle is None:
        build_zip(args.source, args.output)

        if args.validate:
            if not validate_package(args.output):
                sys.exit(1)


# ---------------------------------------------------------------------------
# Deterministische RIS-Bundles (Lifecycle-Vertrag).
#
# Vertrag:
#   gleiche Quelle -> identische Bytes -> identischer source_code_hash
#                    -> Terraform no-op
#   geaenderte Quelle -> anderer Hash -> Lambda-Update im Plan
#
# Mittel: sortierte Eintraege, fixierte Timestamps/Permissions, klarer
# Ausschluss-Satz (kein .git, kein Cache, kein Bytecode, keine Tests).
# Beweis: tests/test_lambda_packaging.py (A–G).
# ---------------------------------------------------------------------------

#: Fixer Zip-Timestamp (Reproduzierbarkeit statt Build-Zeit).
FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)

#: Nur Python-Module gehoeren ins Runtime-Bundle (keine Docs/Specs/Artefakte;
#: entspricht dem bewiesenen Live-Inhalt).
ALLOWED_SUFFIXES = (".py",)

#: Pfade/Arten, die NIE in ein Bundle gehoeren.
EXCLUDED_PARTS = ("__pycache__", ".git", ".pytest_cache", ".DS_Store")
EXCLUDED_SUFFIXES = (".pyc", ".pyo")

#: Bewiesenes Agent-Layout (Einstieg handler.lambda_handler am Root).
AGENT_FILES = ["lambda/handler.py", "lambda/documents.py"]
AGENT_DIRS = ["agents", "jobsearch"]

#: Reader-Layout (Einstieg orders_reader.handler am Root).
READER_FILES = ["lambda/orders_reader.py"]


def _collect(repo_root: Path, rel_paths) -> list:
    """Dateien einsammeln: sortiert, ohne Ausschluesse (relativ zu repo_root)."""
    collected = []
    for rel in rel_paths:
        path = repo_root / rel
        if path.is_file():
            collected.append(rel)
        elif path.is_dir():
            for file_path in sorted(path.rglob("*")):
                if not file_path.is_file():
                    continue
                rel_file = file_path.relative_to(repo_root).as_posix()
                if file_path.suffix not in ALLOWED_SUFFIXES:
                    continue
                if any(part in file_path.parts for part in EXCLUDED_PARTS):
                    continue
                if file_path.suffix in EXCLUDED_SUFFIXES:
                    continue
                collected.append(rel_file)
    return sorted(set(collected))


def build_bundle(repo_root, files: list, arcname_fn, output: str) -> dict:
    """Deterministisches Bundle bauen. Gibt {output, files, sha256} zurueck."""
    import hashlib

    repo_root = Path(repo_root)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entries = sorted((f, arcname_fn(f)) for f in files)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for source_rel, arcname in entries:
            data = (repo_root / source_rel).read_bytes()
            info = zipfile.ZipInfo(arcname, date_time=FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 << 16)
            archive.writestr(info, data)

    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return {"output": str(output_path), "files": len(entries), "sha256": digest}


def build_agent_bundle(repo_root: str = ".") -> dict:
    """Agent-Bundle (handler.py + documents.py + agents/ + jobsearch/) -> terraform/lambda.zip."""
    repo = Path(repo_root)
    files = _collect(repo, AGENT_FILES + AGENT_DIRS)

    def arcname(source_rel: str) -> str:
        if source_rel.startswith("lambda/"):
            return source_rel[len("lambda/"):]
        return source_rel

    return build_bundle(repo, files, arcname,
                        str(repo / "terraform" / "lambda.zip"))


def build_reader_bundle(repo_root: str = ".") -> dict:
    """Reader-Bundle (orders_reader.py) -> lambda/dist/orders-reader.zip."""
    repo = Path(repo_root)
    return build_bundle(repo, READER_FILES, lambda source_rel: "orders_reader.py",
                        str(repo / "lambda" / "dist" / "orders-reader.zip"))


if __name__ == '__main__':
    main()