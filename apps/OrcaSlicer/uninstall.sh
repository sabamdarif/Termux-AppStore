#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing orcaslicer..."

# Uninstall OrcaSlicer
pdrun sudo apt remove -y orcaslicer
pdrun sudo apt autoremove -y

echo "OrcaSlicer has been uninstalled."
progress_done
