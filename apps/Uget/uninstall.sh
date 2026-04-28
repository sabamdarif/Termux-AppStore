#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing uget..."

package_remove_and_check "uget"

progress_done
