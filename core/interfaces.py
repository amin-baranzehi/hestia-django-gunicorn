# -*- coding: utf-8 -*-
"""
Abstract interfaces (contracts) for the deployment engine.

Applying the **Interface Segregation Principle** (ISP) and
**Dependency Inversion Principle** (DIP): every high-level orchestrator
depends on these thin abstractions — never on concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

from core.models import (
    DiagnosticReport,
    DjangoProjectInfo,
    DomainConfig,
    ServiceConfig,
)


class IDjangoDetector(ABC):
    """Inspects a Django project directory and returns structured metadata."""

    @abstractmethod
    def detect(self, web_dir: Path, project_hint: Optional[str] = None) -> DjangoProjectInfo:
        """Analyse *web_dir* and return a populated ``DjangoProjectInfo``."""


class IServiceGenerator(ABC):
    """Renders systemd service unit content from a ``ServiceConfig``."""

    @abstractmethod
    def generate(self, config: ServiceConfig) -> str:
        """Return the full text of a systemd ``.service`` unit file."""


class ISystemExecutor(ABC):
    """Abstraction over OS-level command execution."""

    @abstractmethod
    def run(self, command: str, check: bool = True) -> Tuple[int, str, str]:
        """Execute *command* and return ``(return_code, stdout, stderr)``."""

    @abstractmethod
    def write_file(self, path: Path, content: str, mode: int = 0o644) -> None:
        """Write *content* to *path* with the given POSIX *mode*."""

    @abstractmethod
    def file_exists(self, path: Path) -> bool:
        """Return ``True`` if *path* exists on the filesystem."""

    @abstractmethod
    def backup_file(self, path: Path) -> Optional[Path]:
        """Create a timestamped backup of *path* and return the backup path."""


class INginxManager(ABC):
    """Manages HestiaCP NGINX proxy template installation."""

    @abstractmethod
    def install_templates(self, tpl_source: Path, stpl_source: Path) -> None:
        """Copy templates to the HestiaCP template directory and set permissions."""

    @abstractmethod
    def rebuild_domain(self, domain_config: DomainConfig) -> None:
        """Force-rebuild the NGINX configuration for a domain."""


class IProjectMigrator(ABC):
    """Upgrades / repairs a previously deployed project in-place."""

    @abstractmethod
    def needs_migration(self, domain_config: DomainConfig) -> bool:
        """Return ``True`` if the existing deployment requires migration."""

    @abstractmethod
    def migrate(self, domain_config: DomainConfig) -> DiagnosticReport:
        """Perform the migration / repair and return a diagnostic report."""


class IDeploymentDoctor(ABC):
    """Runs post-deployment health checks."""

    @abstractmethod
    def diagnose(self, domain_config: DomainConfig) -> DiagnosticReport:
        """Run all health checks and return a ``DiagnosticReport``."""
