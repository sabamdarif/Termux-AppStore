# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for termux_appstore.backend.native_data (stdlib unittest).

Run with: PYTHONPATH=appstore venv/bin/python -m unittest discover appstore/tests
Requires the _buildconf.py test shim in termux_appstore/ (gitignored; see the implementation plan for its contents).
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from termux_appstore.backend import native_data


class TestEnabledReposApt(unittest.TestCase):
    def _prefix(self, files):
        tmp = tempfile.TemporaryDirectory()
        base = Path(tmp.name)
        (base / "etc/apt/sources.list.d").mkdir(parents=True)
        for rel, content in files.items():
            (base / "etc/apt" / rel).write_text(content)
        return tmp, str(base)

    def test_x11_and_tur_enabled(self):
        tmp, prefix = self._prefix(
            {
                "sources.list": "deb https://packages-cf.termux.dev/apt/termux-main stable main\n",
                "sources.list.d/x11.list": "deb https://packages-cf.termux.dev/apt/termux-x11 x11 main\n",
                "sources.list.d/tur.list": "deb https://tur.kcubeterm.com tur-packages tur\n",
            }
        )
        with tmp:
            self.assertEqual(native_data.enabled_repos_apt(prefix), {"x11", "tur"})

    def test_commented_out_ignored(self):
        tmp, prefix = self._prefix(
            {
                "sources.list": "# deb https://packages-cf.termux.dev/apt/termux-x11 x11 main\n",
            }
        )
        with tmp:
            self.assertEqual(native_data.enabled_repos_apt(prefix), set())


class TestEnabledReposPacman(unittest.TestCase):
    def test_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            etc = Path(tmp) / "etc"
            etc.mkdir()
            (etc / "pacman.conf").write_text(
                "[options]\n[main]\n[x11]\n#[tur]\n[tur-continuous]\n"
            )
            self.assertEqual(native_data.enabled_repos_pacman(tmp), {"x11"})


class TestMergeCatalog(unittest.TestCase):
    def test_curated_wins_by_package_name(self):
        curated = [
            {"app_name": "Abiword", "folder_name": "Abiword", "package_name": "abiword"}
        ]
        native = [
            {"app_name": "Abiword", "folder_name": "abiword", "package_name": "abiword"},
            {"app_name": "SciTE", "folder_name": "scite", "package_name": "scite"},
        ]
        merged = native_data.merge_catalog(curated, native)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["folder_name"], "Abiword")  # curated casing kept
        self.assertEqual(merged[1]["package_name"], "scite")

    def test_folder_name_fallback_dedupe(self):
        curated = [{"app_name": "X", "folder_name": "X"}]
        native = [{"app_name": "X", "folder_name": "x"}]
        merged = native_data.merge_catalog(curated, native)
        self.assertEqual(len(merged), 1)


class TestFetchCatalogsCaching(unittest.TestCase):
    def test_download_then_cached_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(native_data, "NATIVE_DIR", tmp):
                good = [{"package_name": "foo", "supported_arch": "aarch64,arm"}]
                with mock.patch.object(native_data, "_fetch_json", return_value=good):
                    out = native_data.fetch_native_catalogs({"x11"})
                # x11 + the always-fetched main catalog -> the entry per repo.
                self.assertEqual(out, good + good)
                self.assertTrue(
                    (Path(tmp) / "x11.json").exists(), "cache written"
                )
                self.assertTrue(
                    (Path(tmp) / "main.json").exists(), "main cache written"
                )

                def boom(_url):
                    raise OSError("offline")

                with mock.patch.object(native_data, "_fetch_json", side_effect=boom):
                    out = native_data.fetch_native_catalogs({"x11"})
                self.assertEqual(out, good + good, "cached fallback used")


class TestSvgLogoSelection(unittest.TestCase):
    """app_card._load_logo must fall back to logo.svg when logo.png is absent."""

    def test_svg_fallback_path_selection(self):
        import sys
        from unittest import mock as _mock

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "MyApp"
            folder.mkdir()
            (folder / "logo.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"/>'
            )
            try:
                from gi.repository import GdkPixbuf  # noqa: F401
            except ImportError:
                self.skipTest("no GdkPixbuf on this host")

            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from termux_appstore.ui import app_card

            with _mock.patch.object(app_card, "APPSTORE_LOGO_DIR", tmp):
                image = app_card._load_logo({"folder_name": "MyApp"})
            self.assertIsNotNone(image, "SVG logo was not loaded")


if __name__ == "__main__":
    unittest.main()
