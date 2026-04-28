#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing shotcut jack jack2 jack-example-tools..."

package_remove_and_check "shotcut jack jack2 jack-example-tools"

progress_done
