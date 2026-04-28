#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing darktable..."
package_uninstall "darktable"
progress_done
