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
        for src, dst in [(tpl_source, self.tpl_dest), (stpl_source, self.stpl_dest)]:
            if not self._executor.file_exists(src):
                raise FileNotFoundError(f"Template source not found: {src}")

            content = src.read_text(encoding="utf-8")
            self._executor.write_file(dst, content, mode=0o644)

        # Set ownership to root:root
        self._executor.run(
            f"chown root:root {self.tpl_dest} {self.stpl_dest}"
        )

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
