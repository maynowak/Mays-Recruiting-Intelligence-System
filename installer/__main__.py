#!/usr/bin/env python3
"""
RIS Installer CLI

Usage:
    python -m installer.project_manager
    python -m installer.project_manager mays-orders --execute validate
    python -m installer.project_manager mays-orders plan --format json
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from installer.orchestrator import RISInstaller

if __name__ == "__main__":
    sys.exit(RISInstaller().main() if hasattr(RISInstaller, 'main') else 0)