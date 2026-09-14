#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HestiaCP Django-Gunicorn Deployment CLI.

A clean, modular command-line interface that orchestrates all deployment,
repair, and diagnostic operations.

Usage:
    python3 cli.py setup   <domain> <user> [project]
    python3 cli.py repair  <domain> <user>
    python3 cli.py doctor  <domain> <user>
    python3 cli.py install-templates
    python3 cli.py status  <domain>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path so ``core`` can be imported
# regardless of where the script is invoked from.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.detector import DjangoProjectDetector
from core.doctor import DeploymentDoctor, print_report
from core.executor import LinuxExecutor
from core.migrator import ProjectMigrator
from core.models import DomainConfig, ServiceConfig
from core.nginx_manager import HestiaNginxManager
from core.service_generator import SystemdServiceGenerator


# ──────────────────────────────────────────────────────────────────────────
# ANSI helpers
# ──────────────────────────────────────────────────────────────────────────
RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
CYAN = "\033[96m"


def info(msg: str) -> None:
    print(f"  {CYAN}→{RESET} {msg}")


def success(msg: str) -> None:
    print(f"  {GREEN}✔{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}")


def error(msg: str) -> None:
    print(f"  {RED}✘{RESET} {msg}")


def banner() -> None:
    print(f"""
{BOLD}┌──────────────────────────────────────────────────────────┐
│  HestiaCP + Django + Gunicorn  —  Deployment Engine      │
│  Prepared by MohammadAmin Baranzehi (amin.baranzehi.com) │
└──────────────────────────────────────────────────────────┘{RESET}
""")


# ──────────────────────────────────────────────────────────────────────────
# Shared factory
# ──────────────────────────────────────────────────────────────────────────
def _build_components():
    """Instantiate shared components with dependency injection."""
    executor = LinuxExecutor()
    detector = DjangoProjectDetector()
    generator = SystemdServiceGenerator()
    nginx_mgr = HestiaNginxManager(executor)
    migrator = ProjectMigrator(executor, detector, generator)
    doctor = DeploymentDoctor(executor)
    return executor, detector, generator, nginx_mgr, migrator, doctor


# ──────────────────────────────────────────────────────────────────────────
# Sub-command handlers
# ──────────────────────────────────────────────────────────────────────────
def cmd_setup(args: argparse.Namespace) -> int:
    """Deploy a new Django project on HestiaCP."""
    banner()
    executor, detector, generator, nginx_mgr, _, doctor = _build_components()

    dc = DomainConfig(domain=args.domain, user=args.user)
    info(f"Domain : {dc.domain}")
    info(f"User   : {dc.user}")
    info(f"Web dir: {dc.web_dir}")
    print()

    # 1. Detect project
    info("Detecting Django project structure...")
    project_info = detector.detect(dc.web_dir, project_hint=args.project)

    if not project_info.is_valid:
        error("Project detection failed:")
        for err in project_info.errors:
            error(f"  {err}")
        return 1

    success(f"Layout : {project_info.layout.name}")
    success(f"WSGI   : {project_info.wsgi_module}")
    success(f"Venv   : {project_info.venv_path or 'NOT FOUND'}")
    success(f"Static : {project_info.static_root_name}")
    success(f"DB     : {project_info.database_engine.name}")
    if project_info.has_dot_env:
        success(".env file detected — will load via EnvironmentFile")
    print()

    # 2. Install templates if not present
    if not nginx_mgr.is_template_installed():
        info("Installing NGINX templates...")
        tpl_dir = PROJECT_ROOT / "templates"
        nginx_mgr.install_templates(
            tpl_dir / "django-gunicorn.tpl",
            tpl_dir / "django-gunicorn.stpl",
        )
        success("NGINX templates installed.")
    else:
        success("NGINX templates already installed.")

    # 3. Generate service file
    info("Generating systemd service...")
    service_config = ServiceConfig(domain_config=dc, project_info=project_info)
    content = generator.generate(service_config)

    # Backup if exists
    if executor.file_exists(dc.service_file):
        bak = executor.backup_file(dc.service_file)
        warn(f"Existing service backed up to: {bak}")

    executor.write_file(dc.service_file, content, mode=0o644)
    success(f"Service file: {dc.service_file}")
    success(f"Workers: {service_config.workers} | Threads: {service_config.threads} | umask: {service_config.umask}")
    print()

    # 4. Enable and start
    info("Starting Gunicorn service...")
    executor.run("systemctl daemon-reload")
    executor.run(f"systemctl enable {dc.service_name}", check=False)
    executor.run(f"systemctl restart {dc.service_name}", check=False)

    # 5. Rebuild NGINX
    info("Rebuilding NGINX for domain...")
    nginx_mgr.rebuild_domain(dc)
    print()

    # 6. Fix permissions
    info("Fixing file permissions...")
    db_file = dc.web_dir / "db.sqlite3"
    if executor.file_exists(db_file):
        executor.run(f"chown {dc.user}:www-data {db_file} && chmod 664 {db_file}", check=False)
        success("db.sqlite3 permissions fixed.")

    static_dir = dc.web_dir / project_info.static_root_name
    if executor.file_exists(static_dir):
        executor.run(f"chown -R {dc.user}:www-data {static_dir}", check=False)
        success(f"{project_info.static_root_name}/ ownership fixed.")
    print()

    # 7. Run doctor
    info("Running health checks...")
    report = doctor.diagnose(dc)
    print_report(report)

    return 0 if report.is_healthy else 1


def cmd_repair(args: argparse.Namespace) -> int:
    """Repair / upgrade a previously deployed project."""
    banner()
    executor, detector, generator, nginx_mgr, migrator, _ = _build_components()

    dc = DomainConfig(domain=args.domain, user=args.user)
    info(f"Repairing deployment for: {dc.domain}")
    print()

    if not migrator.needs_migration(dc):
        success("No migration needed — deployment looks up-to-date.")
        return 0

    # Update templates first
    info("Updating NGINX templates...")
    tpl_dir = PROJECT_ROOT / "templates"
    nginx_mgr.install_templates(
        tpl_dir / "django-gunicorn.tpl",
        tpl_dir / "django-gunicorn.stpl",
    )
    success("NGINX templates updated.")

    # Run migration
    info("Migrating service configuration...")
    report = migrator.migrate(dc)

    # Rebuild NGINX
    info("Rebuilding NGINX configuration...")
    nginx_mgr.rebuild_domain(dc)

    print_report(report)
    return 0 if report.is_healthy else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    """Run diagnostics on a deployment."""
    banner()
    _, _, _, _, _, doctor = _build_components()

    dc = DomainConfig(domain=args.domain, user=args.user)
    report = doctor.diagnose(dc)
    print_report(report)

    return 0 if report.is_healthy else 1


def cmd_install_templates(args: argparse.Namespace) -> int:
    """Install NGINX templates to HestiaCP."""
    banner()
    executor, _, _, nginx_mgr, _, _ = _build_components()

    tpl_dir = PROJECT_ROOT / "templates"
    info("Installing NGINX templates...")
    nginx_mgr.install_templates(
        tpl_dir / "django-gunicorn.tpl",
        tpl_dir / "django-gunicorn.stpl",
    )
    success("Templates installed to HestiaCP successfully.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show status of a Gunicorn service."""
    banner()
    executor, _, _, _, _, _ = _build_components()

    service_name = f"gunicorn-{args.domain}"
    rc, stdout, stderr = executor.run(
        f"systemctl status {service_name} --no-pager -l",
        check=False,
    )
    print(stdout)
    if stderr:
        print(stderr)
    return rc


def cmd_update(args: argparse.Namespace) -> int:
    """Self-update the deployment engine and refresh templates."""
    banner()
    executor, _, _, nginx_mgr, _, _ = _build_components()

    info("Updating HestiaCP Django-Gunicorn Deployment Engine...")

    # 1. Pull latest from git if repository
    git_dir = PROJECT_ROOT / ".git"
    if git_dir.exists():
        info("Pulling latest updates from git...")
        rc, out, err = executor.run(f"git -C {PROJECT_ROOT} pull --ff-only", check=False)
        if rc == 0:
            success("Repository updated to latest commit.")
        else:
            rc2, out2, err2 = executor.run(f"git -C {PROJECT_ROOT} pull", check=False)
            if rc2 == 0:
                success("Repository updated.")
            else:
                warn(f"Could not pull updates from git: {err or err2}")

    # 2. Update templates in HestiaCP
    tpl_dir = PROJECT_ROOT / "templates"
    info("Updating NGINX templates...")
    nginx_mgr.install_templates(
        tpl_dir / "django-gunicorn.tpl",
        tpl_dir / "django-gunicorn.stpl",
    )
    success("NGINX templates updated in HestiaCP.")

    # 3. Ensure global symlink
    cmd_install(args)

    success("Update completed successfully! 'hdg' is up to date.")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """Install hdg globally to /usr/local/bin."""
    executor, _, _, nginx_mgr, _, _ = _build_components()
    bin_dir = Path("/usr/local/bin")
    hdg_script = PROJECT_ROOT / "hdg"

    if bin_dir.exists() and hdg_script.exists():
        for link_name in ["hdg", "v-django", "hestia-django"]:
            target = bin_dir / link_name
            executor.run(f"ln -sf {hdg_script} {target}", check=False)
        executor.run(f"chmod +x {hdg_script}", check=False)
        success("Global commands installed: 'hdg', 'v-django', 'hestia-django'")
    return 0


# ──────────────────────────────────────────────────────────────────────────
# Argument parser
# ──────────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hdg",
        description="HestiaCP + Django + Gunicorn Deployment Engine (hdg)",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # setup
    p_setup = sub.add_parser("setup", help="Deploy a new Django project")
    p_setup.add_argument("domain", help="Domain name (e.g. example.com)")
    p_setup.add_argument("user", help="HestiaCP system user")
    p_setup.add_argument("project", nargs="?", default=None,
                         help="Project name (auto-detected if omitted)")

    # repair
    p_repair = sub.add_parser("repair", help="Repair a previously deployed project")
    p_repair.add_argument("domain", help="Domain name")
    p_repair.add_argument("user", help="HestiaCP system user")

    # doctor
    p_doctor = sub.add_parser("doctor", help="Run deployment health checks")
    p_doctor.add_argument("domain", help="Domain name")
    p_doctor.add_argument("user", help="HestiaCP system user")

    # install-templates
    sub.add_parser("install-templates", help="Install NGINX templates to HestiaCP")

    # update
    sub.add_parser("update", help="Update hdg and NGINX templates to latest version")

    # install
    sub.add_parser("install", help="Install global symlinks to /usr/local/bin")

    # status
    p_status = sub.add_parser("status", help="Show Gunicorn service status")
    p_status.add_argument("domain", help="Domain name")

    return parser


def main() -> int:
    # Convenience shorthand: if first arg is a domain or not a command, default to 'setup'
    known_commands = {
        "setup", "repair", "doctor", "install-templates",
        "update", "install", "status", "-h", "--help",
    }
    if len(sys.argv) > 1 and sys.argv[1] not in known_commands:
        sys.argv.insert(1, "setup")

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        "setup": cmd_setup,
        "repair": cmd_repair,
        "doctor": cmd_doctor,
        "install-templates": cmd_install_templates,
        "update": cmd_update,
        "install": cmd_install,
        "status": cmd_status,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except Exception as exc:
        error(f"Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
