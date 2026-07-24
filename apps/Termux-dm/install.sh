#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="termux-dm"
run_cmd="termux-dm"
version="v6-LTS"
app_type="native"

sha256="9b7494a37d3e9ce2788c427a2a03b42b493ce88496e3ac02bb1e7bfaddf72f54"

package_install_and_check "xdotool python libpng libjpeg-turbo python-tkinter python-pillow"
install_deb_into_termux "https://github.com/Superchavo/termux-display-manager-repo/raw/refs/heads/master/TermuxDM-${version}-Codenamed-Morano.deb"
