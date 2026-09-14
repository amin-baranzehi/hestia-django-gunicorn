# -*- coding: utf-8 -*-
"""
Unit tests for ``core.detector.DjangoProjectDetector``.

Tests both modern modular layout (``config/wsgi.py``) and traditional
layout (``<project>/wsgi.py``) to ensure the auto-detection engine works
correctly for all Django project structures.
"""

import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.detector import DjangoProjectDetector
from core.models import DatabaseEngine, ProjectLayout


class TestDjangoProjectDetector(unittest.TestCase):
    """Test suite for the Django project detector."""

    def setUp(self) -> None:
        self.detector = DjangoProjectDetector()

    # ──────────────────────────────────────────────────────────────────
    # Layout detection
    # ──────────────────────────────────────────────────────────────────

    def test_modular_layout_detected(self) -> None:
        """config/wsgi.py should be detected as MODULAR layout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "config").mkdir()
            (web_dir / "config" / "wsgi.py").write_text(
                'import os\n'
                'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")\n'
                'from django.core.wsgi import get_wsgi_application\n'
                'application = get_wsgi_application()\n'
            )
            (web_dir / "config" / "settings.py").write_text(
                'STATIC_ROOT = BASE_DIR / "staticfiles"\n'
                'DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3"}}\n'
            )
            # Create a fake venv
            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("#!/usr/bin/env python3\n")

            info = self.detector.detect(web_dir)

            self.assertEqual(info.layout, ProjectLayout.MODULAR)
            self.assertEqual(info.wsgi_module, "config.wsgi:application")
            self.assertEqual(info.settings_module, "config.settings")
            self.assertTrue(info.is_valid)

    def test_traditional_layout_detected(self) -> None:
        """<project>/wsgi.py should be detected as TRADITIONAL layout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "myproject").mkdir()
            (web_dir / "myproject" / "wsgi.py").write_text(
                'import os\n'
                'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")\n'
                'from django.core.wsgi import get_wsgi_application\n'
                'application = get_wsgi_application()\n'
            )
            (web_dir / "myproject" / "settings.py").write_text(
                'STATIC_ROOT = BASE_DIR / "static"\n'
                'DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql"}}\n'
            )
            # Create a fake venv
            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("#!/usr/bin/env python3\n")

            info = self.detector.detect(web_dir)

            self.assertEqual(info.layout, ProjectLayout.TRADITIONAL)
            self.assertEqual(info.wsgi_module, "myproject.wsgi:application")
            self.assertTrue(info.is_valid)

    def test_traditional_layout_with_hint(self) -> None:
        """When a project hint is provided, it should be preferred."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "zamzam").mkdir()
            (web_dir / "zamzam" / "wsgi.py").write_text("application = None\n")
            (web_dir / "zamzam" / "settings.py").write_text("")
            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("")

            info = self.detector.detect(web_dir, project_hint="zamzam")

            self.assertEqual(info.layout, ProjectLayout.TRADITIONAL)
            self.assertEqual(info.wsgi_module, "zamzam.wsgi:application")

    def test_flat_layout_detected(self) -> None:
        """wsgi.py at root should be detected as FLAT layout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "wsgi.py").write_text(
                'import os\n'
                'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")\n'
                'from django.core.wsgi import get_wsgi_application\n'
                'application = get_wsgi_application()\n'
            )
            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("")

            info = self.detector.detect(web_dir)

            self.assertEqual(info.layout, ProjectLayout.FLAT)
            self.assertEqual(info.wsgi_module, "wsgi:application")

    def test_no_wsgi_returns_unknown(self) -> None:
        """Missing wsgi.py should result in UNKNOWN layout with errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            info = self.detector.detect(web_dir)

            self.assertEqual(info.layout, ProjectLayout.UNKNOWN)
            self.assertFalse(info.is_valid)
            self.assertTrue(len(info.errors) > 0)

    def test_modular_takes_priority_over_traditional(self) -> None:
        """If both config/wsgi.py and myproject/wsgi.py exist, MODULAR wins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "config").mkdir()
            (web_dir / "config" / "wsgi.py").write_text("application = None\n")
            (web_dir / "config" / "settings.py").write_text("")
            (web_dir / "myproject").mkdir()
            (web_dir / "myproject" / "wsgi.py").write_text("application = None\n")

            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("")

            info = self.detector.detect(web_dir)
            self.assertEqual(info.layout, ProjectLayout.MODULAR)

    # ──────────────────────────────────────────────────────────────────
    # Virtual environment detection
    # ──────────────────────────────────────────────────────────────────

    def test_venv_in_public_html(self) -> None:
        """Should find venv inside public_html."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "config").mkdir()
            (web_dir / "config" / "wsgi.py").write_text("")
            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("")

            info = self.detector.detect(web_dir)
            self.assertIsNotNone(info.venv_path)
            self.assertEqual(info.venv_path.name, "venv")

    def test_dotvenv_detected(self) -> None:
        """Should find .venv as an alternative."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "config").mkdir()
            (web_dir / "config" / "wsgi.py").write_text("")
            venv_bin = web_dir / ".venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("")

            info = self.detector.detect(web_dir)
            self.assertIsNotNone(info.venv_path)
            self.assertEqual(info.venv_path.name, ".venv")

    # ──────────────────────────────────────────────────────────────────
    # Settings parsing
    # ──────────────────────────────────────────────────────────────────

    def test_static_root_extracted(self) -> None:
        """STATIC_ROOT value should be extracted from settings.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "config").mkdir()
            (web_dir / "config" / "wsgi.py").write_text("")
            (web_dir / "config" / "settings.py").write_text(
                "STATIC_ROOT = BASE_DIR / 'my_static_output'\n"
            )
            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("")

            info = self.detector.detect(web_dir)
            self.assertEqual(info.static_root_name, "my_static_output")

    def test_database_engine_sqlite(self) -> None:
        """Should detect SQLite database engine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "config").mkdir()
            (web_dir / "config" / "wsgi.py").write_text("")
            (web_dir / "config" / "settings.py").write_text(
                "DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3'}}\n"
            )
            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("")

            info = self.detector.detect(web_dir)
            self.assertEqual(info.database_engine, DatabaseEngine.SQLITE)

    def test_database_engine_postgresql(self) -> None:
        """Should detect PostgreSQL database engine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "config").mkdir()
            (web_dir / "config" / "wsgi.py").write_text("")
            (web_dir / "config" / "settings.py").write_text(
                "DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql'}}\n"
            )
            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("")

            info = self.detector.detect(web_dir)
            self.assertEqual(info.database_engine, DatabaseEngine.POSTGRESQL)

    # ──────────────────────────────────────────────────────────────────
    # Dot-env and requirements detection
    # ──────────────────────────────────────────────────────────────────

    def test_dotenv_detected(self) -> None:
        """Should detect presence of .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "config").mkdir()
            (web_dir / "config" / "wsgi.py").write_text("")
            (web_dir / ".env").write_text("DEBUG=True\n")
            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("")

            info = self.detector.detect(web_dir)
            self.assertTrue(info.has_dot_env)

    def test_requirements_detected(self) -> None:
        """Should detect presence of requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            web_dir = Path(tmpdir)
            (web_dir / "config").mkdir()
            (web_dir / "config" / "wsgi.py").write_text("")
            (web_dir / "requirements.txt").write_text("django\ngunicorn\n")
            venv_bin = web_dir / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("")

            info = self.detector.detect(web_dir)
            self.assertTrue(info.has_requirements)

    def test_nonexistent_directory(self) -> None:
        """Should handle nonexistent directory gracefully."""
        info = self.detector.detect(Path("/tmp/does_not_exist_xyz"))
        self.assertFalse(info.is_valid)
        self.assertTrue(len(info.errors) > 0)


if __name__ == "__main__":
    unittest.main()
