# -*- coding: utf-8 -*-
"""
Post-deployment health checker (doctor).

**Single Responsibility:** Run a suite of diagnostic checks against a live
deployment and return a structured ``DiagnosticReport`` with colour-coded
terminal output.
"""

from __future__ import annotations

try:
    import grp
except ImportError:
    grp = None  # type: ignore

try:
    import pwd
except ImportError:
    pwd = None  # type: ignore

import os
import stat
from pathlib import Path

from core.interfaces import IDeploymentDoctor, ISystemExecutor
from core.models import (
    DiagnosticCheck,
    DiagnosticReport,
    DiagnosticStatus,
    DomainConfig,
)


class DeploymentDoctor(IDeploymentDoctor):
    """Runs comprehensive health checks on a deployed Django/Gunicorn site."""

    def __init__(self, executor: ISystemExecutor) -> None:
        self._executor = executor

    def diagnose(self, domain_config: DomainConfig) -> DiagnosticReport:
        """Run all health checks and return a ``DiagnosticReport``."""
        dc = domain_config
        report = DiagnosticReport(domain_config=dc)

        self._check_service_status(dc, report)
        self._check_socket(dc, report)
        self._check_database_permissions(dc, report)
        self._check_static_files(dc, report)
        self._check_nginx_template(dc, report)
        self._check_socket_response(dc, report)

        return report

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_service_status(self, dc: DomainConfig, report: DiagnosticReport) -> None:
        """Check if the Gunicorn systemd service is active."""
        rc, stdout, _ = self._executor.run(
            f"systemctl is-active {dc.service_name}", check=False
        )
        if rc == 0 and "active" in stdout:
            report.checks.append(DiagnosticCheck(
                name="Gunicorn Service",
                status=DiagnosticStatus.OK,
                message=f"{dc.service_name} is active and running.",
            ))
        else:
            report.checks.append(DiagnosticCheck(
                name="Gunicorn Service",
                status=DiagnosticStatus.CRITICAL,
                message=f"{dc.service_name} is NOT running.",
                suggestion=f"sudo systemctl start {dc.service_name}\n"
                           f"journalctl -u {dc.service_name} -n 30",
            ))

    def _check_socket(self, dc: DomainConfig, report: DiagnosticReport) -> None:
        """Verify unix socket exists with correct ownership and permissions."""
        sock = dc.socket_path

        if not self._executor.file_exists(sock):
            report.checks.append(DiagnosticCheck(
                name="Unix Socket",
                status=DiagnosticStatus.CRITICAL,
                message=f"Socket not found: {sock}",
                suggestion=f"sudo systemctl restart {dc.service_name}",
            ))
            return

        try:
            st = os.stat(str(sock))
            owner = pwd.getpwuid(st.st_uid).pw_name
            group = grp.getgrgid(st.st_gid).gr_name
            mode = stat.S_IMODE(st.st_mode)

            issues = []
            if owner != dc.user:
                issues.append(f"Owner is '{owner}', expected '{dc.user}'")
            if group != "www-data":
                issues.append(f"Group is '{group}', expected 'www-data'")
            if mode & 0o060 != 0o060:
                issues.append(f"Mode is {oct(mode)}, group needs rw (0o660+)")

            if issues:
                report.checks.append(DiagnosticCheck(
                    name="Unix Socket",
                    status=DiagnosticStatus.WARNING,
                    message=f"Socket exists but has permission issues: {'; '.join(issues)}",
                    suggestion=f"sudo chown {dc.user}:www-data {sock} && sudo chmod 660 {sock}",
                ))
            else:
                report.checks.append(DiagnosticCheck(
                    name="Unix Socket",
                    status=DiagnosticStatus.OK,
                    message=f"Socket OK — {owner}:{group} {oct(mode)}",
                ))
        except (OSError, KeyError) as exc:
            report.checks.append(DiagnosticCheck(
                name="Unix Socket",
                status=DiagnosticStatus.WARNING,
                message=f"Could not inspect socket: {exc}",
            ))

    def _check_database_permissions(self, dc: DomainConfig, report: DiagnosticReport) -> None:
        """Check db.sqlite3 is writable by www-data group."""
        db_path = dc.web_dir / "db.sqlite3"

        if not self._executor.file_exists(db_path):
            report.checks.append(DiagnosticCheck(
                name="Database (SQLite)",
                status=DiagnosticStatus.OK,
                message="No db.sqlite3 found (possibly using PostgreSQL).",
            ))
            return

        try:
            st = os.stat(str(db_path))
            mode = stat.S_IMODE(st.st_mode)
            group = grp.getgrgid(st.st_gid).gr_name if grp else "www-data"

            if group != "www-data" or mode & 0o060 != 0o060:
                report.checks.append(DiagnosticCheck(
                    name="Database (SQLite)",
                    status=DiagnosticStatus.CRITICAL,
                    message=f"db.sqlite3 permissions incorrect (group={group}, mode={oct(mode)}).",
                    suggestion=f"sudo chown {dc.user}:www-data {db_path} && sudo chmod 664 {db_path}",
                ))
            else:
                report.checks.append(DiagnosticCheck(
                    name="Database (SQLite)",
                    status=DiagnosticStatus.OK,
                    message="db.sqlite3 permissions correct.",
                ))
        except (OSError, KeyError):
            report.checks.append(DiagnosticCheck(
                name="Database (SQLite)",
                status=DiagnosticStatus.WARNING,
                message="Could not inspect db.sqlite3 permissions.",
            ))

    def _check_static_files(self, dc: DomainConfig, report: DiagnosticReport) -> None:
        """Check if collectstatic has been run."""
        candidates = ["staticfiles", "static"]
        for name in candidates:
            static_dir = dc.web_dir / name
            if self._executor.file_exists(static_dir) and any(static_dir.iterdir()):
                report.checks.append(DiagnosticCheck(
                    name="Static Files",
                    status=DiagnosticStatus.OK,
                    message=f"Static files found in {static_dir.name}/",
                ))
                return

        report.checks.append(DiagnosticCheck(
            name="Static Files",
            status=DiagnosticStatus.WARNING,
            message="No static files found — Django Admin will have no styling.",
            suggestion="cd {web_dir} && source venv/bin/activate && "
                       "python manage.py collectstatic --noinput".format(web_dir=dc.web_dir),
        ))

    def _check_nginx_template(self, dc: DomainConfig, report: DiagnosticReport) -> None:
        """Check if NGINX config for this domain points to the correct socket."""
        nginx_conf = Path(f"/home/{dc.user}/conf/web/{dc.domain}/nginx.conf")

        if not self._executor.file_exists(nginx_conf):
            report.checks.append(DiagnosticCheck(
                name="NGINX Configuration",
                status=DiagnosticStatus.WARNING,
                message="NGINX domain config not found — template may not be applied.",
                suggestion=f"sudo v-rebuild-web-domain {dc.user} {dc.domain} yes",
            ))
            return

        try:
            content = nginx_conf.read_text(encoding="utf-8", errors="replace")
            expected_socket = str(dc.socket_path)
            if expected_socket in content:
                report.checks.append(DiagnosticCheck(
                    name="NGINX Configuration",
                    status=DiagnosticStatus.OK,
                    message="NGINX config points to the correct socket path.",
                ))
            else:
                report.checks.append(DiagnosticCheck(
                    name="NGINX Configuration",
                    status=DiagnosticStatus.CRITICAL,
                    message="NGINX config does NOT point to the expected socket!",
                    suggestion=f"sudo v-rebuild-web-domain {dc.user} {dc.domain} yes && "
                               "sudo systemctl restart nginx",
                ))
        except OSError:
            report.checks.append(DiagnosticCheck(
                name="NGINX Configuration",
                status=DiagnosticStatus.WARNING,
                message="Could not read NGINX configuration.",
            ))

    def _check_socket_response(self, dc: DomainConfig, report: DiagnosticReport) -> None:
        """Try to get an HTTP response through the unix socket."""
        sock = dc.socket_path
        if not self._executor.file_exists(sock):
            return  # Already reported in _check_socket

        rc, stdout, _ = self._executor.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' "
            f"--unix-socket {sock} http://localhost/ --max-time 5",
            check=False,
        )
        if rc == 0 and stdout.strip("'\"") in ("200", "301", "302", "403"):
            report.checks.append(DiagnosticCheck(
                name="Socket Response",
                status=DiagnosticStatus.OK,
                message=f"Socket responds with HTTP {stdout.strip(chr(39))}.",
            ))
        else:
            report.checks.append(DiagnosticCheck(
                name="Socket Response",
                status=DiagnosticStatus.WARNING,
                message=f"Socket did not respond as expected (rc={rc}, response={stdout}).",
                suggestion=f"journalctl -u {dc.service_name} -n 20",
            ))


# ---------------------------------------------------------------------------
# Pretty-printer for terminal output
# ---------------------------------------------------------------------------

def print_report(report: DiagnosticReport) -> None:
    """Print a colour-coded diagnostic report to the terminal."""
    RESET = "\033[0m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"

    dc = report.domain_config
    print(f"\n{BOLD}╔══════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║  Deployment Doctor — {dc.domain:<33}║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════════════════════╝{RESET}\n")

    status_icons = {
        DiagnosticStatus.OK: f"{GREEN}✔{RESET}",
        DiagnosticStatus.WARNING: f"{YELLOW}⚠{RESET}",
        DiagnosticStatus.CRITICAL: f"{RED}✘{RESET}",
    }

    for check in report.checks:
        icon = status_icons.get(check.status, "?")
        print(f"  {icon}  {BOLD}{check.name}{RESET}: {check.message}")
        if check.suggestion:
            print(f"      └─ suggestion: {check.suggestion}")

    print()
    if report.is_healthy:
        print(f"  {GREEN}{BOLD}All checks passed! Your deployment is healthy.{RESET}\n")
    else:
        c = report.critical_count
        w = report.warning_count
        parts = []
        if c:
            parts.append(f"{RED}{c} critical{RESET}")
        if w:
            parts.append(f"{YELLOW}{w} warning(s){RESET}")
        print(f"  Summary: {', '.join(parts)}\n")
