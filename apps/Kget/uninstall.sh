#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing kget..."
package_remove_and_check "kget"
progress_done
