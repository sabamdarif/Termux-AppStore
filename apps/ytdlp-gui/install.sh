#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="ytdlp-gui"
run_cmd="yt-dlp-gui"
version="3.5"
app_type="native"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
declare -A sha256=(
	["logo.png"]="c75ccb9642c32fcd06037ac04e8b407723a01e0e0855446cbb71a87a8251412e"
	["yt-dlp-gui"]="15d01ed24a0f64b547b044d8faf189354174dc60b9f22190a5476180a013e5c5"
)
progress_phase "prepare" 0 "Preparing to install ytdlp-gui..."
package_install_and_check "python-yt-dlp ffmpeg yad atomicparsley xsel xclip"
progress_done

check_and_create_directory "$HOME/.local/bin/"
download_file "$HOME/.local/bin/yt-dlp-gui" "https://raw.githubusercontent.com/sabamdarif/Termux-AppStore/refs/heads/main/apps/ytdlp-gui/bin/yt-dlp-gui"
chmod +x "$HOME/.local/bin/yt-dlp-gui"
check_and_create_directory "$HOME/.config/ytdlp-gui/"
download_file "$HOME/.config/ytdlp-gui/logo.png" "https://raw.githubusercontent.com/sabamdarif/Termux-AppStore/refs/heads/main/apps/ytdlp-gui/logo.png"

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${TERMUX_PREFIX}/share/applications/ytdlp-gui.desktop >/dev/null
[Desktop Entry]
Name=YtDlp GUI
Exec=$HOME/.local/bin/yt-dlp-gui
Terminal=false
Type=Application
Icon=$HOME/.config/ytdlp-gui/logo.png
StartupWMClass=youtube-music
Comment=youtube-music
MimeType=x-scheme-handler/yad;
Categories=Multimedia;
DESKTOP_EOF
