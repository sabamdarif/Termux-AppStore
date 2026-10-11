#!/usr/bin/env python3
"""Merge per-leg native catalog bundles into the final native_data assets.

Each matrix leg of native-catalog.yml uploads a bundle artifact
(``native-<repo>-<arch>``) containing that leg's catalog JSON, its extracted
icons, and its slice of the incremental state file. This script merges them:

- per-repo JSONs are copied through (``x11-aarch64.json`` etc.);
- icons dirs are unioned into ``icons/`` (legs never write the same folder
  for extracted icons; on collision the last one wins, which is fine);
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

EXPECTED_JSONS = [
    "x11-aarch64.json",
    "x11-arm.json",
    "tur-aarch64.json",
    "tur-arm.json",
    "main-aarch64.json",
    "main-arm.json",
]


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
    found_jsons = []
    for bundle in sorted(bundles.iterdir()):
        if not bundle.is_dir():
            continue
        print(f"merging bundle: {bundle.name}")
        for f in bundle.iterdir():
            if f.name in EXPECTED_JSONS:
                shutil.copy2(f, out / f.name)
                found_jsons.append(f.name)
            elif f.name == "native-state.json":
                with open(f) as fh:
                    deep_merge_state(state, json.load(fh))
        icons_dir = bundle / "icons"
        if icons_dir.is_dir():
            for item in icons_dir.iterdir():
                dest = icons_out / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

    missing = [j for j in EXPECTED_JSONS if j not in found_jsons]
    if missing:
        raise SystemExit(f"missing catalog JSONs from bundles: {missing}")

    with open(out / "native-state.json", "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)

    now = datetime.now(timezone.utc)
    counts = {}
    for j in EXPECTED_JSONS:
        with open(out / j) as f:
            counts[j.removesuffix(".json")] = len(json.load(f))
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
    print(f"merged {len(found_jsons)} catalogs, "
          f"{sum(1 for _ in icons_out.rglob('*') if _.is_file())} icon files, "
          f"{len(state)} state packages")


if __name__ == "__main__":
    main()
