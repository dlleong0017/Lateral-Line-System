#include <Arduino.h>
#include <WiFi.h>

#define SENSOR_PIN       36
#define OVERSAMPLE       16
#define SAMPLE_HZ        20
#define SAMPLE_PERIOD_MS (1000 / SAMPLE_HZ)

#define SENSOR_OFFSET_KPA 0.0f
#define WATER_DENSITY     1000.0f  // kg/m^3


float readVoltage()
{
  // Discard initial readings so the ADC settles.
  for (uint8_t i = 0; i < 4; i++)
  {
    analogRead(SENSOR_PIN);
    delayMicroseconds(200);
  }

  uint32_t voltage_sum_mv = 0;

  for (uint8_t i = 0; i < OVERSAMPLE; i++)
  {
    voltage_sum_mv += analogReadMilliVolts(SENSOR_PIN);
    delayMicroseconds(100);
  }

  return (voltage_sum_mv / OVERSAMPLE) / 1000.0f;
}


float readPressure()
{
  float pin_voltage = readVoltage();

  // Reconstruct the sensor voltage before the voltage divider.
  float sensor_voltage = pin_voltage * (5.0f / 3.3f);

  float pressure_kpa =
      (sensor_voltage / 5.0f - 0.5f) / 0.2f;

  return pressure_kpa + SENSOR_OFFSET_KPA;
}


float readFluidVelocity()
{
  float pressure_kpa = readPressure();

  // Convert kPa to Pa.
  float pressure_pa = pressure_kpa * 1000.0f;

  // Bernoulli equation using the pressure magnitude.
  float velocity = sqrtf(
      (2.0f * fabsf(pressure_pa)) / WATER_DENSITY
  );

  // Preserve the sign to indicate flow direction.
  if (pressure_pa < 0.0f)
  {
    velocity = -velocity;
  }

  return velocity;
}


void setup()
{
  Serial.begin(115200);

  // Disable wireless systems to reduce ADC noise.
  WiFi.mode(WIFI_OFF);
  btStop();

  analogReadResolution(12);
  analogSetPinAttenuation(SENSOR_PIN, ADC_11db);

  Serial.println("t_ms,velocity_m_s");
}


void loop()
{
  static uint32_t last_sample_time = 0;

  uint32_t current_time = millis();

  if (current_time - last_sample_time < SAMPLE_PERIOD_MS)
  {
    return;
  }

  last_sample_time = current_time;

  float fluid_velocity = readFluidVelocity();

  float pressure = readPressure();

  Serial.print(current_time);
  Serial.printf(",%.4f\n", fluid_velocity);
  Serial.printf(",%.4f\n", pressure);
}