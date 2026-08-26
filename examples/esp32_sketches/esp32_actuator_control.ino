/**
 * ESP32 with actuator control via Serial commands
 * 
 * Hardware:
 * - ESP32 DevKit
 * - DHT22 on GPIO 4
 * - Built-in LED on GPIO 2 (or external LED)
 * - Optional: Servo on GPIO 5
 * 
 * This sketch:
 * 1. Reads DHT22 and sends JSON over Serial
 * 2. Listens for JSON commands to control actuators
 * 
 * Command format: {"action": "led", "state": "on"}
 */

#include <DHT.h>
#include <ArduinoJson.h>

#define DHTPIN 4
#define DHTTYPE DHT22
#define LED_PIN 2

DHT dht(DHTPIN, DHTTYPE);
unsigned long lastSensorRead = 0;
const long sensorInterval = 2000; // Read every 2 seconds

void setup() {
  Serial.begin(115200);
  dht.begin();
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  delay(2000);
  Serial.println("{\"status\":\"ready\"}");
}

void loop() {
  // Read sensor periodically
  unsigned long currentMillis = millis();
  if (currentMillis - lastSensorRead >= sensorInterval) {
    lastSensorRead = currentMillis;
    
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();
    
    if (!isnan(humidity) && !isnan(temperature)) {
      StaticJsonDocument<128> doc;
      doc["temperature_c"] = temperature;
      doc["humidity_pct"] = humidity;
      doc["timestamp"] = millis();
      
      serializeJson(doc, Serial);
      Serial.println();
    }
  }
  
  // Check for incoming commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    handleCommand(command);
  }
}

void handleCommand(String json) {
  StaticJsonDocument<128> doc;
  DeserializationError error = deserializeJson(doc, json);
  
  if (error) {
    Serial.println("{\"status\":\"error\",\"error\":\"invalid_json\"}");
    return;
  }
  
  const char* action = doc["action"];
  
  if (strcmp(action, "led") == 0) {
    const char* state = doc["state"];
    if (strcmp(state, "on") == 0) {
      digitalWrite(LED_PIN, HIGH);
      Serial.println("{\"status\":\"success\",\"action\":\"led_on\"}");
    } else if (strcmp(state, "off") == 0) {
      digitalWrite(LED_PIN, LOW);
      Serial.println("{\"status\":\"success\",\"action\":\"led_off\"}");
    }
  }
  else if (strcmp(action, "led_pwm") == 0) {
    int value = doc["value"];
    if (value >= 0 && value <= 255) {
      analogWrite(LED_PIN, value);
      Serial.print("{\"status\":\"success\",\"action\":\"led_pwm\",\"value\":");
      Serial.print(value);
      Serial.println("}");
    }
  }
  else {
    Serial.println("{\"status\":\"error\",\"error\":\"unknown_action\"}");
  }
}
