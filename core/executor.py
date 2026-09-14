# -*- coding: utf-8 -*-
"""
System command executor with structured error handling.

**Single Responsibility:** Execute OS-level commands and manage files —
nothing more.  Provides a ``DryRunExecutor`` substitute for safe testing
without side effects (Liskov Substitution Principle).
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from core.interfaces import ISystemExecutor


class LinuxExecutor(ISystemExecutor):
    """Production executor — runs real commands on the host system."""

    def run(self, command: str, check: bool = True) -> Tuple[int, str, str]:
        """Execute *command* via ``/bin/bash`` and return (rc, stdout, stderr)."""
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"Command failed (rc={result.returncode}): {command}\n"
                f"stderr: {result.stderr.strip()}"
            )
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    def write_file(self, path: Path, content: str, mode: int = 0o644) -> None:
        """Write *content* to *path* with the given POSIX *mode*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        path.chmod(mode)

    def file_exists(self, path: Path) -> bool:
        return path.exists()

    def backup_file(self, path: Path) -> Optional[Path]:
        """Create a timestamped backup of *path*."""
        if not path.exists():
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_suffix(f".bak.{timestamp}")
        shutil.copy2(str(path), str(backup_path))
        return backup_path


class DryRunExecutor(ISystemExecutor):
    """Test / dry-run executor — logs actions without side effects (LSP)."""

    def __init__(self) -> None:
        self.log: list[str] = []

    def run(self, command: str, check: bool = True) -> Tuple[int, str, str]:
        self.log.append(f"[DRY-RUN] exec: {command}")
        return 0, "", ""

    def write_file(self, path: Path, content: str, mode: int = 0o644) -> None:
        self.log.append(f"[DRY-RUN] write: {path} (mode={oct(mode)}, {len(content)} bytes)")

    def file_exists(self, path: Path) -> bool:
        return path.exists()

    def backup_file(self, path: Path) -> Optional[Path]:
        self.log.append(f"[DRY-RUN] backup: {path}")
        return None
