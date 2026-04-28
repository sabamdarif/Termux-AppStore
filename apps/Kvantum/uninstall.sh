#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing kvantum..."

package_remove_and_check "kvantum"

progress_done
