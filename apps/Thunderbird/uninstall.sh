#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing thunderbird..."

package_remove_and_check "thunderbird"

progress_done

