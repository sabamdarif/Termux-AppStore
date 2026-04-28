#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing hangover..."

package_remove_and_check "hangover"

progress_done

