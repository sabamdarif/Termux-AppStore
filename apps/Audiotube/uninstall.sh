#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing audiotube..."

package_remove_and_check "audiotube"

progress_done
