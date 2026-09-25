#!/usr/bin/env python3
"""
Centralized RIS Installer Orchestrator

Manages project installations and coordinates with project-specific installers.

This installer handles:
1. Project discovery and checkout
2. Git repository management
3. Coordination with project-specific installers
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class GitInfo:
    """Git repository identity information."""
    root: str
    remote: str
    branch: str
    commit: str
    is_clean: bool


@dataclass
class ProjectInfo:
    """Project information for managed repositories."""
    name: str
    git_url: str
    local_path: Path
    git_info: Optional[GitInfo] = None
    installer_exists: bool = False


class RISInstaller:
    """
    Central installer for managing Mays-RIS and dependent projects.
    
    This installer provides:
    - Project checkout management
    - Git discovery and validation
    - Coordination with project-specific installers
    """
    
    DEFAULT_PROJECTS_DIR = Path("projects")
    PROJECTS = {
        "mays-orders": {
            "git_url": "git@github.com:maynowak/mays-order-aws.git",
            "name": "Mays-Orders-AWS",
            "installer_path": "installer",
        }
    }
    
    def __init__(self, projects_dir: Optional[Path] = None, dry_run: bool = True):
        self.projects_dir = projects_dir or self.DEFAULT_PROJECTS_DIR
        self.dry_run = dry_run
        
    def discover_project(self, project_name: str) -> ProjectInfo:
        """
        Discover a project's local state and git information.
        
        Args:
            project_name: Key from PROJECTS dict
            
        Returns:
            ProjectInfo with current state
        """
        if project_name not in self.PROJECTS:
            raise ValueError(f"Unknown project: {project_name}")
            
        project_config = self.PROJECTS[project_name]
        local_path = self.projects_dir / project_name.replace("-", "_")
        
        info = ProjectInfo(
            name=project_config["name"],
            git_url=project_config["git_url"],
            local_path=local_path
        )
        
        # Check if directory exists
        if not local_path.exists():
            return info
            
        # Check if it's a git repository
        git_dir = local_path / ".git"
        if not git_dir.exists() and not git_dir.is_file():
            return info
            
        # Get git info
        try:
            info.git_info = self._get_git_info(local_path)
        except Exception:
            pass
            
        # Check for installer
        installer_path = local_path / project_config["installer_path"]
        info.installer_exists = installer_path.exists() and (installer_path / "__init__.py").exists()
        
        return info
    
    def _get_git_info(self, repo_path: Path) -> GitInfo:
        """Get git repository information."""
        def git_cmd(args):
            result = subprocess.run(
                ["git"] + args,
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
            
        root = git_cmd(["rev-parse", "--show-toplevel"])
        remote = git_cmd(["remote", "get-url", "origin"])
        branch = git_cmd(["rev-parse", "--abbrev-ref", "HEAD"])
        commit = git_cmd(["rev-parse", "HEAD"])
        
        # Check if working tree is clean
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        is_clean = status_result.returncode == 0 and not status_result.stdout.strip()
        
        return GitInfo(
            root=root,
            remote=remote,
            branch=branch,
            commit=commit,
            is_clean=is_clean
        )
    
    def checkout_project(self, project_name: str) -> ProjectInfo:
        """
        Ensure project is checked out locally.
        
        Args:
            project_name: Key from PROJECTS dict
            
        Returns:
            ProjectInfo with checkout status
        """
        if project_name not in self.PROJECTS:
            raise ValueError(f"Unknown project: {project_name}")
            
        project_config = self.PROJECTS[project_name]
        local_path = self.projects_dir / project_name.replace("-", "_")
        
        info = ProjectInfo(
            name=project_config["name"],
            git_url=project_config["git_url"],
            local_path=local_path
        )
        
        if self.dry_run:
            if local_path.exists():
                info.git_info = self._get_git_info(local_path)
                info.installer_exists = (local_path / project_config["installer_path"]).exists()
            return info
            
        # Clone if not exists
        if not local_path.exists():
            subprocess.run(
                ["git", "clone", project_config["git_url"], str(local_path)],
                check=True
            )
            
        # Verify it's the correct repository
        git_dir = local_path / ".git"
        if git_dir.exists() or git_dir.is_file():
            info.git_info = self._get_git_info(local_path)
            if info.git_info and info.git_info.remote != project_config["git_url"]:
                raise RuntimeError(
                    f"Wrong repository! Expected {project_config['git_url']}, "
                    f"got {info.git_info.remote}"
                )
                
        info.installer_exists = (local_path / project_config["installer_path"]).exists()
        return info
    
    def run_project_installer(self, project_name: str, command: str = "validate") -> Dict[str, Any]:
        """
        Run the project-specific installer.
        
        Args:
            project_name: Key from PROJECTS dict
            command: Command to run (validate, plan, etc.)
            
        Returns:
            Result dictionary
        """
        info = self.checkout_project(project_name)
        
        if not info.git_info:
            return {"status": "ERROR", "error": "Project not checked out properly"}
            
        if not info.installer_exists:
            return {"status": "ERROR", "error": "Installer not found in project"}
            
        installer_path = info.local_path / self.PROJECTS[project_name]["installer_path"]
        installer_script = installer_path / f"{info.name.lower().replace('-', '_')}"
        
        # Check if installer script exists
        if not installer_script.exists():
            # Try alternative names
            possible_names = ["installer", "main", "cli"]
            installer_script = next(
                (installer_path / name for name in possible_names 
                 if (installer_path / name).exists()),
                None
            )
            
        if not installer_script or not installer_script.exists():
            return {"status": "ERROR", "error": "Installer script not found"}
            
        if self.dry_run:
            return {
                "status": "DRY_RUN",
                "project": project_name,
                "installer_path": str(installer_script),
                "git": {
                    "remote": info.git_info.remote,
                    "branch": info.git_info.branch,
                    "commit": info.git_info.commit
                },
                "would_run": f"python {installer_script} {command}"
            }
            
        # Run the installer
        import shutil
        venv_python = info.local_path / ".venv" / "bin" / "python"
        python = str(venv_python) if venv_python.exists() else sys.executable
        
        results = {"project": project_name, "git_info": info.git_info}
        
        try:
            result = subprocess.run(
                [python, str(installer_script), command],
                cwd=info.local_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            results.update({
                "status": "SUCCESS" if result.returncode == 0 else "FAILED",
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else ""
            })
        except subprocess.TimeoutExpired:
            results["status"] = "TIMEOUT"
        except Exception as e:
            results["status"] = "ERROR"
            results["error"] = str(e)
            
        return results


def main():
    parser = argparse.ArgumentParser(
        description="RIS Project Installer Orchestrator"
    )
    parser.add_argument(
        "project",
        help="Project to manage (e.g., mays-orders)"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="validate",
        help="Command to run (validate, plan, etc.)"
    )
    parser.add_argument(
        "--projects-dir", default=None,
        help="Directory for project checkouts"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Verify existing checkout (do not clone)"
    )
    parser.add_argument(
        "--format", choices=["text", "json"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Dry run mode (default: True)"
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually execute (disables dry-run)"
    )
    
    args = parser.parse_args()
    
    installer = RISInstaller(
        projects_dir=Path(args.projects_dir) if args.projects_dir else None,
        dry_run=not args.execute
    )
    
    if args.verify:
        info = installer.discover_project(args.project)
    else:
        info = installer.checkout_project(args.project)
        
    result = installer.run_project_installer(args.project, args.command)
    result["checkout"] = {
        "path": str(info.local_path),
        "exists": info.local_path.exists(),
        "git_info": info.git_info,
        "installer_exists": info.installer_exists
    }
    
    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"=== RIS Installer: {args.project} ===")
        print(f"Local path: {info.local_path}")
        if info.git_info:
            print(f"Git: {info.git_info.remote} @ {info.git_info.branch}")
            print(f"Commit: {info.git_info.commit}")
        print(f"Status: {result['status']}")


if __name__ == "__main__":
    sys.exit(main() or 0)