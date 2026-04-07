from acconeer.exptool import a121
import serial

class AcconeerRadar:
    def __init__(self, port, log_callback=None):
        self.log = log_callback if log_callback else print
        self.port = port
        self.client = None
        self.true_step_mm = None
        self.true_start_mm = None
    
    # Set up the radar session with specified parameters and begin. 
    # Reads back the true step and start values from the radar metadata for later use in backprojection.
    def setup_and_start(self, start_mm=200.0, depth_mm=500.0):
        self.log(f"Configuring Radar: Start {start_mm}mm, Depth {depth_mm}mm...")
        
        try:
            self.client = a121.Client.open(serial_port=self.port)

            # Create the Sensor Configuration
            sensor_config = a121.SensorConfig()

            # Profile 3 is generally the best balance of range and resolution for lab-scale SAR
            sensor_config.profile = a121.Profile.PROFILE_3 

            # Convert millimetres to Acconeer 'points' (~2.5mm per point)
            # We use round() to ensure we snap to the nearest valid hardware step
            step_length_mm = 2.5 
            sensor_config.start_point = int(round(start_mm / step_length_mm))
            sensor_config.num_points = int(round(depth_mm / step_length_mm))
            
            
            
            # Wrap it in a Session Configuration
            session_config = a121.SessionConfig(sensor_config)
            
            # Setup the Client Session 
            # (This is where your code was failing. We just save the metadata, we don't call .session_config on it)
            self.metadata = self.client.setup_session(session_config)

            # We use the metadata to find the EXACT physical distances the hardware snapped to
            true_step_m = metadata.session_config.sensor_config.step_length_m
            self.true_step_mm = true_step_m * 1000.0
            self.true_start_mm = (metadata.session_config.sensor_config.start_point * true_step_m) * 1000.0
            
            # Start the Session
            self.client.start_session()
            
            return True, "Radar setup complete and session started successfully."
            
        except serial.SerialException:
            return False, f"Could not open {self.port}. Is it in use by another script?"
        except Exception as e:
            return False, f"Radar setup error: {e}"
                    
    # Function to grab a single frame of complex (IQ)radar data.
    def grab_frame(self):
        if self.client:
            result = self.client.get_next()
            return result.frame
        return None
    
    # Clean disconnection method to stop radar session and close connection
    def stop_and_disconnect(self):
        if self.client:
            try:
                self.client.stop_session()
            except Exception:
                pass
            try:
                self.client.close()
            except Exception:
                pass