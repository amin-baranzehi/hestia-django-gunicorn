# -*- coding: utf-8 -*-
"""
NGINX template manager for HestiaCP.

**Single Responsibility:** Install, validate, and manage the custom NGINX
proxy templates that HestiaCP uses to route traffic to the Gunicorn socket.
"""

from __future__ import annotations

from pathlib import Path

from core.interfaces import INginxManager, ISystemExecutor
from core.models import HESTIA_TEMPLATE_DIR, TEMPLATE_NAME, DomainConfig


class HestiaNginxManager(INginxManager):
    """Manages NGINX template deployment for HestiaCP."""

    def __init__(self, executor: ISystemExecutor) -> None:
        self._executor = executor

    @property
    def tpl_dest(self) -> Path:
        return HESTIA_TEMPLATE_DIR / f"{TEMPLATE_NAME}.tpl"

    @property
    def stpl_dest(self) -> Path:
        return HESTIA_TEMPLATE_DIR / f"{TEMPLATE_NAME}.stpl"

    def install_templates(self, tpl_source: Path, stpl_source: Path) -> None:
        """Copy templates to the HestiaCP template directory and set permissions."""
        dest_dirs = [HESTIA_TEMPLATE_DIR]
        php_fpm_dir = HESTIA_TEMPLATE_DIR / "php-fpm"
        if self._executor.file_exists(php_fpm_dir):
            dest_dirs.append(php_fpm_dir)

        for dest_dir in dest_dirs:
            for src, name in [(tpl_source, f"{TEMPLATE_NAME}.tpl"), (stpl_source, f"{TEMPLATE_NAME}.stpl")]:
                if not self._executor.file_exists(src):
                    raise FileNotFoundError(f"Template source not found: {src}")

                content = src.read_text(encoding="utf-8")
                dst = dest_dir / name
                self._executor.write_file(dst, content, mode=0o644)
                self._executor.run(f"chown root:root {dst}")

    def rebuild_domain(self, domain_config: DomainConfig) -> None:
        """Force-rebuild the NGINX configuration for a domain and restart."""
        dc = domain_config
        self._executor.run(
            f"v-rebuild-web-domain {dc.user} {dc.domain} yes",
            check=False,
        )
        self._executor.run("systemctl restart nginx", check=False)

    def is_template_installed(self) -> bool:
        """Check if both template files exist in the HestiaCP directory."""
        return (
            self._executor.file_exists(self.tpl_dest)
            and self._executor.file_exists(self.stpl_dest)
        )
