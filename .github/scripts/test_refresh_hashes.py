"""CB6 — refresh_hashes.py pure-logic tests (no network).

refresh_hashes.py re-pins an app's sha256 header after a version bump. The
network-touching parts (sandbox URL replay, download+hash) are exercised
manually; here we lock the header state machine that decides what gets written:
parse_sha_header, build_header, and replace_header. These are what guarantee a
bump never leaves a stale hash and that a scalar upgrades to a map when a script
resolves several artifacts.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import refresh_hashes as rh  # noqa: E402


# --- parse_sha_header: the three states the updater branches on ---------------

def test_parse_scalar():
    assert rh.parse_sha_header('version="v1"\nsha256="abc"\n') == "scalar"


def test_parse_skip_is_distinct_from_scalar():
    # sha256="skip" must NOT be treated as a hash to refresh.
    assert rh.parse_sha_header('sha256="skip"\n') == "skip"
    assert rh.parse_sha_header('sha256="SKIP"\n') == "skip"


def test_parse_map():
    text = 'declare -A sha256=(\n\t["a.deb"]="h1"\n\t["b.deb"]="h2"\n)\n'
    assert rh.parse_sha_header(text) == "map"


def test_parse_none():
    assert rh.parse_sha_header('version="v1"\npage_url="x"\n') == "none"


# --- build_header: scalar vs map rendering ------------------------------------

def test_build_scalar_single_artifact():
    assert rh.build_header([("f.deb", "deadbeef")], force_map=False) == 'sha256="deadbeef"'


def test_build_map_when_multiple_artifacts():
    out = rh.build_header([("a.deb", "h1"), ("b.deb", "h2")], force_map=False)
    assert out.startswith("declare -A sha256=(")
    assert '["a.deb"]="h1"' in out
    assert '["b.deb"]="h2"' in out
    assert out.rstrip().endswith(")")


def test_build_force_map_keeps_map_for_single_artifact():
    # A script that was already a map stays a map even if it resolves one file,
    # so the header shape does not thrash between runs.
    out = rh.build_header([("only.deb", "h1")], force_map=True)
    assert out.startswith("declare -A sha256=(")
    assert '["only.deb"]="h1"' in out


# --- replace_header: matched flag + literal substitution ----------------------

def test_replace_scalar_updates_value_only():
    text = '#!/bin/bash\nversion="v2"\nsha256="oldhash"\n\necho hi\n'
    out, matched = rh.replace_header(text, "scalar", 'sha256="newhash"')
    assert matched
    assert 'sha256="newhash"' in out
    assert "oldhash" not in out
    # The following blank line and code must survive (regex must not eat them).
    assert out.endswith("\n\necho hi\n")


def test_replace_scalar_to_map_block():
    text = 'version="v2"\nsha256="oldhash"\nprogress_phase "prepare"\n'
    new = 'declare -A sha256=(\n\t["a"]="h1"\n\t["b"]="h2"\n)'
    out, matched = rh.replace_header(text, "scalar", new)
    assert matched
    assert "declare -A sha256=(" in out
    assert 'progress_phase "prepare"' in out


def test_replace_map_block():
    text = 'v="x"\ndeclare -A sha256=(\n\t["a"]="old1"\n\t["b"]="old2"\n)\ncode\n'
    new = 'declare -A sha256=(\n\t["a"]="new1"\n\t["b"]="new2"\n)'
    out, matched = rh.replace_header(text, "map", new)
    assert matched
    assert "old1" not in out and "old2" not in out
    assert "new1" in out and "new2" in out
    assert out.endswith("code\n")


def test_replace_reports_no_match():
    # No header present -> matched False, so the caller fails the bump rather
    # than silently leaving a stale hash.
    _out, matched = rh.replace_header("version=\"v2\"\n", "scalar", 'sha256="x"')
    assert not matched


def test_replace_is_literal_not_regex_template():
    # A hash string can't contain regex group refs, but guard anyway: the repl
    # must be inserted literally.
    text = 'sha256="old"\n'
    out, matched = rh.replace_header(text, "scalar", r'sha256="\1\g<0>&"')
    assert matched
    assert r'sha256="\1\g<0>&"' in out
