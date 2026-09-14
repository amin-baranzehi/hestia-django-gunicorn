# -*- coding: utf-8 -*-
"""
Smart Django project structure detector.

**Single Responsibility:** Inspect a ``public_html`` directory and produce a
fully populated ``DjangoProjectInfo`` — identifying the WSGI module, virtual
environment, static-file conventions, and database engine.

Supports three layout styles:
  * **Modular** — ``config/wsgi.py``  (clean architecture like ``portfolio``)
  * **Traditional** — ``<project>/wsgi.py``  (``django-admin startproject``)
  * **Flat** — ``wsgi.py`` at the project root (rare but valid)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from core.interfaces import IDjangoDetector
from core.models import (
    DEFAULT_STATIC_DIR,
    DEFAULT_VENV_CANDIDATES,
    DatabaseEngine,
    DjangoProjectInfo,
    ProjectLayout,
)


class DjangoProjectDetector(IDjangoDetector):
    """Concrete detector that inspects the filesystem for Django conventions."""

    # Regex patterns for extracting settings values
    _STATIC_ROOT_RE = re.compile(
        r"""STATIC_ROOT\s*=\s*(?:"""
        r"""BASE_DIR\s*/\s*['"]([^'"]+)['"]"""     # BASE_DIR / 'staticfiles'
        r"""|os\.path\.join\s*\(\s*BASE_DIR\s*,\s*['"]([^'"]+)['"]"""  # os.path.join(...)
        r"""|['"]([^'"]+)['"]"""                    # plain string
        r""")""",
        re.VERBOSE,
    )
    _DB_ENGINE_RE = re.compile(r"""['"]ENGINE['"]\s*:\s*['"]([^'"]+)['"]""")
    _WSGI_APP_RE = re.compile(r"""WSGI_APPLICATION\s*=\s*['"]([^'"]+)['"]""")

    def detect(self, web_dir: Path, project_hint: Optional[str] = None) -> DjangoProjectInfo:
        """Analyse *web_dir* and return a populated ``DjangoProjectInfo``."""
        info = DjangoProjectInfo()

        if not web_dir.is_dir():
            info.errors.append(f"Web directory does not exist: {web_dir}")
            return info

        # --- 1. Detect project layout & WSGI module ---
        self._detect_layout(web_dir, info, project_hint)

        # --- 2. Locate virtualenv ---
        self._detect_venv(web_dir, info)

        # --- 3. Inspect settings.py ---
        self._inspect_settings(web_dir, info)

        # --- 4. Check for .env and requirements.txt ---
        info.has_dot_env = (web_dir / ".env").is_file()
        info.has_requirements = (web_dir / "requirements.txt").is_file()

        return info

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_layout(
        self,
        web_dir: Path,
        info: DjangoProjectInfo,
        project_hint: Optional[str],
    ) -> None:
        """Determine project layout and set ``wsgi_module``."""

        # Priority 1: Modular layout  (config/wsgi.py)
        if (web_dir / "config" / "wsgi.py").is_file():
            info.layout = ProjectLayout.MODULAR
            info.wsgi_module = "config.wsgi:application"
            info.settings_module = "config.settings"
            return

        # Priority 2: Traditional layout  (<project>/wsgi.py)
        if project_hint:
            candidate = web_dir / project_hint / "wsgi.py"
            if candidate.is_file():
                info.layout = ProjectLayout.TRADITIONAL
                info.wsgi_module = f"{project_hint}.wsgi:application"
                info.settings_module = f"{project_hint}.settings"
                return

        # Auto-scan for traditional layout directories
        for child in sorted(web_dir.iterdir()):
            if child.is_dir() and (child / "wsgi.py").is_file():
                name = child.name
                info.layout = ProjectLayout.TRADITIONAL
                info.wsgi_module = f"{name}.wsgi:application"
                info.settings_module = f"{name}.settings"
                return

        # Priority 3: Flat layout  (wsgi.py at root)
        if (web_dir / "wsgi.py").is_file():
            info.layout = ProjectLayout.FLAT
            info.wsgi_module = "wsgi:application"
            # Try to read DJANGO_SETTINGS_MODULE from wsgi.py
            self._extract_settings_from_wsgi(web_dir / "wsgi.py", info)
            return

        info.errors.append(
            "Could not locate wsgi.py — checked config/, <project>/, and root."
        )

    def _detect_venv(self, web_dir: Path, info: DjangoProjectInfo) -> None:
        """Find the first existing virtualenv candidate directory."""
        search_dirs = [web_dir, web_dir.parent]  # public_html, then domain root

        for base in search_dirs:
            for candidate_name in DEFAULT_VENV_CANDIDATES:
                candidate = base / candidate_name
                if (candidate / "bin" / "python").is_file() or \
                   (candidate / "bin" / "python3").is_file():
                    info.venv_path = candidate
                    return

        info.errors.append(
            f"No virtualenv found. Searched for {DEFAULT_VENV_CANDIDATES} "
            f"in {web_dir} and {web_dir.parent}."
        )

    def _inspect_settings(self, web_dir: Path, info: DjangoProjectInfo) -> None:
        """Parse ``settings.py`` for STATIC_ROOT and DATABASE ENGINE."""
        settings_path = self._find_settings_file(web_dir, info)
        if settings_path is None:
            return

        try:
            content = settings_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            info.errors.append(f"Cannot read settings: {exc}")
            return

        # STATIC_ROOT
        match = self._STATIC_ROOT_RE.search(content)
        if match:
            # Pick the first non-None group
            info.static_root_name = next(
                (g for g in match.groups() if g), DEFAULT_STATIC_DIR
            )

        # Database engine
        db_match = self._DB_ENGINE_RE.search(content)
        if db_match:
            engine_str = db_match.group(1).lower()
            if "sqlite" in engine_str:
                info.database_engine = DatabaseEngine.SQLITE
            elif "postgresql" in engine_str or "postgis" in engine_str:
                info.database_engine = DatabaseEngine.POSTGRESQL
            elif "mysql" in engine_str:
                info.database_engine = DatabaseEngine.MYSQL
            else:
                info.database_engine = DatabaseEngine.OTHER

    def _find_settings_file(
        self, web_dir: Path, info: DjangoProjectInfo
    ) -> Optional[Path]:
        """Locate settings.py based on the detected layout."""
        if info.settings_module:
            relative = info.settings_module.replace(".", "/") + ".py"
            candidate = web_dir / relative
            if candidate.is_file():
                return candidate

        # Fallback: search common locations
        for candidate in [
            web_dir / "config" / "settings.py",
            web_dir / "settings.py",
        ]:
            if candidate.is_file():
                return candidate

        # Search any subdirectory
        for child in sorted(web_dir.iterdir()):
            if child.is_dir():
                settings = child / "settings.py"
                if settings.is_file():
                    return settings

        return None

    @staticmethod
    def _extract_settings_from_wsgi(wsgi_path: Path, info: DjangoProjectInfo) -> None:
        """Try to read DJANGO_SETTINGS_MODULE from a flat wsgi.py."""
        try:
            content = wsgi_path.read_text(encoding="utf-8", errors="replace")
            match = re.search(
                r"""os\.environ.*?['"]DJANGO_SETTINGS_MODULE['"]\s*,\s*['"]([^'"]+)['"]""",
                content,
            )
            if match:
                info.settings_module = match.group(1)
        except OSError:
            pass
