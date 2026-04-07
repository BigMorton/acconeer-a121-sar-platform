from acconeer.exptool import a121
import serial
import time

class AcconeerRadar:
    def __init__(self, port, log_callback=None):
        self.log = log_callback if log_callback else print
        self.port = port
        self.client = None
        self.true_step_mm = 2.5023  # Professional fallback
        self.true_start_mm = None

    def setup_and_start(self, start_mm=200.0, depth_mm=500.0):
        try:
            # 1. Establish connection
            self.client = a121.Client.open(serial_port=self.port)
            
            # --- NEW: THE PROTOCOL STABILIZER ---
            # Wait 0.5s for initial startup logs to finish sending
            time.sleep(0.5) 
            
            # 2. Configuration
            sensor_config = a121.SensorConfig()
            sensor_config.profile = a121.Profile.PROFILE_3 
            
            # Map distance to hardware indices
            sensor_config.start_point = int(round(start_mm / 2.5023))
            sensor_config.num_points = int(round(depth_mm / 2.5023))
            
            # 3. Setup Session
            session_config = a121.SessionConfig(sensor_config)
            
            # We wrap setup and start in a retry loop to skip "Log" collisions
            metadata = None
            for attempt in range(3):
                try:
                    metadata = self.client.setup_session(session_config)
                    break 
                except Exception as e:
                    if "header" in str(e).lower():
                        self.log(f"Syncing... (Attempt {attempt+1})")
                        time.sleep(0.2)
                        continue
                    raise e

            # 4. Extract Truth (Metadata handling)
            try:
                if metadata and hasattr(metadata, 'base_step_length_m'):
                    step_m = metadata.base_step_length_m
                else:
                    step_m = 0.0025023
                self.true_step_mm = step_m * 1000.0
            except:
                self.log(f"Metadata Note: Using fallback bin size ({self.true_step_mm}mm)")

            self.true_start_mm = (sensor_config.start_point * (self.true_step_mm / 1000.0)) * 1000.0
            
            # 5. Start Radar
            self.client.start_session()
            
            return True, f"Radar Ready. Bin size: {self.true_step_mm:.3f}mm"
            
        except Exception as e:
            self.stop_and_disconnect()
            return False, f"Radar setup error: {str(e)}"
                    
    def grab_frame(self):
        try:
            if self.client:
                result = self.client.get_next()
                return result.frame
        except Exception:
            return None
    
    def stop_and_disconnect(self):
        if self.client:
            try:
                self.client.stop_session()
                self.client.close()
            except:
                pass
            self.client = None