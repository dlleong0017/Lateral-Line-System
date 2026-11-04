#include <Arduino.h>
#include <WiFi.h>
#if __has_include(<driver/dac.h>)
  #include <driver/dac.h>
#endif

#define N_SENSORS   8
#define OVERSAMPLE  1        // was 16 - average in Python instead
#define DISCARD     1        // throwaway reads after switching channel (try 0, check crosstalk)
#define SAMPLE_HZ   400      // was 20
#define BAUD        921600   // was 115200 - set your pyserial script to match

#define SAMPLE_PERIOD_US (1000000UL / SAMPLE_HZ)

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
//  one throwaway read so the ADC cap forgets the previous channel (no delays)
float readVoltage(uint8_t idx)
{
  uint8_t pin = sensors[idx].pin;

  for (uint8_t k = 0; k < DISCARD; k++)
  {
    analogRead(pin);
  }

  uint32_t sum = 0;
  for (uint8_t k = 0; k < OVERSAMPLE; k++)
  {
    sum += analogReadMilliVolts(pin);
  }

  return (sum / (float)OVERSAMPLE) / 1000.0f;
}

// readPressure
//  MPXV7002: Vout = Vs * (0.2 * P + 0.5)
float readPressure(uint8_t idx)
{
  float v_pin    = readVoltage(idx);
  float v_sensor = v_pin * (5.0f / 3.3f);
  float p        = (v_sensor / 5.0f - 0.5f) / 0.2f;
  return p + sensors[idx].sensor_offset;
}

void setup() {
  Serial.setTxBufferSize(2048);   // so printing doesn't block the next sweep
  Serial.begin(BAUD);
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
  static uint32_t next_due = micros();

  if ((int32_t)(micros() - next_due) < 0)
  {
    return;
  }

  uint32_t t  = millis();
  uint32_t t0 = micros();

  float p[N_SENSORS];

  for (uint8_t i = 0; i < N_SENSORS; i++)
  {
    p[i] = readPressure(i);
  }

  uint32_t t1 = micros();

  // Same text as before (t,p0,...,p7 with 4 decimals), but built with integer
  // formatting into one buffer and sent in a single write - float printf is slow.
  char line[128];
  int  len = snprintf(line, sizeof(line), "%lu", (unsigned long)t);

  for (uint8_t i = 0; i < N_SENSORS; i++)
  {
    long v = lroundf(p[i] * 10000.0f);
    const char* sign = (v < 0) ? "-" : "";
    if (v < 0) v = -v;
    len += snprintf(line + len, sizeof(line) - len, ",%s%ld.%04ld", sign, v / 10000, v % 10000);
  }

  line[len++] = '\r';   // \r\n like println, so serial monitors start each line at the left
  line[len++] = '\n';
  Serial.write((const uint8_t*)line, len);

  uint32_t t2 = micros();

  // Timing check, once per second. No commas, so capture.py skips this line.
  static uint32_t n = 0;
  if (++n >= SAMPLE_HZ)
  {
    n = 0;
    Serial.printf("# read_us=%u print_us=%u\r\n", (unsigned)(t1 - t0), (unsigned)(t2 - t1));
  }

  // Advance by exactly one period so the average rate stays true.
  // If the sweep overran, start the next one immediately (don't wait a full period).
  next_due += SAMPLE_PERIOD_US;
  if ((int32_t)(micros() - next_due) > 0)
  {
    next_due = micros();
  }
}