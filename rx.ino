#include <SPI.h>
#include <RF24.h>

// nRF24L01 definitions
#define CE_PIN 9           // CE pin connected to Arduino digital pin 9
#define CSN_PIN 10         // CSN pin connected to Arduino digital pin 10
RF24 radio(CE_PIN, CSN_PIN);
const byte address[6] = "00001";  // Must match the transmitter's address

// Structure matching the transmitter's sensor data format
struct SensorData {
  float humidity;
  float temperatureC;
  float temperatureF;
};

void setup() {
  Serial.begin(9600);
  Serial.println("Receiver: Waiting for sensor data...");
  
  // Initialize the nRF24L01 transceiver
  if (!radio.begin()) {
    Serial.println("nRF24L01 radio hardware is not responding!");
    while (1) {} // Halt if radio hardware is not found
  }
  
  // Open the reading pipe on channel 0 with the same address as the transmitter
  radio.openReadingPipe(0, address);
  radio.setPALevel(RF24_PA_LOW);  // Adjust power level as needed
  radio.startListening();         // Set radio to listening mode
}

void loop() {
  // Check if there is incoming data
  if (radio.available()) {
    SensorData data;
    // Read the data into the structure
    radio.read(&data, sizeof(data));
    
    // Print the received sensor data to the Serial Monitor
    Serial.print("Humidity: ");
    Serial.print(data.humidity);
    Serial.print(" %\t");
    Serial.print("Temperature: ");
    Serial.print(data.temperatureC);
    Serial.print(" *C / ");
    Serial.print(data.temperatureF);
    Serial.println(" *F");
  }
}
