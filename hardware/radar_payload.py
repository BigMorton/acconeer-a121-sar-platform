from acconeer.exptool import a121
import serial
import time
import threading

class AcconeerRadar:
    def __init__(self, port, log_callback=None):
        self.log = log_callback if log_callback else print
        self.port = port
        self.client = None
        self.true_step_mm = 2.5023
        self.true_start_mm = None
        
        # Threading variables
        self.latest_frame = None
        self.stream_active = False
        self.worker_thread = None

    def setup_and_start_stream(self, start_mm=200.0, depth_mm=500.0):
        try:
            self.client = a121.Client.open(serial_port=self.port,override_baudrate=115200)
            time.sleep(0.5) 
            
            sensor_config = a121.SensorConfig()
            sensor_config.profile = a121.Profile.PROFILE_3
            sensor_config.sweeps_per_frame = 1
            sensor_config.frame_rate = 5.0  # Constant 5Hz stream
            
            sensor_config.start_point = int(round(start_mm / 2.5023))
            sensor_config.num_points = int(round(depth_mm / 2.5023))
            
            session_config = a121.SessionConfig(sensor_config)
            
            # Setup the session
            metadata = None
            for attempt in range(3):
                try:
                    metadata = self.client.setup_session(session_config)
                    break 
                except Exception as e:
                    if "header" in str(e).lower():
                        time.sleep(0.2)
                        continue
                    raise e

            try:
                if metadata and hasattr(metadata, 'base_step_length_m'):
                    self.true_step_mm = metadata.base_step_length_m * 1000.0
                else:
                    self.true_step_mm = 2.5023
            except: pass

            self.true_start_mm = (sensor_config.start_point * (self.true_step_mm / 1000.0)) * 1000.0
            
            # Start the session for the duration of the scan
            self.client.start_session()
            
            # Launch the background consumer thread
            self.stream_active = True
            self.worker_thread = threading.Thread(target=self._stream_worker, daemon=True)
            self.worker_thread.start()
            
            return True, f"Radar Streaming. Bin size: {self.true_step_mm:.3f}mm"
            
        except Exception as e:
            self.stop_and_disconnect()
            return False, f"Radar setup error: {str(e)}"
            
    def _stream_worker(self):
        # Constantly receives frames from the buffer so it never overflows.
        while self.stream_active and self.client:
            try:
                result = self.client.get_next()
                # Constantly overwrite with the absolute newest frame
                self.latest_frame = result.frame 
            except Exception as e:
                # If it drops a frame, just wait for the next one
                self.log(f"STREAM ERROR: {repr(e)}")
                time.sleep(0.01)
                
    def grab_fresh_frame(self):
        # Called by the GUI. Clears the last frame and waits for a fresh one.
        if not self.stream_active: return None
        
        # 1. Nullify the old frame (which was taken while the motor was moving)
        self.latest_frame = None 
        
        # 2. Wait for the background thread to grab the NEXT stationary frame
        # At 10Hz, this should take a maximum of 0.1 seconds
        timeout = time.time() + 1.5 
        while self.latest_frame is None and time.time() < timeout:
            time.sleep(0.01)
            
        return self.latest_frame

    def stop_and_disconnect(self):
        self.stream_active = False # 1. Signal the thread it's time to die
        
        if self.client:
            # 2. Stop the session FIRST. 
            # This safely interrupts the background thread if it's stuck waiting in get_next()
            try: 
                self.client.stop_session() 
            except: 
                pass
            
            # 3. Give the background thread time to catch the interruption and exit
            time.sleep(0.3) 
            
            # 4. Now it is safe to completely destroy the client connection
            try: 
                self.client.close()
            except: 
                pass
            
        self.client = None