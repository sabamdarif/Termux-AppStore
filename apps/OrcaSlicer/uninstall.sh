#!/data/data/com.termux/files/usr/bin/bash


# Uninstall OrcaSlicer
pdrun sudo apt remove -y orcaslicer
pdrun sudo apt autoremove -y

echo "OrcaSlicer has been uninstalled."
