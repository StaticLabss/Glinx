/**
 * ESP32 MPU6050 IMU with WiFi/MQTT
 * 
 * Hardware:
 * - ESP32 DevKit
 * - MPU6050 6-axis IMU
 *   - VCC -> 3.3V
 *   - GND -> GND
 *   - SCL -> GPIO 22
 *   - SDA -> GPIO 21
 * 
 * Install libraries:
 * - Adafruit MPU6050
 * - PubSubClient (MQTT)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <ArduinoJson.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// MQTT broker (change to your broker IP)
const char* mqtt_server = "192.168.1.100";
const char* mqtt_topic = "sensor/imu";

WiFiClient espClient;
PubSubClient client(espClient);
Adafruit_MPU6050 mpu;

void setup() {
  Serial.begin(115200);
  
  // Initialize MPU6050
  if (!mpu.begin()) {
    Serial.println("Failed to find MPU6050");
    while (1) {
      delay(10);
    }
  }
  
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  
  // Connect WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  
  // Connect MQTT
  client.setServer(mqtt_server, 1883);
  reconnect();
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    if (client.connect("ESP32_IMU")) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.println(client.state());
      delay(5000);
    }
  }
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
  
  // Read sensor
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);
  
  // Create JSON payload
  StaticJsonDocument<256> doc;
  doc["accel_x"] = a.acceleration.x;
  doc["accel_y"] = a.acceleration.y;
  doc["accel_z"] = a.acceleration.z;
  doc["gyro_x"] = g.gyro.x;
  doc["gyro_y"] = g.gyro.y;
  doc["gyro_z"] = g.gyro.z;
  doc["temp_c"] = temp.temperature;
  doc["timestamp"] = millis();
  
  char buffer[256];
  serializeJson(doc, buffer);
  
  // Publish to MQTT
  client.publish(mqtt_topic, buffer);
  
  delay(50); // 20 Hz
}
