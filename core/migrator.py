# -*- coding: utf-8 -*-
"""
Project migrator — upgrades and repairs previously deployed projects.

**Single Responsibility:** Scan an existing systemd service file, detect
misconfigurations (wrong socket path, missing ``--umask``, incorrect WSGI
module), and apply corrective changes without downtime where possible.

"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from core.detector import DjangoProjectDetector
from core.interfaces import IProjectMigrator, IServiceGenerator, ISystemExecutor
from core.models import (
    DiagnosticCheck,
    DiagnosticReport,
    DiagnosticStatus,
    DjangoProjectInfo,
    DomainConfig,
    ServiceConfig,
)


class ProjectMigrator(IProjectMigrator):
    """Scans and repairs previously deployed Gunicorn services."""

    def __init__(
        self,
        executor: ISystemExecutor,
        detector: DjangoProjectDetector,
        generator: IServiceGenerator,
    ) -> None:
        self._executor = executor
        self._detector = detector
        self._generator = generator

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def needs_migration(self, domain_config: DomainConfig) -> bool:
        """Return ``True`` if the existing deployment has known issues."""
        service_file = domain_config.service_file
        if not self._executor.file_exists(service_file):
            return False

        content = service_file.read_text(encoding="utf-8", errors="replace")

        checks = [
            "--umask" not in content,
            self._has_socket_mismatch(content, domain_config),
            self._has_wsgi_mismatch(content, domain_config),
            "ProtectSystem" not in content,
        ]
        return any(checks)

    def migrate(self, domain_config: DomainConfig) -> DiagnosticReport:
        """Perform the migration / repair and return a diagnostic report."""
        report = DiagnosticReport(domain_config=domain_config)
        dc = domain_config

        # --- Step 1: Read existing service file ---
        if not self._executor.file_exists(dc.service_file):
            report.checks.append(DiagnosticCheck(
                name="Service File",
                status=DiagnosticStatus.CRITICAL,
                message=f"Service file not found: {dc.service_file}",
                suggestion="Run 'setup' command first to create the service.",
            ))
            return report

        # --- Step 2: Backup existing service file ---
        backup_path = self._executor.backup_file(dc.service_file)
        report.checks.append(DiagnosticCheck(
            name="Backup",
            status=DiagnosticStatus.OK,
            message=f"Backed up to: {backup_path}",
        ))

        # --- Step 3: Re-detect the project (smart detection) ---
        project_info = self._detector.detect(dc.web_dir)
        if not project_info.is_valid:
            report.checks.append(DiagnosticCheck(
                name="Project Detection",
                status=DiagnosticStatus.CRITICAL,
                message="Could not detect project structure.",
                suggestion=f"Errors: {'; '.join(project_info.errors)}",
            ))
            return report

        report.checks.append(DiagnosticCheck(
            name="Project Detection",
            status=DiagnosticStatus.OK,
            message=f"Layout: {project_info.layout.name}, "
                    f"WSGI: {project_info.wsgi_module}",
        ))

        # --- Step 4: Generate corrected service file ---
        service_config = ServiceConfig(
            domain_config=dc,
            project_info=project_info,
        )
        new_content = self._generator.generate(service_config)
        self._executor.write_file(dc.service_file, new_content, mode=0o644)

        report.checks.append(DiagnosticCheck(
            name="Service File Update",
            status=DiagnosticStatus.OK,
            message="Service file regenerated with --umask 007, hardened security, "
                    f"and correct WSGI module ({project_info.wsgi_module}).",
        ))

        # --- Step 5: Fix file permissions ---
        self._fix_permissions(dc, project_info, report)

        # --- Step 6: Reload and restart ---
        self._restart_service(dc, report)

        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _has_socket_mismatch(self, content: str, dc: DomainConfig) -> bool:
        """Check if the socket path in the service file differs from canonical."""
        match = re.search(r"unix:(\S+)", content)
        if match:
            existing = Path(match.group(1))
            return existing != dc.socket_path
        return True

    def _has_wsgi_mismatch(self, content: str, dc: DomainConfig) -> bool:
        """Check if the WSGI module might be wrong for the current project."""
        project_info = self._detector.detect(dc.web_dir)
        if not project_info.is_valid:
            return False
        return project_info.wsgi_module not in content

    def _fix_permissions(
        self,
        dc: DomainConfig,
        project_info: DjangoProjectInfo,
        report: DiagnosticReport,
    ) -> None:
        """Fix ownership and permissions on db.sqlite3 and static directory."""
        web_dir = dc.web_dir

        # Fix db.sqlite3
        db_file = web_dir / "db.sqlite3"
        if self._executor.file_exists(db_file):
            self._executor.run(
                f"chown {dc.user}:www-data {db_file} && chmod 664 {db_file}",
                check=False,
            )
            report.checks.append(DiagnosticCheck(
                name="Database Permissions",
                status=DiagnosticStatus.OK,
                message=f"Set {dc.user}:www-data 664 on db.sqlite3",
            ))

        # Fix static root directory
        static_dir = web_dir / project_info.static_root_name
        if self._executor.file_exists(static_dir):
            self._executor.run(
                f"chown -R {dc.user}:www-data {static_dir}",
                check=False,
            )
            report.checks.append(DiagnosticCheck(
                name="Static Files Permissions",
                status=DiagnosticStatus.OK,
                message=f"Fixed ownership on {static_dir}",
            ))

    def _restart_service(self, dc: DomainConfig, report: DiagnosticReport) -> None:
        """Reload systemd daemon and restart the Gunicorn service."""
        self._executor.run("systemctl daemon-reload", check=False)
        rc, _, stderr = self._executor.run(
            f"systemctl restart {dc.service_name}", check=False
        )

        if rc == 0:
            report.checks.append(DiagnosticCheck(
                name="Service Restart",
                status=DiagnosticStatus.OK,
                message=f"{dc.service_name} restarted successfully.",
            ))
        else:
            report.checks.append(DiagnosticCheck(
                name="Service Restart",
                status=DiagnosticStatus.CRITICAL,
                message=f"Failed to restart {dc.service_name}.",
                suggestion=f"Check logs: journalctl -u {dc.service_name} -n 30\n"
                           f"Error: {stderr}",
            ))
