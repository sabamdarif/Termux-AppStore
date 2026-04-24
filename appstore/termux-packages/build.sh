TERMUX_PKG_HOMEPAGE=https://github.com/sabamdarif/Termux-AppStore
TERMUX_PKG_DESCRIPTION="A simple gtk3 appstore for Termux"
TERMUX_PKG_LICENSE="GPL-3.0"
TERMUX_PKG_MAINTAINER="@sabamdarif"
TERMUX_PKG_VERSION="@VERSION@"
TERMUX_PKG_SRCURL="git+https://github.com/sabamdarif/Termux-AppStore"
TERMUX_PKG_DEPENDS="python, pygobject, python-pillow, python-pip, gtk3, glib, aria2, gobject-introspection"
TERMUX_PKG_BUILD_DEPENDS="pkg-config, xorgproto"
TERMUX_PKG_PYTHON_RUNTIME_DEPS="fuzzysearch"

termux_step_post_get_source() {
	cd "$TERMUX_PKG_SRCDIR"
	find . -mindepth 1 -maxdepth 1 ! -name 'appstore' ! -name '.git' -exec rm -rf {} +
}

termux_step_configure() {
	TERMUX_PKG_SRCDIR="$TERMUX_PKG_SRCDIR/appstore"
	TERMUX_PKG_BUILDDIR="$TERMUX_PKG_SRCDIR/build"
	termux_setup_meson
	termux_step_configure_meson
}
