#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing qbittorrent..."

package_remove_and_check "qbittorrent"

progress_done
