from acconeer.exptool import a121

class AcconeerRadar:
    def __init__(self, port):
        self.port = port
        self.client = None
        self.true_step_mm = None
        self.true_start_mm = None
    
    # Set up the radar session with specified parameters and begin. 
    # Reads back the true step and start values from the radar metadata for later use in backprojection.
    def setup_and_start(self, start_mm=200, depth_mm=250):
        try:
            self.client = a121.Client.open(serial_port=self.port)

            # Translate scan parameters from mm to bin indices
            start_index = int(start_mm / 2.5)  # Assuming 2.5mm per bin
            depth_index = int(depth_mm / 2.5)

            sensor_config = a121.SensorConfig(
                profile=a121.Profile.PROFILE_3, 
                start_point=start_index,
                num_points=depth_index,
                sweeps_per_frame=10,    # These values can be adjusted based on testing needs
                frame_rate=2.0,         # Same here, adjust as needed
            )

            session_config = a121.SessionConfig(sensor_config)
            metadata = self.client.setup_session(session_config)
            self.client.start_session()

            # Store the true physical parameters for later use in backprojection
            # The acconeer radar may slightly adjust the actual start and step size based on hardware capabilities, so we read these back from the metadata.
            true_bin_length_m = metadata.session_config.sensor_config.step_length_m
            self.true_step_mm = true_bin_length_m * 1000  # Convert to mm
            self.true_start_mm = (metadata.session_config.sensor_config.start_point * true_bin_length_m) * 1000.0

            return True, "Radar successfully initialised."
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