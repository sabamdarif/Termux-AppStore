# SPDX-License-Identifier: GPL-3.0-or-later
"""4-Layer Hybrid Progress Engine for script execution.

Converts raw script output lines into (fraction, message) pairs
suitable for updating a GTK progress bar.  Layers are checked in
priority order — the first layer that matches wins.

Layer 1: Explicit ``__PROGRESS__`` / ``__PHASE__`` / ``__DONE__`` /
         ``__ERROR__`` tokens emitted by instrumented bash functions.
Layer 2: Tool-specific structured output (dpkg ``pmstatus:``,
         aria2c ``(N%)``, wget ``N%``).
Layer 3: Keyword heuristics (Downloading, Unpacking, Setting up, …).
Layer 4: Time-based heartbeat drift (slow progress so the bar
         never completely freezes).
"""

import re
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# ─── Phase Weight Maps ────────────────────────────────────────────────────────

PHASE_MAPS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "native_install": {
        "script_download": (0.00, 0.08),
        "prepare": (0.08, 0.12),
        "install": (0.12, 0.88),
        "desktop": (0.88, 0.94),
        "finalize": (0.94, 1.00),
    },
    "native_uninstall": {
        "script_download": (0.00, 0.05),
        "prepare": (0.05, 0.10),
        "cleanup": (0.10, 0.92),
        "finalize": (0.92, 1.00),
    },
    "distro_install_repo": {
        "script_download": (0.00, 0.05),
        "prepare": (0.05, 0.12),
        "configure": (0.12, 0.25),
        "install": (0.25, 0.88),
        "desktop": (0.88, 0.95),
        "finalize": (0.95, 1.00),
    },
    "distro_install_download": {
        "script_download": (0.00, 0.05),
        "prepare": (0.05, 0.10),
        "download": (0.10, 0.65),
        "extract": (0.65, 0.82),
        "configure": (0.82, 0.90),
        "desktop": (0.90, 0.96),
        "finalize": (0.96, 1.00),
    },
    "appimage_install": {
        "script_download": (0.00, 0.05),
        "prepare": (0.05, 0.08),
        "download": (0.08, 0.60),
        "extract": (0.60, 0.80),
        "configure": (0.80, 0.88),
        "desktop": (0.88, 0.95),
        "finalize": (0.95, 1.00),
    },
    "uninstall": {
        "script_download": (0.00, 0.08),
        "prepare": (0.08, 0.15),
        "cleanup": (0.15, 0.90),
        "finalize": (0.90, 1.00),
    },
    # Default map for unknown operation types
    "default": {
        "script_download": (0.00, 0.05),
        "prepare": (0.05, 0.15),
        "install": (0.15, 0.90),
        "finalize": (0.90, 1.00),
    },
}

# ─── Heuristic Keyword Rules ──────────────────────────────────────────────────

KEYWORD_RULES = [
    # (regex pattern, phase_hint, bump_pct)
    (re.compile(r"^(Downloading|Fetching|Get:[0-9])", re.I), "download", 2),
    (re.compile(r"^(Unpacking|Extracting)", re.I), "extract", 3),
    (re.compile(r"^(Setting up|Configuring|Processing)", re.I), "configure", 5),
    (re.compile(r"^(Removing|Purging|Deleting)", re.I), "cleanup", 5),
    (re.compile(r"^(Building|Compiling)", re.I), "install", 2),
    (re.compile(r"Creating desktop entry", re.I), "desktop", 20),
    (re.compile(r"(Successfully installed|Done\.?$)", re.I), "finalize", 95),
    (re.compile(r"^(Installing|install_and_check)", re.I), "install", 3),
]

# ─── Tool-specific structured output patterns ─────────────────────────────────

RE_DPKG_PMSTATUS = re.compile(r"^(pmstatus|dlstatus|pmerror):([^:]+):([0-9.]+):(.+)$")
RE_ARIA2C = re.compile(r"\(([0-9]+)%\)")
RE_WGET = re.compile(r"\s+([0-9]+)%\s+\S+\s+")

# ─── Human-readable phase labels for UI ───────────────────────────────────────

PHASE_LABELS = {
    "script_download": "Preparing",
    "prepare": "Preparing",
    "download": "Downloading",
    "extract": "Extracting",
    "install": "Installing",
    "configure": "Configuring",
    "desktop": "Creating shortcut",
    "cleanup": "Cleaning up",
    "finalize": "Finishing up",
}

# Token prefixes used by the explicit progress protocol
PROGRESS_TOKENS = ("__PROGRESS__", "__PHASE__", "__DONE__", "__ERROR__")


# ─── ProgressEngine ───────────────────────────────────────────────────────────


@dataclass
class ProgressEngine:
    """Converts a raw stream of script output lines into
    ``(fraction, message)`` pairs suitable for a GTK progress bar.

    Attributes:
        operation:  ``"install"`` | ``"uninstall"`` | ``"update"``
        app_type:   ``"native"`` | ``"distro"`` | ``"appimage"``
        script_type: ``"repo"`` | ``"download"`` | ``""`` (auto-detect)
    """

    operation: str
    app_type: str = "native"
    script_type: str = ""

    current_fraction: float = field(default=0.0, init=False)
    current_message: str = field(default="Starting...", init=False)
    current_phase: str = field(default="script_download", init=False)
    _phase_map: dict = field(default=None, init=False)
    _last_token_time: float = field(default_factory=time.time, init=False)
    is_done: bool = field(default=False, init=False)
    has_error: bool = field(default=False, init=False)

    def __post_init__(self):
        self._phase_map = self._select_phase_map()
        start, _ = self._phase_map.get("script_download", (0.0, 0.08))
        self.current_fraction = start
        self.current_message = "Downloading install script..."

    def _select_phase_map(self) -> dict:
        op = self.operation.lower()
        atyp = self.app_type.lower()
        stype = self.script_type.lower()

        if "uninstall" in op:
            return PHASE_MAPS["uninstall"]
        if atyp == "appimage" or "appimage" in stype:
            return PHASE_MAPS["appimage_install"]
        if atyp == "distro":
            if "download" in stype or "extract" in stype:
                return PHASE_MAPS["distro_install_download"]
            return PHASE_MAPS["distro_install_repo"]
        if atyp == "native":
            return PHASE_MAPS["native_install"]
        return PHASE_MAPS["default"]

    def _phase_range(self, phase: str) -> Tuple[float, float]:
        return self._phase_map.get(
            phase, (self.current_fraction, self.current_fraction + 0.01)
        )

    def _set_fraction(self, new_fraction: float, message: Optional[str] = None):
        """Set fraction, ensuring it never goes backwards."""
        clamped = max(self.current_fraction, min(1.0, new_fraction))
        self.current_fraction = clamped
        if message:
            self.current_message = message
        self._last_token_time = time.time()

    def _fraction_from_phase_pct(self, phase: str, pct_in_phase: float) -> float:
        """Convert a 0–100 percent within a phase to absolute 0.0–1.0."""
        lo, hi = self._phase_range(phase)
        return lo + (pct_in_phase / 100.0) * (hi - lo)

    def _apply_heuristic_bump(self, phase_hint: str, bump_pct: float):
        """Bump progress by *bump_pct*% of current phase range,
        capped at phase ceiling."""
        lo, hi = self._phase_range(phase_hint)
        bump = (hi - lo) * (bump_pct / 100.0)
        new_f = min(hi - 0.01, self.current_fraction + bump)
        self._set_fraction(new_f)
        self.current_phase = phase_hint

    # ── Public API ────────────────────────────────────────────────────────

    def heartbeat(self):
        """Called by a GTK timeout (~500 ms).  Provides very slow drift
        so the bar never completely freezes.

        Max drift: 0.3 %/s, never past 2 % below phase ceiling.
        Stops drifting if a token arrived in the last 2 seconds.
        """
        if self.is_done or self.has_error:
            return
        elapsed = time.time() - self._last_token_time
        if elapsed < 2.0:
            return  # Recent activity — don't drift
        _, hi = self._phase_range(self.current_phase)
        ceiling = hi - 0.02  # Stop 2% before phase end
        drift = 0.003 * min(elapsed, 5.0)  # 0.3%/s, max 1.5%
        new_f = min(ceiling, self.current_fraction + drift)
        self._set_fraction(new_f)

    def process_line(self, line: str) -> Tuple[float, str]:
        """Main entry point.  Pass every line from the script subprocess.

        Returns ``(fraction, message)``.  Always safe to call — never
        raises.
        """
        if not line:
            return self.current_fraction, self.current_message

        stripped = line.strip()

        # ── Layer 1: Explicit Protocol ────────────────────────────────
        if "__DONE__" in stripped:
            self._set_fraction(1.0, "Complete")
            self.is_done = True
            return 1.0, "Complete"

        if "__ERROR__" in stripped:
            msg = stripped.split("__ERROR__", 1)[-1].strip().lstrip("|").strip()
            self.current_message = f"Error: {msg}" if msg else "Error occurred"
            self.has_error = True
            return self.current_fraction, self.current_message

        if "__PROGRESS__" in stripped:
            try:
                _, data = stripped.split("__PROGRESS__", 1)
                data = data.strip().lstrip("|").strip()
                msg = ""
                if "|" in data:
                    pct_str, msg = data.split("|", 1)
                    msg = msg.strip()
                else:
                    pct_str = data

                if "/" in pct_str:
                    curr, tot = map(int, pct_str.strip().split("/"))
                    pct = (curr / max(1, tot)) * 100.0
                else:
                    pct = float(pct_str.strip())

                # Never go past 0.98 (reserve final 2% for __DONE__)
                new_f = min(0.98, pct / 100.0)
                self._set_fraction(new_f, msg or self.current_message)
                return self.current_fraction, self.current_message
            except Exception:
                pass  # Malformed token — fall through

        if "__PHASE__" in stripped:
            try:
                _, data = stripped.split("__PHASE__", 1)
                data = data.strip().lstrip("|").strip()
                parts = data.split("|", 2)
                phase = parts[0].strip().lower()
                pct_in_ph = float(parts[1].strip()) if len(parts) > 1 else 0.0
                msg = parts[2].strip() if len(parts) > 2 else ""
                new_f = self._fraction_from_phase_pct(phase, pct_in_ph)
                self.current_phase = phase
                self._set_fraction(new_f, msg or self.current_message)
                return self.current_fraction, self.current_message
            except Exception:
                pass

        # ── Layer 2: Tool-specific structured lines ───────────────────
        m = RE_DPKG_PMSTATUS.match(stripped)
        if m:
            kind = m.group(1)
            pct = float(m.group(3))
            desc = m.group(4).strip()
            phase = "download" if kind == "dlstatus" else "install"
            new_f = self._fraction_from_phase_pct(phase, pct)
            self.current_phase = phase
            self._set_fraction(new_f, desc)
            return self.current_fraction, self.current_message

        # aria2c  [#abc 14MiB/187MiB(7%) ...]
        m = RE_ARIA2C.search(stripped)
        if m and "MiB" in stripped:
            pct = float(m.group(1))
            new_f = self._fraction_from_phase_pct("download", pct)
            self._set_fraction(new_f, f"Downloading... ({int(pct)}%)")
            return self.current_fraction, self.current_message

        # wget  "     14K  14%  123KB/s"
        m = RE_WGET.search(stripped)
        if m and ("KB/s" in stripped or "MB/s" in stripped):
            pct = float(m.group(1))
            new_f = self._fraction_from_phase_pct("download", pct)
            self._set_fraction(new_f, f"Downloading... ({int(pct)}%)")
            return self.current_fraction, self.current_message

        # ── Layer 3: Keyword heuristics ───────────────────────────────
        for pattern, phase_hint, bump in KEYWORD_RULES:
            if pattern.search(stripped):
                self._apply_heuristic_bump(phase_hint, bump)
                # Use line text as message if it's informative enough
                if len(stripped) > 10:
                    self.current_message = stripped[:80]
                break

        return self.current_fraction, self.current_message

    def script_downloaded(self):
        """Call after install.sh downloaded successfully."""
        _, hi = self._phase_range("script_download")
        self._set_fraction(hi, "Running install script...")
        self.current_phase = "prepare"

    def detect_script_type(self, script_content: str):
        """Auto-detect whether script uses download+extract or
        repo-based install.  Call after downloading install.sh,
        before running it.  Updates the phase map accordingly.
        """
        if "install_appimage" in script_content:
            self.app_type = "appimage"
            self.script_type = "appimage"
        elif "download_file" in script_content and "extract" in script_content:
            self.script_type = "download"
        elif "distro_run" in script_content:
            if self.script_type != "download":
                self.script_type = "repo"
        # Re-select map based on updated type info
        self._phase_map = self._select_phase_map()

    @staticmethod
    def is_progress_token(line: str) -> bool:
        """Return True if *line* contains a progress protocol token."""
        return any(tok in line for tok in PROGRESS_TOKENS)
