#!/usr/bin/env python3
"""Merge per-leg native catalog bundles into the final native_data assets.

Each matrix leg of native-catalog.yml uploads a bundle artifact
(``native-<repo>-<arch>``) containing that leg's catalog JSON, its extracted
icons, and its slice of the incremental state file. This script merges them:

- per-arch JSONs are merged into ONE catalog per repo (``x11.json``,
  ``tur.json``, ``main.json``); each entry's ``supported_arch`` records the
  arches the package appeared in, and the newest version across arches wins;
- icons dirs are unioned into ``icons/`` (extracted icons are arch-independent);
- state files are deep-merged per package/repo/arch so no leg's cached
  results are lost;
- ``native-version.json`` is regenerated fresh (new catalog_version);
- ``native-icons.zip`` is rebuilt from the merged icons dir.

Usage: merge_native_bundles.py --bundles bundles/ --out out/
"""

import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPOS = ("x11", "tur", "main")
ARCHES = ("aarch64", "arm")


def deep_merge_state(base, extra):
    """Merge extra into base: pkg -> repo -> arch -> record."""
    for pkg, repos in extra.items():
        if not isinstance(repos, dict):
            continue
        target = base.setdefault(pkg, {})
        for repo, archs in repos.items():
            if not isinstance(archs, dict):
                continue
            target_repo = target.setdefault(repo, {})
            for arch, record in archs.items():
                target_repo[arch] = record
    return base


def merge_repo_catalogs(per_arch):
    """Merge {arch: [entries]} into one list with supported_arch filled in.

    Entries are keyed by package_name; the record from the arch whose version
    sorts last wins for the scalar fields, and supported_arch lists every arch
    the package appeared in.
    """
    by_pkg = {}
    for arch in ARCHES:
        for entry in per_arch.get(arch, []):
            pkg = entry.get("package_name")
            if not pkg:
                continue
            existing = by_pkg.get(pkg)
            if existing is None:
                entry = dict(entry)
                entry["supported_arch"] = arch
                by_pkg[pkg] = entry
            else:
                archs = existing["supported_arch"].split(",")
                if arch not in archs:
                    archs.append(arch)
                    existing["supported_arch"] = ",".join(sorted(archs))
                if entry.get("version", "") > existing.get("version", ""):
                    for key, value in entry.items():
                        if key != "supported_arch":
                            existing[key] = value
    return list(by_pkg.values())


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--bundles", required=True, help="dir of bundle artifact dirs")
    ap.add_argument("--out", required=True, help="output dir for release assets")
    args = ap.parse_args()

    bundles = Path(args.bundles)
    out = Path(args.out)
    icons_out = out / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icons_out.mkdir(exist_ok=True)

    state = {}
    # repo -> arch -> [entries]
    per_repo = {repo: {} for repo in REPOS}
    for bundle in sorted(bundles.iterdir()):
        if not bundle.is_dir():
            continue
        print(f"merging bundle: {bundle.name}")
        # upload-artifact preserves the upload paths relative to the workspace
        # (out/<json>, state/native-state.json, out/icons/...), so resolve
        # recursively rather than assuming a flat bundle root.
        for f in bundle.rglob("*"):
            if not f.is_file():
                continue
            stem = f.name.removesuffix(".json")
            if f.name == "native-state.json":
                with open(f) as fh:
                    deep_merge_state(state, json.load(fh))
            elif "-" in stem:
                repo, _, arch = stem.rpartition("-")
                if repo in REPOS and arch in ARCHES:
                    with open(f) as fh:
                        per_repo[repo][arch] = json.load(fh)
        for icons_dir in (d for d in bundle.rglob("icons") if d.is_dir()):
            for item in icons_dir.iterdir():
                dest = icons_out / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

    counts = {}
    for repo in REPOS:
        if not per_repo[repo]:
            raise SystemExit(f"missing all catalog JSONs for repo: {repo}")
        merged = merge_repo_catalogs(per_repo[repo])
        with open(out / f"{repo}.json", "w") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        counts[repo] = len(merged)

    with open(out / "native-state.json", "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)

    now = datetime.now(timezone.utc)
    with open(out / "native-version.json", "w") as f:
        json.dump(
            {
                "generated_at": now.isoformat(),
                "catalog_version": now.strftime("%Y%m%d%H%M%S"),
                "counts": counts,
            },
            f,
            indent=2,
        )

    with zipfile.ZipFile(out / "native-icons.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(icons_out.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(icons_out))

    print(json.dumps(counts, indent=2))
    print(f"merged {len(counts)} repo catalogs, "
          f"{sum(1 for _ in icons_out.rglob('*') if _.is_file())} icon files, "
          f"{len(state)} state packages")


if __name__ == "__main__":
    main()
