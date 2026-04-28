#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing xpdf..."

package_remove_and_check "xpdf"

progress_done
