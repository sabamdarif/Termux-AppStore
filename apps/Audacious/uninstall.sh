#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing audacious..."

package_remove_and_check "audacious"

progress_done
