project(
  'termux-appstore',
  version: '0.5.4.1',
  meson_version: '>= 0.59.0',
  license: 'GPL-3.0-or-later',
)

app_id = 'org.sabamdarif.termux.appstore'
app_name = 'Termux AppStore'

# Modules
python = import('python')
gnome = import('gnome')
i18n = import('i18n')

py_installation = python.find_installation('python3', required: true)

if not py_installation.language_version().version_compare('>= 3.10')
  error('Python 3.10 or newer is required.')
endif

# Program Dependencies
find_program('aria2c', required: false)

# System Library Dependencies
dependency('glib-2.0', version: '>= 2.88.0', required: true)
dependency('gobject-introspection-1.0', version: '>= 1.86.0', required: true)
dependency('gtk+-3.0', version: '>= 3.24.52', required: true)
dependency('pygobject-3.0', version: '>= 3.56.2', required: true)

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

# Generate config files with build-time variables
conf_data = configuration_data()
conf_data.set('PREFIX', get_option('prefix'))
conf_data.set('APP_VERSION', meson.project_version())
conf_data.set('APP_NAME', app_name)
conf_data.set('APP_ID', app_id)

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
configure_file(
  input: 'data/org.sabamdarif.termux.appstore.desktop.in',
  output: 'org.sabamdarif.termux.appstore.desktop',
  configuration: conf_data,
  install: true,
  install_dir: get_option('prefix') / 'share' / 'applications',
)

# Install icon
install_data(
  'data/org.sabamdarif.termux.appstore.svg',
  install_dir: get_option('prefix') / 'share' / 'icons' / 'hicolor' / 'scalable' / 'apps',
)

# Install launcher script
install_data(
  'termux-appstore',
  install_dir: get_option('prefix') / 'bin',
  install_mode: 'rwxr-xr-x',
)

# Install inbuild_functions (bash API sourced by install/uninstall scripts)
install_data(
  'inbuild_functions/inbuild_functions',
  install_dir: pkgdir / 'inbuild_functions',
)

if not meson.is_cross_build()
  gnome.post_install(
    gtk_update_icon_cache: true,
    update_desktop_database: true,
  )
endif