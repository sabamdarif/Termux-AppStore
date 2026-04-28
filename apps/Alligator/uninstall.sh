#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing alligator..."
package_remove_and_check "alligator"
progress_done
