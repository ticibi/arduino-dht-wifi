#include <SPI.h>
#include <RF24.h>
#include "DHT.h"

// DHT sensor definitions
#define DHTPIN 2           // DHT sensor data pin
#define DHTTYPE DHT11      // DHT 22 (AM2302); change if using DHT11
DHT dht(DHTPIN, DHTTYPE);

// nRF24L01 definitions
#define CE_PIN 9           // CE pin connected to Arduino digital pin 9
#define CSN_PIN 10         // CSN pin connected to Arduino digital pin 10
RF24 radio(CE_PIN, CSN_PIN);
const byte address[6] = "00001";  // Define the writing pipe address

// Define a structure to hold sensor data
struct SensorData {
  float humidity;
  float temperatureC;
  float temperatureF;
};

void setup() {
  Serial.begin(9600);
  Serial.println("DHT Sensor with nRF24L01 Transmitter");

  // Initialize the DHT sensor
  dht.begin();

  // Initialize the nRF24L01 transceiver
  if (!radio.begin()) {
    Serial.println("nRF24L01 radio hardware is not responding!");
    while (1) {} // halt if radio hardware is not found
  }
  
  radio.openWritingPipe(address);     // Set the address for the writing pipe
  radio.setPALevel(RF24_PA_LOW);        // Set power level (adjust as needed)
  radio.stopListening();                // Configure as transmitter
}

void loop() {
  // Wait 2 seconds between measurements
  delay(2000);

  // Read data from the DHT sensor
  float humidity = dht.readHumidity();
  float temperatureC = dht.readTemperature();
  float temperatureF = dht.readTemperature(true); // Read in Fahrenheit

  // Check if any reads failed and exit early (to try again)
  if (isnan(humidity) || isnan(temperatureC) || isnan(temperatureF)) {
    Serial.println("Failed to read from DHT sensor!");
    return;
  }

  // Print sensor readings to the Serial Monitor
  Serial.print("Humidity: ");
  Serial.print(humidity);
  Serial.print(" %\t");
  Serial.print("Temperature: ");
  Serial.print(temperatureC);
  Serial.print(" *C / ");
  Serial.print(temperatureF);
  Serial.println(" *F");

  // Package the sensor data into the struct
  SensorData data;
  data.humidity = humidity;
  data.temperatureC = temperatureC;
  data.temperatureF = temperatureF;

  // Transmit the sensor data over nRF24L01
  bool success = radio.write(&data, sizeof(data));
  if (success) {
    Serial.println("Data sent successfully");
  } else {
    Serial.println("Data transmission failed");
  }
}
