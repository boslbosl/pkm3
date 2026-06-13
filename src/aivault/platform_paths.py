"""Cross-OS home-directory resolution for discovery (ARCHITECTURE §8a).

Adapters never hard-code ``$HOME``. They ask this layer for candidate home
directories per OS context; ``--os-scope`` selects direction:

    native  -> the current user's home on the current OS
    windows -> Windows user profiles (C:\\Users\\* / /mnt/<drive>/Users/*)
    wsl     -> WSL distro homes (/home/* / \\\\wsl.localhost\\<distro>\\home\\*)
    all     -> union of the above

Everything degrades gracefully: unreachable roots simply contribute nothing.
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path

OS_SCOPES = ("native", "windows", "wsl", "all")


@dataclass(frozen=True)
class HomeDir:
    path: Path
    os_context: str  # native | windows | wsl


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    rel = platform.release().lower()
    return "microsoft" in rel or "wsl" in rel


def _is_windows() -> bool:
    return os.name == "nt"


def current_os_context() -> str:
    if _is_windows():
        return "windows"
    if _is_wsl():
        return "wsl"
    return "native"


# --- enumeration helpers ---------------------------------------------------

def _windows_user_homes() -> list[HomeDir]:
    homes: list[HomeDir] = []
    if _is_windows():
        users = Path("C:/Users")
        if users.exists():
            homes += [HomeDir(p, "windows") for p in users.iterdir() if p.is_dir()]
    else:
        # from WSL/Linux, Windows drives are mounted under /mnt/<letter>
        mnt = Path("/mnt")
        if mnt.exists():
            for drive in mnt.iterdir():
                users = drive / "Users"
                try:
                    if users.is_dir():
                        homes += [HomeDir(p, "windows") for p in users.iterdir() if p.is_dir()]
                except (PermissionError, OSError):
                    continue
    return homes


def _wsl_distro_homes() -> list[HomeDir]:
    homes: list[HomeDir] = []
    if _is_windows():
        # WSL distros are reachable via \\wsl.localhost\<distro> (and legacy \\wsl$)
        for root in (Path(r"\\wsl.localhost"), Path(r"\\wsl$")):
            try:
                if not root.exists():
                    continue
                for distro in root.iterdir():
                    home = distro / "home"
                    if home.is_dir():
                        homes += [HomeDir(p, "wsl") for p in home.iterdir() if p.is_dir()]
            except (PermissionError, OSError):
                continue
    else:
        # already inside a Linux/WSL distro
        home = Path("/home")
        if home.is_dir():
            homes += [HomeDir(p, "wsl") for p in home.iterdir() if p.is_dir()]
    return homes


def home_dirs(os_scope: str = "native") -> list[HomeDir]:
    """Return candidate home directories for the requested scope."""
    if os_scope not in OS_SCOPES:
        raise ValueError(f"Invalid os-scope '{os_scope}'. Allowed: {', '.join(OS_SCOPES)}")

    result: list[HomeDir] = []
    if os_scope in ("native", "all"):
        result.append(HomeDir(Path.home(), current_os_context()))
    if os_scope in ("windows", "all"):
        result += _windows_user_homes()
    if os_scope in ("wsl", "all"):
        result += _wsl_distro_homes()

    # de-duplicate by resolved path, keep first os_context seen
    seen: set[str] = set()
    deduped: list[HomeDir] = []
    for h in result:
        key = str(h.path)
        if key not in seen:
            seen.add(key)
            deduped.append(h)
    return deduped


def infer_os_context(path: str | os.PathLike | None) -> str:
    """Best-effort OS context for a single imported file path."""
    if not path:
        return current_os_context()
    p = str(path).replace("\\", "/").lower()
    if p.startswith("//wsl.localhost") or p.startswith("//wsl$"):
        return "wsl"
    if p.startswith("/mnt/") and "/users/" in p:
        return "windows"
    if len(p) >= 2 and p[1] == ":":  # e.g. c:/users/...
        return "windows"
    return current_os_context()
