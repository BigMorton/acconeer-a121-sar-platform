import threading
import time
import os
import numpy as np
import serial.tools.list_ports
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import scrolledtext, messagebox

# Import our isolated subsystems
from hardware.stepper_bus import GantryController
from hardware.radar_payload import AcconeerRadar

class SARDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("SAR Mission Control")
        self.root.geometry("1380x650")

        # Hardware Objects
        self.gantry = None
        self.radar = None
        self.is_scanning = False

        self.setup_ui()

    def setup_ui(self):
        # TOP FRAME: Hardware Connections
        conn_frame = tb.Labelframe(self.root, text="Hardware Bus", padding=10, bootstyle=INFO)
        conn_frame.pack(fill=X, padx=10, pady=5)

        tb.Label(conn_frame, text="Arduino Port:").grid(row=0, column=0, padx=5, pady=5)
        self.port_arduino = tb.StringVar()
        self.cb_arduino = tb.Combobox(conn_frame, textvariable=self.port_arduino, bootstyle=PRIMARY)
        self.cb_arduino.grid(row=0, column=1, padx=5, pady=5)

        tb.Label(conn_frame, text="Radar Port:").grid(row=0, column=2, padx=5, pady=5)
        self.port_radar = tb.StringVar()
        self.cb_radar = tb.Combobox(conn_frame, textvariable=self.port_radar, bootstyle=PRIMARY)
        self.cb_radar.grid(row=0, column=3, padx=5, pady=5)

        self.btn_refresh = tb.Button(conn_frame, text="Refresh Ports", bootstyle=SECONDARY, command=self.refresh_ports)
        self.btn_refresh.grid(row=0, column=4, padx=5)

        self.btn_connect = tb.Button(conn_frame, text="Connect Systems", bootstyle=SUCCESS, command=self.toggle_connection)
        self.btn_connect.grid(row=0, column=5, padx=10)

        self.refresh_ports()

        # MIDDLE FRAME: Radar Parameters
        param_frame = tb.Labelframe(self.root, text="Radar Parameters", padding=10, bootstyle=WARNING)
        param_frame.pack(fill=X, padx=10, pady=5)

        tb.Label(param_frame, text="Start Distance (mm):").grid(row=0, column=0, padx=5)
        self.val_start = tb.Entry(param_frame, width=10)
        self.val_start.insert(0, "200") # Default
        self.val_start.grid(row=0, column=1, padx=5)

        tb.Label(param_frame, text="Scan Depth (mm):").grid(row=0, column=2, padx=5)
        self.val_depth = tb.Entry(param_frame, width=10)
        self.val_depth.insert(0, "500") # Default
        self.val_depth.grid(row=0, column=3, padx=5)

        tb.Label(param_frame, text="Total Scan Positions:").grid(row=0, column=4, padx=5)
        self.val_positions = tb.Entry(param_frame, width=10)
        self.val_positions.insert(0, "1400") # Default for 1.4m rail
        self.val_positions.grid(row=0, column=5, padx=5)

        # CONTROLS FRAME
        ctrl_frame = tb.Frame(self.root, padding=10)
        ctrl_frame.pack(fill=X, padx=10)

        self.btn_cal = tb.Button(ctrl_frame, text="Calibrate Rail (C)", bootstyle=DANGER, state=DISABLED, command=self.cmd_calibrate)
        self.btn_cal.pack(side=LEFT, fill=X, expand=True, padx=5)

        self.btn_scan = tb.Button(ctrl_frame, text="START SAR SCAN", bootstyle=SUCCESS, state=DISABLED, command=self.start_scan_thread)
        self.btn_scan.pack(side=LEFT, fill=X, expand=True, padx=5)

        # LOGGING FRAME
        log_frame = tb.Frame(self.root, padding=10)
        log_frame.pack(fill=BOTH, expand=True)
        self.log_area = scrolledtext.ScrolledText(log_frame, font=("Consolas", 9))
        self.log_area.pack(fill=BOTH, expand=True)

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.cb_arduino['values'] = ports
        self.cb_radar['values'] = ports
        if len(ports) >= 2:
            self.cb_arduino.current(0)
            self.cb_radar.current(1)
        elif len(ports) == 1:
            self.cb_arduino.current(0)

    def log(self, msg):
        timestamp = time.strftime("[%H:%M:%S] ")
        self.log_area.insert(END, f"{timestamp}{msg}\n")
        self.log_area.see(END)

    def toggle_connection(self):
        if self.gantry and self.gantry.isConnected:
            self.disconnect_systems()
        else:
            self.connect_systems()

    def connect_systems(self):
        port_ard = self.port_arduino.get()
        port_rad = self.port_radar.get()

        if port_ard == port_rad:
            messagebox.showerror("Port Error", "Arduino and Radar cannot share the same COM port!")
            return

        self.log("Initialising Systems...")
        
        # Instantiate our classes
        self.gantry = GantryController(port_ard)
        self.radar = AcconeerRadar(port_rad, log_callback=self.log)


        # Connect Gantry
        success_ard, msg_ard = self.gantry.connect()
        self.log(f"Arduino: {msg_ard}")

        if success_ard:
            self.btn_connect.config(text="Disconnect Systems", bootstyle=DANGER)
            self.btn_cal.config(state=NORMAL)
            self.btn_scan.config(state=NORMAL)
        else:
            self.gantry = None

    def disconnect_systems(self):
        if self.gantry: self.gantry.disconnect()
        if self.radar: self.radar.stop_and_disconnect()
        
        self.gantry = None
        self.radar = None
        self.btn_connect.config(text="Connect Systems", bootstyle=SUCCESS)
        self.btn_cal.config(state=DISABLED)
        self.btn_scan.config(state=DISABLED)
        self.log("Systems disconnected safely.")

    def cmd_calibrate(self):
        if self.gantry:
            self.gantry.command_calibrate()
            self.log(">>> Sent Calibration Command.")

    # SAR SCAN CONTROL SEQUENCE
    def start_scan_thread(self):
        if self.is_scanning: return
        self.is_scanning = True
        self.btn_scan.config(state=DISABLED, text="SCANNING...")
        self.btn_cal.config(state=DISABLED)
        
        # Launch background thread so GUI doesn't freeze
        threading.Thread(target=self.execute_sar_scan, daemon=True).start()

    def execute_sar_scan(self):
        try:
            # 1. Read parameters from GUI
            start_mm = float(self.val_start.get())
            depth_mm = float(self.val_depth.get())
            total_positions = int(self.val_positions.get())

            # 2. Motor Math
            # For example, 31,160 microsteps / 1400 positions = 22.257 microsteps per position
            # microsteps value received from arduino calibration response, total_positions from GUI input
            microsteps_per_position = self.gantry.total_rail_microsteps / total_positions
            microstep_error_accumulator = 0.0

            # 2. Setup Radar
            self.log(f"Configuring Radar: Start {start_mm}mm, Depth {depth_mm}mm...")
            success, msg = self.radar.setup_and_start(start_mm, depth_mm)
            if not success:
                self.log(msg)
                raise Exception("Radar setup failed.")
            
            self.log(f"Radar locked! True Step: {self.radar.true_step_mm:.3f}mm")

            # 3. The Stop-and-Go Loop
            raw_iq_data = []
            self.log(f"Beginning {total_positions}-step SAR acquisition...")

            for step in range(total_positions):
                if not self.is_scanning: break # Allow early abort

                # Calculate microsteps for this position, including error compensation
                ideal_microsteps = microsteps_per_position + microstep_error_accumulator
                actual_microsteps = int(ideal_microsteps)
                microstep_error_accumulator = ideal_microsteps - actual_microsteps

                self.gantry.command_move(actual_microsteps)
                
                # Wait for TRIGGER with timeout failsafe
                trigger_received = False
                timeout = time.time() + 5.0 # 5 second timeout per step
                
                while time.time() < timeout:
                    reply = self.gantry.check_for_trigger()
                    if reply == "TRIGGER":
                        trigger_received = True
                        break
                    time.sleep(0.01)

                if not trigger_received:
                    self.log(f"ERROR: Step {step} timed out waiting for Arduino.")
                    raise Exception("Motor Timeout")

                # Grab frame instantly
                frame = self.radar.grab_frame()
                if frame is not None:
                    raw_iq_data.append(frame[0]) # Append the 1D array
                
                if step % 50 == 0:
                    self.log(f"Progress: {step}/{total_positions} steps complete.")

            # 4. Shutdown and Save
            self.log("Scan complete. Shutting down payload...")
            self.radar.stop_and_disconnect()

            # Save the matrix to storage
            matrix = np.array(raw_iq_data)
            os.makedirs("data/raw_scans", exist_ok=True)
            filename = f"data/raw_scans/sar_data_{int(time.time())}.npy"
            np.save(filename, matrix)
            
            self.log(f"SUCCESS: Radar Matrix {matrix.shape} saved to {filename}")
            self.log("Pass this file to your Back-Projection algorithm!")

        except Exception as e:
            self.log(f"SCAN ABORTED: {e}")
            if self.radar: self.radar.stop_and_disconnect()

        finally:
            self.is_scanning = False
            self.btn_scan.config(state=NORMAL, text="START SAR SCAN")
            self.btn_cal.config(state=NORMAL)