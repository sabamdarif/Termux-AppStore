#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing gedit..."
package_uninstall "gedit"
progress_done
