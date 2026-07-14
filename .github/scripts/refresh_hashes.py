#!/usr/bin/env python3
"""refresh_hashes.py — re-pin an app's SHA256 header after a version bump (CB6).

Invoked by update_versions.sh immediately after it rewrites `version="..."` in a
single apps/<App>/install.sh. A pinned sha256 header points at the *old* artifact,
so once Part C-bis verification is enforced an auto-bumped app would fail to install
with a hash mismatch. This script recomputes the hash(es) for the NEW version, in the
same change that bumps the version.

Behavior (see docs/REFACTOR_PLAN.md CB6):
  * No `sha256` header, or `sha256="skip"`  -> nothing to refresh, exit 0.
  * scalar `sha256="<hex>"`                 -> re-hash; stays scalar if the script
                                               resolves to one artifact, upgrades to a
                                               map if it resolves to several.
  * `declare -A sha256=( ["file"]="hex" )`  -> rebuilt key->hash with the NEW filenames.
  * Any artifact 404s / download fails / hashing errors -> exit non-zero WITHOUT
    editing the file, so the caller reverts the version bump for that app.

URL resolution replays the script's OWN url-building logic in a sandbox where the
download entrypoints are stubbed to record (filename, url) instead of fetching — the
same technique the one-shot backfill used, so resolved URLs match runtime exactly.
This is safe here because update_versions.sh runs only on schedule/workflow_dispatch
against already-merged code; it is never reachable from a PR/fork. (The separate CI
PR gate, CB8, inspects untrusted PR code and must NOT source it.)
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# Cap a single artifact download so a hostile redirect can't exhaust the runner.
MAX_ARTIFACT_BYTES = 1024 * 1024 * 1024  # 1 GiB
DOWNLOAD_TIMEOUT = 60  # seconds per read/connect
USER_AGENT = "termux-appstore-refresh-hashes"

# Bash harness that sources the (trusted) install.sh with every side effect stubbed
# and the download entrypoints recording "<filename>\t<url>". Mirrors the runtime
# arg handling of download_file and the install_* helpers so recorded filenames equal
# the sha256 map keys used at verify time. Prints unique "filename\turl" pairs.
_RESOLVER = r"""
set -uo pipefail
install_sh="$1"

STUBS="$(mktemp)"
cat >"$STUBS" <<'STUBEOF'
_record() { printf '%s\t%s\n' "$1" "$2" >>"$CAPTURE_FILE"; }
download_file() {
	local dest url
	if [[ -z "${2:-}" ]]; then url="$1"; dest="$(basename "$1")"; else dest="$1"; url="$2"; fi
	_record "$(basename "$dest")" "$url"
	return 0
}
install_archive_into_opt() { _record "$(basename "$2")" "$2"; return 0; }
install_deb_into_distro()  { _record "$(basename "$2")" "$1"; return 0; }
install_deb_into_termux()  { _record "$(basename "$1")" "$1"; return 0; }
uname() { if [[ "${1:-}" == "-m" ]]; then echo "$FORCE_ARCH"; else command uname "$@"; fi; }
detect_arch() {
	local pair key val
	for pair in "$@"; do
		key="${pair%%=*}"; val="${pair#*=}"
		# shellcheck disable=SC2254
		case "$FORCE_ARCH" in $key) echo "$val"; return 0 ;; esac
	done
	return 1
}
progress_phase() { :; }; progress_done() { :; }; progress_report() { :; }
progress_error() { :; }; print_success() { :; }; print_failed() { return 0; }
print_warn() { :; }; print_msg() { :; }; log_debug() { :; }; log_warn() { :; }
log_error() { :; }; check_and_delete() { :; }
check_and_create_directory() { mkdir -p "$@" 2>/dev/null || :; }
check_and_backup() { :; }; check_and_restore() { :; }; pd_check_and_delete() { :; }
pd_check_and_create_directory() { :; }; pd_update_sys() { :; }; update_sys() { :; }
distro_run() { :; }; install_appimage() { :; }; install_deb_in_termux_pacman() { :; }
create_desktop_entry() { :; }; fix_exec() { :; }; extract() { :; }
package_install_and_check() { :; }; package_remove_and_check() { :; }
pdrun() { :; }; sudo() { :; }; dpkg() { :; }; apt() { :; }; apt-get() { :; }
dnf() { :; }; proot-distro() { :; }; chroot-distro() { :; }
STUBEOF
trap 'rm -f "$STUBS"' EXIT

sa="$(grep -m1 '^supported_arch=' "$install_sh" | cut -d'"' -f2)"
app_arches=()
case ",$sa," in *,aarch64,*|*,arm64,*) app_arches+=(aarch64) ;; esac
case ",$sa," in *,arm,*|*,armv7l,*|*,armhf,*) app_arches+=(armv7l) ;; esac
[[ ${#app_arches[@]} -eq 0 ]] && app_arches=(aarch64 armv7l)

CAPTURE_FILE="$(mktemp)"
for FORCE_ARCH in "${app_arches[@]}"; do
	for SELECTED_DISTRO in debian fedora; do
		sandbox="$(mktemp -d)"
		(
			set +e +u
			export CAPTURE_FILE FORCE_ARCH
			export HOME="$sandbox" PREFIX="$sandbox/usr" TERMUX_PREFIX="$sandbox/usr"
			export TMPDIR="$sandbox/tmp" distro_path="$sandbox/distro"
			export SELECTED_DISTRO SELECTED_DISTRO_TYPE="proot"
			mkdir -p "$TMPDIR" "$TERMUX_PREFIX/share/applications/pd_added" \
				"$distro_path/opt" "$distro_path/root" 2>/dev/null
			# shellcheck disable=SC1090
			source "$STUBS"
			cd "$TMPDIR" 2>/dev/null
			# shellcheck disable=SC1090
			source "$install_sh"
		) >/dev/null 2>&1
		rm -rf "$sandbox"
	done
done

sort -u "$CAPTURE_FILE"
rm -f "$CAPTURE_FILE"
"""


def log(msg: str) -> None:
    print(f"[refresh_hashes] {msg}", file=sys.stderr)


def parse_sha_header(text: str) -> str:
    """Return 'none', 'skip', 'scalar', or 'map' for the file's sha256 header."""
    # scalar sha256="..." (also matches sha256="skip")
    m = re.search(r'^\s*sha256="([^"]*)"\s*$', text, re.MULTILINE)
    if m:
        return "skip" if m.group(1).strip().lower() == "skip" else "scalar"
    if re.search(r"^\s*declare\s+-A\s+sha256=\(", text, re.MULTILINE):
        return "map"
    return "none"


def resolve_artifacts(install_sh: Path) -> list[tuple[str, str]]:
    """Replay the script to get unique (filename, url) pairs. Raises on resolver error."""
    # Absolute path: the sandbox does `cd "$TMPDIR"` before sourcing, so a
    # relative path would not resolve.
    proc = subprocess.run(
        ["bash", "-c", _RESOLVER, "resolver", str(install_sh.resolve())],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"URL resolver failed: {proc.stderr.strip()}")
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in proc.stdout.splitlines():
        if "\t" not in line:
            continue
        key, url = line.split("\t", 1)
        key, url = key.strip(), url.strip()
        if not key or not url:
            continue
        # Drop obviously-unresolved URLs (empty path segment from an unmatched arch).
        if "//" in url.split("://", 1)[-1] or "/./" in url:
            continue
        if not url.startswith("https://"):
            raise RuntimeError(f"refusing non-https url: {url}")
        if key in seen:
            continue
        seen.add(key)
        pairs.append((key, url))
    return pairs


def download_and_hash(url: str) -> str:
    """Stream the artifact to a temp file and return its sha256 hex. Raises on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    h = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp, \
            tempfile.NamedTemporaryFile() as tmp:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ARTIFACT_BYTES:
                raise RuntimeError(f"artifact exceeds {MAX_ARTIFACT_BYTES} bytes: {url}")
            tmp.write(chunk)
            h.update(chunk)
    if total == 0:
        raise RuntimeError(f"empty download: {url}")
    return h.hexdigest()


def build_header(pairs_with_hash: list[tuple[str, str]], force_map: bool) -> str:
    """Render the replacement sha256 header. Scalar for one artifact unless force_map."""
    if len(pairs_with_hash) == 1 and not force_map:
        return f'sha256="{pairs_with_hash[0][1]}"'
    lines = ["declare -A sha256=("]
    for key, digest in pairs_with_hash:
        lines.append(f'\t["{key}"]="{digest}"')
    lines.append(")")
    return "\n".join(lines)


def replace_header(text: str, header_kind: str, new_header: str) -> tuple[str, bool]:
    """Swap the old sha256 header for new_header. Returns (text, matched).

    `matched` is False only when the header regex found nothing — that's the
    error case. A matched-but-unchanged result (recomputed hash equals the old
    one) returns matched=True with identical text, which is the normal no-op.
    """
    # Trailing whitespace class is [ \t] (not \s) so we don't swallow the
    # following blank line / newline and merge the header into the next block.
    if header_kind == "scalar":
        pattern = r'^[ \t]*sha256="[^"]*"[ \t]*$'
        flags = re.MULTILINE
    else:
        # map: replace from `declare -A sha256=(` through the closing `)` line.
        pattern = r"^[ \t]*declare\s+-A\s+sha256=\(.*?^[ \t]*\)[ \t]*$"
        flags = re.MULTILINE | re.DOTALL
    if not re.search(pattern, text, flags):
        return text, False
    # new_header may contain backslashes/group refs; use a function repl to keep
    # it literal.
    return re.sub(pattern, lambda _: new_header, text, count=1, flags=flags), True


def main() -> int:
    if len(sys.argv) != 2:
        log("usage: refresh_hashes.py <path/to/install.sh>")
        return 2
    install_sh = Path(sys.argv[1])
    if not install_sh.is_file():
        log(f"not a file: {install_sh}")
        return 2

    text = install_sh.read_text()
    kind = parse_sha_header(text)

    if kind in ("none", "skip"):
        log(f"{install_sh.parent.name}: no hash to refresh ({kind})")
        return 0

    log(f"{install_sh.parent.name}: refreshing ({kind}) header...")
    try:
        pairs = resolve_artifacts(install_sh)
    except RuntimeError as e:
        log(f"resolve failed: {e}")
        return 1
    if not pairs:
        log("no artifact URLs resolved")
        return 1

    hashed: list[tuple[str, str]] = []
    for key, url in pairs:
        try:
            digest = download_and_hash(url)
        except Exception as e:  # network, http error, size cap, empty
            log(f"FAILED {key}: {e} ({url})")
            return 1
        log(f"  {key} -> {digest}")
        hashed.append((key, digest))

    new_header = build_header(hashed, force_map=(kind == "map"))
    updated, matched = replace_header(text, kind, new_header)
    if not matched:
        log("header replacement matched nothing — refusing to leave a stale hash")
        return 1
    if updated != text:
        install_sh.write_text(updated)
        log(f"{install_sh.parent.name}: pinned {len(hashed)} artifact(s)")
    else:
        log(f"{install_sh.parent.name}: hashes unchanged ({len(hashed)} artifact(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
