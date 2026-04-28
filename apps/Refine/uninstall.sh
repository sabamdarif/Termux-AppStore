#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing refine..."

package_remove_and_check "refine"

progress_done
