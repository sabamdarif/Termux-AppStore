#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing gwenview..."

package_remove_and_check "gwenview"

progress_done
