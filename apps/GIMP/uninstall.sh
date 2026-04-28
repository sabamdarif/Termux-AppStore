#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing gimp..."

package_remove_and_check "gimp"

progress_done

