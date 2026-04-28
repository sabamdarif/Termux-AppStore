#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing kate..."

package_remove_and_check "kate"

progress_done
