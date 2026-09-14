# -*- coding: utf-8 -*-
"""
Domain models and value objects for the HestiaCP Django-Gunicorn deployment engine.

These dataclasses serve as the **Single Source of Truth** for all path
conventions, service naming rules, and configuration parameters used across
every module.  Centralising them here eliminates magic strings and satisfies
the DRY principle.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ProjectLayout(Enum):
    """Detected Django project directory layout."""

    MODULAR = auto()       # config/wsgi.py  (clean / modern)
    TRADITIONAL = auto()   # <project>/wsgi.py  (django-admin startproject)
    FLAT = auto()           # wsgi.py at project root (rare but valid)
    UNKNOWN = auto()


class DatabaseEngine(Enum):
    """Database back-end detected in settings."""

    SQLITE = auto()
    POSTGRESQL = auto()
    MYSQL = auto()
    OTHER = auto()
    UNKNOWN = auto()


class DiagnosticStatus(Enum):
    """Result status for a single diagnostic check."""

    OK = auto()
    WARNING = auto()
    CRITICAL = auto()


# ---------------------------------------------------------------------------
# Path & naming conventions  (Single Source of Truth)
# ---------------------------------------------------------------------------

HESTIA_TEMPLATE_DIR = Path("/usr/local/hestia/data/templates/web/nginx")
SYSTEMD_SERVICE_DIR = Path("/etc/systemd/system")
TEMPLATE_NAME = "django-gunicorn"
SOCKET_FILENAME = "gunicorn.sock"
DEFAULT_VENV_CANDIDATES = ("venv", ".venv", "env")
DEFAULT_STATIC_DIR = "staticfiles"


def build_home_dir(user: str) -> Path:
    """Return the HestiaCP home directory for *user*."""
    return Path(f"/home/{user}")


def build_web_dir(user: str, domain: str) -> Path:
    """Return the web-root (``public_html``) for a domain."""
    return build_home_dir(user) / "web" / domain / "public_html"


def build_socket_path(user: str, domain: str) -> Path:
    """Return the canonical unix-socket path."""
    return build_web_dir(user, domain) / SOCKET_FILENAME


def build_service_name(domain: str) -> str:
    """Return the systemd service unit name (without ``.service``)."""
    return f"gunicorn-{domain}"


def build_service_file(domain: str) -> Path:
    """Return the absolute path to the systemd unit file."""
    return SYSTEMD_SERVICE_DIR / f"{build_service_name(domain)}.service"


# ---------------------------------------------------------------------------
# Core data-transfer objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DomainConfig:
    """Immutable value object describing a HestiaCP domain deployment target."""

    domain: str
    user: str

    @property
    def home_dir(self) -> Path:
        return build_home_dir(self.user)

    @property
    def web_dir(self) -> Path:
        return build_web_dir(self.user, self.domain)

    @property
    def socket_path(self) -> Path:
        return build_socket_path(self.user, self.domain)

    @property
    def service_name(self) -> str:
        return build_service_name(self.domain)

    @property
    def service_file(self) -> Path:
        return build_service_file(self.domain)


@dataclass
class DjangoProjectInfo:
    """Result of inspecting the Django project inside ``public_html``."""

    layout: ProjectLayout = ProjectLayout.UNKNOWN
    wsgi_module: str = ""
    venv_path: Optional[Path] = None
    settings_module: str = ""
    static_root_name: str = DEFAULT_STATIC_DIR
    database_engine: DatabaseEngine = DatabaseEngine.UNKNOWN
    has_dot_env: bool = False
    has_requirements: bool = False
    errors: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.layout != ProjectLayout.UNKNOWN and bool(self.wsgi_module)


@dataclass
class ServiceConfig:
    """All parameters needed to render a systemd unit file."""

    domain_config: DomainConfig
    project_info: DjangoProjectInfo
    workers: int = 0
    threads: int = 2
    umask: str = "007"
    log_level: str = "info"
    restart_sec: int = 3

    def __post_init__(self) -> None:
        if self.workers <= 0:
            cpu = os.cpu_count() or 1
            self.workers = (2 * cpu) + 1


@dataclass
class DiagnosticCheck:
    """A single diagnostic check result."""

    name: str
    status: DiagnosticStatus
    message: str
    suggestion: str = ""


@dataclass
class DiagnosticReport:
    """Collection of diagnostic checks for a deployment."""

    domain_config: DomainConfig
    checks: List[DiagnosticCheck] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return all(c.status == DiagnosticStatus.OK for c in self.checks)

    @property
    def critical_count(self) -> int:
        return sum(1 for c in self.checks if c.status == DiagnosticStatus.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.checks if c.status == DiagnosticStatus.WARNING)
