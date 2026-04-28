#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing atril..."

package_remove_and_check "atril"

progress_done
