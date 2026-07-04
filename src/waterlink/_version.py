"""Version metadata for waterlink.

This module is the single source of truth for the package version. It is
imported by ``waterlink.__init__`` and read by build tooling, so keep it
free of any other imports to avoid circular dependencies.
"""

from __future__ import annotations

__version__ = "1.0.7"
__version_info__: tuple[int, int, int, str, int] = (1, 0, 7, "final", 0)
