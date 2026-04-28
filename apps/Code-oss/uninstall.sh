#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing code-oss..."

package_remove_and_check "code-oss"

progress_done

