import time
import json
import ast
from hiwonder_servo_controller import *
from gpio import *

class MotionManager:
    runningAction = False
    stopRunning = False

    def __init__(self, serial_port='/dev/ttySC2', baudrate=115200):
        self.servo_control = HiwonderServoController(serial_port, baudrate)

    def set_servos_position(self, duration, *args):
        self.servo_control.set_servos_position(duration, args)

    def get_servos_position(self, *args):
        return self.servo_control.get_servos_position(args)

    def stop_action_group(self):
        self.stopRunning = True
    
    def run_action(self, action):
        # Load JSON data for the specified action
        with open("./json_data/"+action+".json", 'r') as file:
            action_data = json.load(file)

        self.stopRunning = False
        self.runningAction = True

        # Iterate through each step in the action data
        for step in action_data:
            if self.stopRunning:
                self.stopRunning = False
                break
            #with open("./json_data/"+current+".json", 'r') as file:
            #    action_data = json.load(file)
            # Duration is stored with key "0" in each step
            duration = step.get("0")
            # Positions for each servo
            #breakpoint()
            positions = [[int(servo_id), position] for servo_id, position in step.items() if servo_id != "0"]
            self.set_servos_position(duration, positions)
            time.sleep(float(duration)/1000.0)
            #with open("./json_data/"+current+".json", 'w') as file:
            #    action_data = json.dumps(step, file)

        self.runningAction = False

if __name__ == '__main__':
    motion_manager = MotionManager()

    # Run different actions by specifying paths to their JSON files
    motion_manager.run_action('greet')  # Replace with actual path
