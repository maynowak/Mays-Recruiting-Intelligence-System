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
    
    args = parser.parse_args()
    
    build_zip(args.source, args.output)
    
    if args.validate:
        if not validate_package(args.output):
            sys.exit(1)


if __name__ == '__main__':
    main()