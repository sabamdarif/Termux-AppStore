#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing spotofy-qt..."

package_remove_and_check "spotofy-qt"

progress_done
