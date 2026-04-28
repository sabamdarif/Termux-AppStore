#!/bin/bash

progress_phase "cleanup" 0 "Removing vlc-qt..."
pkg remove vlc-qt -y
progress_done

