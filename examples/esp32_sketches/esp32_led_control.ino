/**
 * ESP32 LED Control via Serial Commands
 * 
 * Demonstrates bidirectional communication:
 * - ESP32 sends sensor data to computer
 * - Computer sends commands back to ESP32
 * 
 * Hardware:
 * - ESP32 DevKit
 * - LED on GPIO 2 (built-in LED on most boards)
 * - Optional: DHT22 on GPIO 4
 * 
 * Commands (JSON format):
 * {"action":"led_on"}
 * {"action":"led_off"}
 * {"action":"led_blink","count":5}
 */

#include <DHT.h>
#include <ArduinoJson.h>

#define LED_PIN 2
#define DHTPIN 4
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);
StaticJsonDocument<256> doc;

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  dht.begin();
  delay(1000);
  
  Serial.println("{\"status\":\"ready\",\"device\":\"esp32_led_control\"}");
}

void processCommand() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    
    DeserializationError error = deserializeJson(doc, input);
    if (error) {
      Serial.print("{\"error\":\"json_parse_failed\",\"input\":\"");
      Serial.print(input);
      Serial.println("\"}");
      return;
    }
    
    const char* action = doc["action"];
    
    if (strcmp(action, "led_on") == 0) {
      digitalWrite(LED_PIN, HIGH);
      Serial.println("{\"action\":\"led_on\",\"status\":\"success\"}");
    }
    else if (strcmp(action, "led_off") == 0) {
      digitalWrite(LED_PIN, LOW);
      Serial.println("{\"action\":\"led_off\",\"status\":\"success\"}");
    }
    else if (strcmp(action, "led_blink") == 0) {
      int count = doc["count"] | 3; // Default 3 blinks
      for (int i = 0; i < count; i++) {
        digitalWrite(LED_PIN, HIGH);
        delay(200);
        digitalWrite(LED_PIN, LOW);
        delay(200);
      }
      Serial.print("{\"action\":\"led_blink\",\"count\":");
      Serial.print(count);
      Serial.println(",\"status\":\"success\"}");
    }
    else {
      Serial.print("{\"error\":\"unknown_action\",\"action\":\"");
      Serial.print(action);
      Serial.println("\"}");
    }
  }
}

void loop() {
  // Process incoming commands
  processCommand();
  
  // Send sensor data every 2 seconds
  static unsigned long lastSend = 0;
  if (millis() - lastSend > 2000) {
    lastSend = millis();
    
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();
    
    if (!isnan(humidity) && !isnan(temperature)) {
      Serial.print("{");
      Serial.print("\"type\":\"sensor\",");
      Serial.print("\"temperature_c\":");
      Serial.print(temperature, 2);
      Serial.print(",\"humidity_pct\":");
      Serial.print(humidity, 2);
      Serial.print(",\"led_state\":");
      Serial.print(digitalRead(LED_PIN));
      Serial.print(",\"timestamp\":");
      Serial.print(millis());
      Serial.println("}");
    }
  }
}
