#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

/* ================= WIFI ================= */
// Change these values for your Wi-Fi network.
#define WIFI_SSID       "YOUR_WIFI_NAME"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"

/* ================= BACKEND ================= */
// Change this IP/URL to your FastAPI backend.
// Example: "http://192.168.1.50:8000"
#define API_BASE_URL    "http://192.168.1.100:8000"

#define MACHINE_ID      "motor_01"

#define API_READINGS_ENDPOINT          "/api/readings"
#define API_COMMAND_LATEST_ENDPOINT    "/api/commands/latest/" MACHINE_ID
#define API_COMMAND_CONFIRM_ENDPOINT   "/api/commands/confirm"

#define HTTP_TIMEOUT_MS 5000

/* ================= TIMING ================= */
#define SEND_READING_INTERVAL_MS   2000
#define GET_COMMAND_INTERVAL_MS    2000
#define LCD_UPDATE_INTERVAL_MS     500
#define WIFI_RECONNECT_INTERVAL_MS 5000

/* ================= PINS ================= */
#define RELAY_PIN 26

// DHT22 data pin. Used when TEMP_SENSOR_TYPE == TEMP_SENSOR_DHT22.
#define DHT_PIN 4

// DS18B20 OneWire pin. Used when TEMP_SENSOR_TYPE == TEMP_SENSOR_DS18B20.
#define ONEWIRE_PIN 4

/* ================= RELAY LOGIC ================= */
// Most relay modules are active LOW. If your relay turns ON when GPIO is HIGH,
// change this to true.
#define RELAY_ACTIVE_HIGH false

/* ================= TEMPERATURE SENSOR ================= */
#define TEMP_SENSOR_DHT22   1
#define TEMP_SENSOR_DS18B20 2

// Default: DHT22. To use DS18B20, change to TEMP_SENSOR_DS18B20.
#define TEMP_SENSOR_TYPE TEMP_SENSOR_DHT22
#define TEMP_SENSOR_DHT_TYPE DHT22

/* ================= LCD ================= */
// I2C LCD default address is usually 0x27 or 0x3F.
#define LCD_I2C_ADDR 0x27
#define LCD_COLS 20
#define LCD_ROWS 4

/* ================= PRODUCTION RATE ================= */
// Simple demo logic: productionRate is this value when relay is ON, otherwise 0.
#define PRODUCTION_RATE_ON 75

#endif
