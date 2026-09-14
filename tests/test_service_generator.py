# -*- coding: utf-8 -*-
"""
Unit tests for ``core.service_generator.SystemdServiceGenerator``.

Validates that the generated systemd service content includes:
- Correct WSGI module reference
- ``--umask 007`` flag
- Dynamic worker count
- EnvironmentFile for .env projects
- Security hardening directives
"""

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.models import (
    DatabaseEngine,
    DjangoProjectInfo,
    DomainConfig,
    ProjectLayout,
    ServiceConfig,
)
from core.service_generator import SystemdServiceGenerator


class TestSystemdServiceGenerator(unittest.TestCase):
    """Test suite for the systemd service generator."""

    def setUp(self) -> None:
        self.generator = SystemdServiceGenerator()
        self.dc = DomainConfig(domain="example.com", user="amin")

    def _make_project_info(self, **kwargs) -> DjangoProjectInfo:
        defaults = dict(
            layout=ProjectLayout.MODULAR,
            wsgi_module="config.wsgi:application",
            venv_path=Path("/home/amin/web/example.com/public_html/venv"),
            settings_module="config.settings",
            static_root_name="staticfiles",
            database_engine=DatabaseEngine.SQLITE,
            has_dot_env=False,
            has_requirements=True,
        )
        defaults.update(kwargs)
        return DjangoProjectInfo(**defaults)

    # ──────────────────────────────────────────────────────────────────
    # Content validation
    # ──────────────────────────────────────────────────────────────────

    def test_contains_wsgi_module(self) -> None:
        """Output should contain the correct WSGI module."""
        pi = self._make_project_info()
        config = ServiceConfig(domain_config=self.dc, project_info=pi)
        content = self.generator.generate(config)
        self.assertIn("config.wsgi:application", content)

    def test_contains_umask(self) -> None:
        """Output must include --umask 007."""
        pi = self._make_project_info()
        config = ServiceConfig(domain_config=self.dc, project_info=pi)
        content = self.generator.generate(config)
        self.assertIn("--umask 007", content)

    def test_contains_protect_system(self) -> None:
        """Output should include systemd security hardening."""
        pi = self._make_project_info()
        config = ServiceConfig(domain_config=self.dc, project_info=pi)
        content = self.generator.generate(config)
        self.assertIn("ProtectSystem=full", content)
        self.assertIn("PrivateTmp=true", content)
        self.assertIn("NoNewPrivileges=true", content)

    def test_dynamic_worker_count(self) -> None:
        """Workers should be (2 * CPU) + 1 when not specified."""
        pi = self._make_project_info()
        config = ServiceConfig(domain_config=self.dc, project_info=pi)
        expected_workers = (2 * (os.cpu_count() or 1)) + 1
        self.assertEqual(config.workers, expected_workers)
        content = self.generator.generate(config)
        self.assertIn(f"--workers {expected_workers}", content)

    def test_custom_worker_count(self) -> None:
        """Explicit worker count should override dynamic calculation."""
        pi = self._make_project_info()
        config = ServiceConfig(domain_config=self.dc, project_info=pi, workers=4)
        self.assertEqual(config.workers, 4)
        content = self.generator.generate(config)
        self.assertIn("--workers 4", content)

    def test_env_file_included_when_present(self) -> None:
        """EnvironmentFile should be set if .env exists."""
        pi = self._make_project_info(has_dot_env=True)
        config = ServiceConfig(domain_config=self.dc, project_info=pi)
        content = self.generator.generate(config)
        self.assertIn("EnvironmentFile=", content)

    def test_env_file_commented_when_absent(self) -> None:
        """EnvironmentFile should be commented out if .env is missing."""
        pi = self._make_project_info(has_dot_env=False)
        config = ServiceConfig(domain_config=self.dc, project_info=pi)
        content = self.generator.generate(config)
        self.assertIn("# No .env found", content)
        self.assertNotIn("EnvironmentFile=", content)

    def test_traditional_layout_wsgi(self) -> None:
        """Traditional layout should use <project>.wsgi:application."""
        pi = self._make_project_info(
            layout=ProjectLayout.TRADITIONAL,
            wsgi_module="zamzam.wsgi:application",
        )
        config = ServiceConfig(domain_config=self.dc, project_info=pi)
        content = self.generator.generate(config)
        self.assertIn("zamzam.wsgi:application", content)

    def test_socket_path_in_output(self) -> None:
        """Socket path should match the canonical path from DomainConfig."""
        pi = self._make_project_info()
        config = ServiceConfig(domain_config=self.dc, project_info=pi)
        content = self.generator.generate(config)
        self.assertIn(str(self.dc.socket_path), content)

    def test_domain_in_description(self) -> None:
        """Service description should include the domain name."""
        pi = self._make_project_info()
        config = ServiceConfig(domain_config=self.dc, project_info=pi)
        content = self.generator.generate(config)
        self.assertIn("example.com", content)

    def test_correct_user_and_group(self) -> None:
        """User and Group should be correctly set."""
        pi = self._make_project_info()
        config = ServiceConfig(domain_config=self.dc, project_info=pi)
        content = self.generator.generate(config)
        self.assertIn("User=amin", content)
        self.assertIn("Group=www-data", content)


if __name__ == "__main__":
    unittest.main()
