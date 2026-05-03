#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing video-downloader..."
package_remove_and_check "video-downloader"
progress_done
