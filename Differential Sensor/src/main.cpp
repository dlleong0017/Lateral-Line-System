#include <Arduino.h>
#include <WiFi.h>
#if __has_include(<driver/dac.h>)
  #include <driver/dac.h>
#endif

#define N_SENSORS   8
#define OVERSAMPLE  16
#define SAMPLE_HZ   20

#define SAMPLE_PERIOD_MS (1000 / SAMPLE_HZ)

struct Sensor 
{
  uint8_t pin;
  float   sensor_offset;
};

// pin  sensor_offset (kPa)
Sensor sensors[N_SENSORS] = 
{
  { 36,  -0.115f },
  { 39,  -0.200f },
  { 34,   0.000f },
  { 35,  -0.190f },
  { 32,  -0.075f },
  { 33,  -0.120f },
  { 25,  -0.130f },
  { 26,  -0.198f },
};

// readVoltage
//  discards a few reads first so the ADC cap forgets the previous channel
//  uses analogReadMilliVolts as the main source of tracking voltage
float readVoltage(uint8_t idx) 
{
  uint8_t pin = sensors[idx].pin;

  for (uint8_t k = 0; k < 4; k++) 
  { 
    analogRead(pin); delayMicroseconds(200);
  }

  uint32_t sum = 0;
  for (uint8_t k = 0; k < OVERSAMPLE; k++) 
  {
    sum += analogReadMilliVolts(pin);
    delayMicroseconds(100);
  }

  return (sum / OVERSAMPLE) / 1000.0f;
}

// readPressure
//  based on 
//
float readPressure(uint8_t idx) 
{
  float v_pin    = readVoltage(idx);
  float v_sensor = v_pin * (5.0f / 3.3f);
  float p        = (v_sensor / 5.0f - 0.5f) / 0.2f;
  return p + sensors[idx].sensor_offset;
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_OFF);
  btStop();

  analogReadResolution(12);

  for (uint8_t i = 0; i < N_SENSORS; i++)
  {
    analogSetPinAttenuation(sensors[i].pin, ADC_11db);
  }

#if __has_include(<driver/dac.h>)
  dac_output_disable(DAC_CHANNEL_1);   // GPIO25
  dac_output_disable(DAC_CHANNEL_2);   // GPIO26
#endif
}

void loop() {
  static uint32_t next_due = 0;
  static bool     started  = false;
  if (!started) 
  {
    next_due = millis(); started = true; 
  }

  if ((int32_t)(millis() - next_due) < 0)
  {
    return;
  }

  uint32_t t = millis();

  float p[N_SENSORS];

  for (uint8_t i = 0; i < N_SENSORS; i++)
  {
    p[i] = readPressure(i);
  }

  Serial.print(t);
  for (uint8_t i = 0; i < N_SENSORS; i++)
  {
    Serial.printf(",%.4f", p[i]);
  }

  Serial.println();

  // Advance by exactly one period so the average rate stays true.
  // If the sweep overran, resync instead of bursting to catch up.
  next_due += SAMPLE_PERIOD_MS;
  if ((int32_t)(millis() - next_due) > 0)
  {
    next_due = millis() + SAMPLE_PERIOD_MS;
  }
}