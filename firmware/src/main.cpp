#include <Arduino.h>
#include <TMCStepper.h>
#include <AccelStepper.h>

// Serial Definitions 
#define USB_SERIAL Serial   // USB-C Serial Connection
#define SERIAL_PORT Serial0 // Nano ESP32 HardwareSerial port

// Pin Definitons
#define DIR_PIN           D3 // Direction
#define STEP_PIN          D4 // Step
#define EN_PIN            D5 // Enable
#define START_PIN         D9 // Start Limit Switch (Normally Open, Connects to GND when triggered)
#define MAX_PIN           D10// End Limit Switch (Normally Open, Connects to GND when triggered)

// Settings
#define DRIVER_ADDRESS 0b00 // TMC2209 Driver address according to MS1 and MS2
#define R_SENSE 0.11f       // 110 mOhm (from datasheet)
#define MAX_SPEED 2000      // Steps per second
#define ACCELERATION 1000   // Steps/sec^2 (Lower this if gantry shakes)

TMC2209Stepper driver(&SERIAL_PORT, R_SENSE, DRIVER_ADDRESS);
AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

long maxGantrySteps = 0; // Set in calibrateGantry() after reading limit switches

void calibrateGantry()
{
  USB_SERIAL.println("STATUS: Homing to end of rail...");
  stepper.setSpeed(-800);
  while (digitalRead(MAX_PIN) == LOW)  // Move towards end until end limit switch triggered
  {
    stepper.runSpeed();
  }

  // Set current position (END) as 0
  stepper.setCurrentPosition(0);

  // Back off a little from the switch
  stepper.runToNewPosition(200);
  stepper.setCurrentPosition(0);  // Reset end point after backing off
  USB_SERIAL.println("STATUS: End point calibrated at 0");

  // Move towards start until start limit switch triggered, counting steps to find max travel distance
  USB_SERIAL.println("STATUS: Homing to start of rail...");
  stepper.setSpeed(800);
  while (digitalRead(START_PIN) == LOW)
  {
    stepper.runSpeed();
  }

  maxGantrySteps = (stepper.currentPosition() - 200);  // Store max travel distance in steps
  
  // Send machine-readable calibration to Python
  USB_SERIAL.print("Start point calibrated. Total Steps:"); 
  USB_SERIAL.println(maxGantrySteps);
  
  stepper.runToNewPosition(maxGantrySteps);  // Move to safe start point
  USB_SERIAL.println("READY");
}

void setup() {
  // Pin Setup
  pinMode(EN_PIN, OUTPUT);
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(START_PIN, INPUT_PULLUP);  // Limit switch pins with pullup resistors
  pinMode(MAX_PIN, INPUT_PULLUP);    // Limit switch pins with pullup resistors
  digitalWrite(EN_PIN, LOW);       // Enable driver in hardware

  // Serial Communication Setup
  USB_SERIAL.begin(115200);       // Python-on-PC Communication over USB C
  SERIAL_PORT.begin(115200);      // HW UART drivers for stepper driver

  // Initialise TMC2209
  driver.begin();
  driver.toff(5);                 // Enables driver in software (Any value from 1-15)
  driver.rms_current(600);        // Set motor RMS current (TMC2209 2A max)
  driver.microsteps(16);          // Set microsteps to 1/16th

  // Use spreadCycle for higher accuracy 
  driver.en_spreadCycle(true);    // Toggle spreadCycle on or off (for stealthchop)
  driver.pwm_autoscale(true);     // Needed for stealthChop

  // Initialise Motion Controller (AccelStepper)
  stepper.setMaxSpeed(MAX_SPEED);
  stepper.setAcceleration(ACCELERATION);

  USB_SERIAL.println("READY");
}

void loop() {
  // Handle Motion
  stepper.run();           // Called as fast as possible, checks "time to take step?" and returns immediately

  // Listen for Python Command
  if (USB_SERIAL.available() > 0)
    {
      char cmd = USB_SERIAL.read();

      if (cmd == 'M')       // 'M' for "move"
      {
        // Parse the integer following the 'M' (e.g., M22) sent by the Python Anti-Drift logic
        long microstepsToMove = USB_SERIAL.parseInt();

        if (stepper.distanceToGo() == 0)  // Only accept a new move if we are currently stopped
        {
          stepper.move(microstepsToMove);
        }
      }
      else if (cmd == 'C')
      {
        calibrateGantry();  // Recalibrate gantry if needed
      }
    }

  // Tell PC to trigger radar when movement finished and stopped
  static bool wasMoving = false;
  bool isMoving = (stepper.distanceToGo() != 0);  // True if moving, false if not

  if (wasMoving && !isMoving)
  {
    // Arrived at target position
    delay(200);     // 200ms delay for dampening and waiting for vibrations to settle

    USB_SERIAL.println("TRIGGER"); // Tell Python to fire radar
  }
  wasMoving = isMoving;   // Reset falling edge detection
}