project(
  'termux-appstore',
  version: '0.5.4.1',
  meson_version: '>= 0.59.0',
  license: 'GPL-3.0-or-later',
)

# Python module
python = import('python')
py_installation = python.find_installation('python3')

# Package sources — main package
termux_appstore_sources = files(
  'termux_appstore/__init__.py',
  'termux_appstore/__main__.py',
  'termux_appstore/application.py',
  'termux_appstore/constants.py',
  'termux_appstore/main.py',
  'termux_appstore/utils.py',
  'termux_appstore/window.py',
)

# Backend sub-package
termux_appstore_backend_sources = files(
  'termux_appstore/backend/__init__.py',
  'termux_appstore/backend/app_data.py',
  'termux_appstore/backend/distro.py',
  'termux_appstore/backend/installed_apps.py',
  'termux_appstore/backend/refresh.py',
  'termux_appstore/backend/script_runner.py',
  'termux_appstore/backend/settings.py',
  'termux_appstore/backend/updates.py',
)

# Terminal sub-package
termux_appstore_terminal_sources = files(
  'termux_appstore/terminal/__init__.py',
  'termux_appstore/terminal/ansi_parser.py',
  'termux_appstore/terminal/command_runner.py',
  'termux_appstore/terminal/emulator.py',
)

# UI sub-package
termux_appstore_ui_sources = files(
  'termux_appstore/ui/__init__.py',
  'termux_appstore/ui/app_card.py',
  'termux_appstore/ui/dialogs.py',
  'termux_appstore/ui/header.py',
  'termux_appstore/ui/search.py',
  'termux_appstore/ui/sidebar.py',
)

# Tasks sub-package
termux_appstore_tasks_sources = files(
  'termux_appstore/tasks/__init__.py',
  'termux_appstore/tasks/task_manager.py',
  'termux_appstore/tasks/update_check.py',
)

# Install Python sources
pkgdir = py_installation.get_install_dir() / 'termux_appstore'

# Generate _buildconf.py with build-time PREFIX
conf_data = configuration_data()
conf_data.set('PREFIX', get_option('prefix'))

configure_file(
  input: 'termux_appstore/_buildconf.py.in',
  output: '_buildconf.py',
  configuration: conf_data,
  install: true,
  install_dir: pkgdir,
)

py_installation.install_sources(
  termux_appstore_sources,
  subdir: 'termux_appstore',
)

py_installation.install_sources(
  termux_appstore_backend_sources,
  subdir: 'termux_appstore' / 'backend',
)

py_installation.install_sources(
  termux_appstore_terminal_sources,
  subdir: 'termux_appstore' / 'terminal',
)

py_installation.install_sources(
  termux_appstore_ui_sources,
  subdir: 'termux_appstore' / 'ui',
)

py_installation.install_sources(
  termux_appstore_tasks_sources,
  subdir: 'termux_appstore' / 'tasks',
)

# Install style files alongside the Python package so they are found
# relative to __file__ at runtime.
install_data(
  'style/style.css',
  'style/terminal_style.css',
  install_dir: pkgdir / 'style',
)

# Install desktop file
install_data(
  'org.sabamdarif.termux.appstore.desktop',
  install_dir: get_option('prefix') / 'share' / 'applications',
)

# Install launcher script
install_data(
  'appstore',
  install_dir: get_option('prefix') / 'bin',
  install_mode: 'rwxr-xr-x',
)

# NOTE: Legacy files (gtk_app_store.py, terminal_emulator.py) are
# installed by the bash 'appstore' launcher script via git clone,
# not by meson. They will be removed in Phase 8 (final cutover).
