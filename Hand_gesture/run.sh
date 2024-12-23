#!/bin/bash

# Run the Python script in the background
chmod 777 /sys/class/gpio/export
cd ~/A55_GPIO
python3 gesture.py &

# Wait for 3 seconds, then run the shell command with an argument in the background
(sleep 3 && cd ~/Hand_Gesture_Recognition/exe_v2h && ./hand_gesture USB) &

