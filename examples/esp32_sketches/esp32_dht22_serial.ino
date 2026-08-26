/**
 * ESP32 DHT22 Temperature/Humidity Sensor Example
 * 
 * Hardware:
 * - ESP32 DevKit
 * - DHT22 sensor (or DHT11)
 *   - VCC -> 3.3V
 *   - GND -> GND
 *   - DATA -> GPIO 4
 * 
 * Install DHT sensor library:
 * Arduino IDE -> Tools -> Manage Libraries -> Search "DHT sensor library"
 */

#include <DHT.h>

#define DHTPIN 4        // GPIO 4
#define DHTTYPE DHT22   // DHT 22 (AM2302)

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(115200);
  dht.begin();
  
  // Wait for serial to stabilize
  delay(2000);
  Serial.println("{\"status\":\"ready\",\"sensor\":\"dht22\"}");
}

void loop() {
  // Reading takes about 250ms
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature(); // Celsius
  
  // Check if readings failed
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("{\"error\":\"sensor_read_failed\"}");
    delay(2000);
    return;
  }
  
  // Send as JSON for easy parsing
  Serial.print("{");
  Serial.print("\"temperature_c\":");
  Serial.print(temperature, 2);
  Serial.print(",\"humidity_pct\":");
  Serial.print(humidity, 2);
  Serial.print(",\"timestamp\":");
  Serial.print(millis());
  Serial.println("}");
  
  delay(2000); // Read every 2 seconds (DHT22 limitation)
}
