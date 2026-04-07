import serial
import time

class GantryController:
    def __init__(self, port, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.isConnected = False

        # Calibration Parameters
        self.total_rail_microsteps = 31160   # Default fallback for 1.4m rail
        self.rail_length_mm = 1400.0       # UPDATE IF RAIL LENGTH CHANGES

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino to reset
            self.ser.reset_input_buffer()
            self.isConnected = True
            return True, f"Connected to {self.port} @ {self.baudrate} baud."
        except Exception as e:
            self.isConnected = False
            return False, f"Connection error: {e}"
        
    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.isConnected = False

    def command_move(self, steps):
        # Tells Arduino to move stepper a specified number of steps.
        if self.isConnected:
            self.ser.write(f'M{int(steps)}\n'.encode('utf-8'))  # Send move command with steps
    
    def command_calibrate(self):
        if self.isConnected:
            self.ser.write(b'C\n')  # Send calibrate command

    def parse_calibration(self, raw_string):
        # Extract step count from Arduino's calibration response and update internal parameters
        try:
            parts = raw_string.split(":")
            if len(parts) == 2 and parts[0].strip() == "Start point calibrated. Total Steps:":
                self.total_rail_steps = int(parts[1].strip())
                return True, self.total_rail_steps
        except Exception as e:
                pass
        return False, 0
        

    def check_for_trigger(self):
        if self.isConnected and self.ser.in_waiting > 0:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                return line
            except Exception:
                return None
        return None
    