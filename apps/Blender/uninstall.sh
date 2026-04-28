#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing blender..."

package_remove_and_check "blender"

progress_done
