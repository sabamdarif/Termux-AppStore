# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for .github/scripts/native_catalog_gen.py (stdlib unittest)."""

import io
import importlib.util
import tarfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "scripts"
    / "native_catalog_gen.py"
)
spec = importlib.util.spec_from_file_location("native_catalog_gen", SCRIPT)
assert spec is not None and spec.loader is not None
ncg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ncg)


def make_deb(files):
    """Build an in-memory .deb (ar + data.tar.xz) from {path: bytes}."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:xz") as tf:
        for name, data in sorted(files.items()):
            ti = tarfile.TarInfo(f"./{name}")
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    payload = buf.getvalue()

    def member(name, data):
        header = (
            f"{name:<16}{0:<12}{0:<6}{0:<6}{0o100644:<8}{len(data):<10}`\n".encode()
        )
        return header + data + (b"\n" if len(data) % 2 else b"")

    return b"!<arch>\n" + member("debian-binary", b"2.0\n") + member(
        "data.tar.xz", payload
    )


PREFIX = "data/data/com.termux/files/usr"


class TestStanzaParser(unittest.TestCase):
    def test_basic_and_continuation(self):
        text = (
            "Package: foo\n"
            "Version: 1:2.3-4\n"
            "Description: short\n"
            " long continuation line\n"
            "\n"
            "Package: bar\n"
            "Version: 0.1\n"
        )
        stanzas = list(ncg.parse_stanzas(text))
        self.assertEqual(len(stanzas), 2)
        self.assertEqual(stanzas[0]["Package"], "foo")
        self.assertEqual(stanzas[0]["Description"], "short long continuation line")

    def test_strip_epoch(self):
        self.assertEqual(ncg.strip_epoch("1:2.3-4"), "2.3-4")
        self.assertEqual(ncg.strip_epoch("2.3"), "2.3")


class TestContentsParser(unittest.TestCase):
    def test_desktop_lines_and_comma_split(self):
        text = (
            f"{PREFIX}/share/applications/foo.desktop foo\n"
            f"{PREFIX}/share/applications/wezterm.desktop wezterm,wezterm-nightly\n"
            f"{PREFIX}/bin/foo foo\n"
            f"{PREFIX}/share/applications/nested/sub.desktop bad\n"
        )
        result = ncg.parse_contents(text)
        self.assertIn("foo", result)
        self.assertIn("wezterm", result)
        self.assertIn("wezterm-nightly", result)  # comma-split
        self.assertNotIn("bad", result)  # nested dir doesn't match


class TestDesktopParsing(unittest.TestCase):
    def test_ignores_localized_and_other_groups(self):
        text = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=SciTE\n"
            "Name[de]=SciTE-DE\n"
            "Comment=Edit source\n"
            "Exec=scite %F\n"
            "[Desktop Action new]\n"
            "Name=Should not leak\n"
        )
        d = ncg.parse_desktop_file(text)
        self.assertEqual(d["Name"], "SciTE")
        self.assertEqual(d["Exec"], "scite %F")
        self.assertNotIn("Should", d.get("Name", ""))

    def test_clean_exec(self):
        self.assertEqual(ncg.clean_exec("scite %F", "scite"), "scite")
        self.assertEqual(ncg.clean_exec("env FOO=1 run --x %u", "run"), "run --x")
        self.assertEqual(ncg.clean_exec("", "pkg"), "pkg")


class TestCategories(unittest.TestCase):
    def test_freedesktop_mapping(self):
        self.assertEqual(ncg.map_categories("Utility;TextEditor;", "x", "y"), ["Accessories"])
        self.assertEqual(ncg.map_categories("Network;WebBrowser;", "x", "y"), ["Internet"])
        self.assertEqual(ncg.map_categories("AudioVideo;Player;", "x", "y"), ["Multimedia"])

    def test_regex_fallback_and_default(self):
        self.assertEqual(ncg.map_categories("", "kturtle", ""), ["Productivity"])
        self.assertEqual(ncg.map_categories("", "mystery", "does nothing"), ["Accessories"])


class TestDebExtraction(unittest.TestCase):
    def _deb_path(self, tmp, files):
        path = Path(tmp) / "test.deb"
        path.write_bytes(make_deb(files))
        return path

    def test_full_entry_extraction(self):
        desktop = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Test Editor\n"
            "Comment=Edit things\n"
            "Exec=testedit %F\n"
            "Icon=testedit\n"
            "Categories=Development;IDE;\n"
        ).encode()
        with self.subTest("extract"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                deb = self._deb_path(
                    tmp,
                    {
                        f"{PREFIX}/share/applications/testedit.desktop": desktop,
                        f"{PREFIX}/share/icons/hicolor/64x64/apps/testedit.png": b"PNGDATA",
                        f"{PREFIX}/bin/testedit": b"#!/bin/sh\n",
                    },
                )
                tf = ncg.open_deb_payload(deb)
                stanza = {"Version": "1:1.0-2", "Description": "A test editor"}
                entry, icon = ncg.build_entry_from_package(tf, "testedit", stanza, {})
                self.assertEqual(entry["app_name"], "Test Editor")
                self.assertEqual(entry["description"], "Edit things")
                self.assertEqual(entry["run_cmd"], "testedit")
                self.assertEqual(entry["categories"], ["Development"])
                self.assertEqual(entry["version"], "1.0-2")  # epoch stripped
                self.assertEqual(entry["install_url"], "scripts/native-install.sh")
                self.assertIsNotNone(icon)
                folder, ext, data = icon
                self.assertEqual((folder, ext, data), ("testedit", ".png", b"PNGDATA"))

    def test_nodisplay_filtered(self):
        desktop = (
            "[Desktop Entry]\nType=Application\nName=Hidden\nNoDisplay=true\n"
        ).encode()
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            deb = self._deb_path(
                tmp, {f"{PREFIX}/share/applications/hidden.desktop": desktop}
            )
            tf = ncg.open_deb_payload(deb)
            entry, icon = ncg.build_entry_from_package(tf, "hidden", {}, {})
            self.assertIsNone(entry)
            self.assertIsNone(icon)

    def test_override_wins(self):
        desktop = (
            "[Desktop Entry]\nType=Application\nName=Raw Name\nExec=raw\n"
        ).encode()
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            deb = self._deb_path(
                tmp, {f"{PREFIX}/share/applications/raw.desktop": desktop}
            )
            tf = ncg.open_deb_payload(deb)
            ov = {
                "raw": {
                    "app_name": "Pretty",
                    "folder_name": "Pretty",
                    "description": "Curated desc",
                    "categories": ["Office"],
                    "run_cmd": "raw --pretty",
                }
            }
            entry, _ = ncg.build_entry_from_package(tf, "raw", {"Version": "1"}, ov)
            self.assertEqual(entry["app_name"], "Pretty")
            self.assertEqual(entry["folder_name"], "Pretty")
            self.assertEqual(entry["description"], "Curated desc")
            self.assertEqual(entry["categories"], ["Office"])
            self.assertEqual(entry["run_cmd"], "raw --pretty")

    def test_metadata_only_entry(self):
        stanza = {"Version": "2.0", "Description": "A CLI tool", "Homepage": "https://x"}
        ov = {
            "lazygit": {
                "app_name": "Lazygit",
                "folder_name": "Lazygit",
                "run_cmd": "lazygit",
                "terminal": True,
                "categories": ["Development"],
            }
        }
        entry = ncg.build_entry_metadata_only("lazygit", stanza, ov)
        self.assertEqual(entry["folder_name"], "Lazygit")
        self.assertTrue(entry["terminal"])
        self.assertEqual(entry["version"], "2.0")
        self.assertEqual(entry["homepage"], "https://x")


class TestMergeRepoCatalogs(unittest.TestCase):
    """merge_native_bundles.merge_repo_catalogs — per-arch -> per-repo."""

    @classmethod
    def setUpClass(cls):
        spec2 = importlib.util.spec_from_file_location(
            "merge_native_bundles",
            Path(__file__).resolve().parents[2]
            / ".github"
            / "scripts"
            / "merge_native_bundles.py",
        )
        cls.mnb = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(cls.mnb)

    def test_supported_arch_accumulates(self):
        entry_a = {"package_name": "foo", "version": "1.0", "app_name": "Foo"}
        entry_b = {"package_name": "foo", "version": "1.1", "app_name": "Foo"}
        merged = self.mnb.merge_repo_catalogs(
            {"aarch64": [entry_a], "arm": [entry_b]}
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["supported_arch"], "aarch64,arm")
        # newer version's scalar fields win
        self.assertEqual(merged[0]["version"], "1.1")

    def test_single_arch_entry(self):
        merged = self.mnb.merge_repo_catalogs(
            {"aarch64": [{"package_name": "bar", "version": "1.0"}], "arm": []}
        )
        self.assertEqual(merged[0]["supported_arch"], "aarch64")

    def test_distinct_packages_kept(self):
        merged = self.mnb.merge_repo_catalogs(
            {
                "aarch64": [{"package_name": "a", "version": "1"}],
                "arm": [{"package_name": "b", "version": "1"}],
            }
        )
        self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
