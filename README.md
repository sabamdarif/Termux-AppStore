# Termux App Store

A simple GTK3 based app store for Termux.

## Where the app catalog comes from

The store merges two data sources:

- **Curated apps** (`apps/` → `data/apps.json`, published as the `apps_data`
  release): distro (proot) apps and native apps with custom install steps.
- **Native repo catalog** (published as the rolling `native_data` release):
  generated daily by `.github/scripts/native_catalog_gen.py`, a small
  AppStream-free generator that finds Termux packages shipping `.desktop`
  launchers (x11 via the Contents index, TUR via a GUI-dependency shortlist),
  extracts their desktop metadata and icons, and applies the curated
  `data/native-overrides.json` (per-package names, descriptions, categories,
  run commands, and terminal-app exceptions).

To tweak how a repo package appears in the store, edit
`data/native-overrides.json` — do not add a manual `apps/` folder for packages
that exist in the Termux repos.

## Installation

### Pre-installed in my [Termux-Desktop](https://github.com/sabamdarif/termux-desktop) setup

### Or to install it manually, go to the [Releases](https://github.com/sabamdarif/Termux-AppStore/releases) section and download appropriate package

---

## Support the Project

If you find this project helpful and would like to support its development, consider buying me a coffee! Your support helps maintain and improve this project.

**Cryptocurrency Donations:**

- **USDT (BEP20,ERC20):** `0x1d216cf986d95491a479ffe5415dff18dded7e71`
- **USDT (TRC20):** `TCjRKPLG4BgNdHibt2yeAwgaBZVB4JoPaD`
- **BTC:** `13Q7xf3qZ9xH81rS2gev8N4vD92L9wYiKH`
- **DOGE:** `DJkMCnBAFG14TV3BqZKmbbjD8Pi1zKLLG6`
- **ETH:** `0x1d216cf986d95491a479ffe5415dff18dded7e71`

_Every contribution, no matter how small, helps keep this project alive and growing! ❤️_

---

## Acknowledgments:

Special thanks to:

- [Pi-Appps](https://github.com/Botspot/pi-apps)
- [phoenixbyrd/App-Installer](https://github.com/phoenixbyrd/App-Installer)
- [taleinat/fuzzysearch](https://github.com/taleinat/fuzzysearch) — the bundled `termux_appstore/fuzzysearch.py` module is a lightweight pure-Python port of this library (MIT License, Copyright (c) 2013-2024 taleinat).
