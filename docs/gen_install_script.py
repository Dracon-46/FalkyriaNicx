"""Publish the canonical install scripts into the built docs site.

Copies the installers to the site root as ``install.sh`` (Linux / macOS /
WSL2) and ``install.ps1`` (native Windows), so any build of the docs ships
the same scripts the one-liners fetch from the repository::

    https://raw.githubusercontent.com/Dracon-46/FalkyriaNicx/main/scripts/install/install.sh
    https://raw.githubusercontent.com/Dracon-46/FalkyriaNicx/main/deploy/windows/install.ps1

Single source of truth: the scripts live under ``scripts/install/`` and
``deploy/windows/`` (also bundled into the wheel as ``_install_scripts/``).
This copies them verbatim into the built site on every ``mkdocs build``,
so the published copies can never drift from the canonical ones.
"""

from pathlib import Path

import mkdocs_gen_files

# (source path, published URL path)
_SCRIPTS = [
    (Path("scripts/install/install.sh"), "install.sh"),
    (Path("deploy/windows/install.ps1"), "install.ps1"),
]

for src, dest in _SCRIPTS:
    with mkdocs_gen_files.open(dest, "wb") as out:
        out.write(src.read_bytes())
