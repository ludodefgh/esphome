#pragma once

#include "esphome/components/zigbee/zigbee_zephyr.h"
#if defined(USE_ZIGBEE) && defined(USE_NRF52)
#include "esphome/core/component.h"
#ifdef USE_SENSOR
#include "esphome/components/sensor/sensor.h"
#endif
#ifdef USE_BINARY_SENSOR
#include "esphome/components/binary_sensor/binary_sensor.h"
#endif
extern "C" {
#include <zboss_api.h>
#include <zboss_api_addons.h>
// zboss_api_zcl.h only pulls in the CO2 / PM2.5 headers when a
// ZB_ZCL_SUPPORT_CLUSTER_* macro is set (and #undefs those two outright when
// single-precision types are off), so the clusters used here are included by
// hand, as firmware-nrf54l15 does.
#include <addons/zcl/zb_zcl_temp_measurement_addons.h>
#include <zcl/zb_zcl_carbon_dioxide_measurement.h>
#include <zcl/zb_zcl_occupancy_sensing.h>
#include <zcl/zb_zcl_pm2_5_measurement.h>
}

namespace esphome::zigbee {

// Attribute storage for the standard clusters ZBOSS ships no struct for
// (temperature, CO2 and PM2.5 use zb_zcl_*_attrs_t straight from ZBOSS).
struct HumidityAttrs {
  zb_uint16_t rel_humidity;
  zb_uint16_t min_val;
  zb_uint16_t max_val;
};

struct IlluminanceAttrs {
  zb_uint16_t log_lux;
};

struct OccupancyAttrs {
  zb_uint8_t occupancy;
  zb_uint8_t sensor_type;
  zb_uint8_t sensor_type_bitmap;
};

/// Standard ZCL measurement clusters a sensor can be exposed as, chosen from its device_class.
enum class StandardKind : uint8_t {
  TEMPERATURE,
  HUMIDITY,
  ILLUMINANCE,
  CO2,
  PM25,
};

#ifdef USE_SENSOR
/// Publishes a sensor through the standard cluster of its kind (Temperature Measurement, Relative Humidity,
/// Illuminance, Carbon Dioxide, PM2.5), converting ESPHome's units to the ZCL ones. Several of these, of different
/// kinds, can share one endpoint.
class ZigbeeStandardSensor final : public ZigbeeEntity, public Component {
 public:
  ZigbeeStandardSensor(sensor::Sensor *sensor, StandardKind kind) : sensor_(sensor), kind_(kind) {}

  void setup() override;
  void dump_config() override;

 protected:
  void publish_(float state);

  sensor::Sensor *sensor_;
  StandardKind kind_;
};
#endif

#ifdef USE_BINARY_SENSOR
/// Publishes a binary sensor through the Occupancy Sensing cluster.
class ZigbeeOccupancySensor final : public ZigbeeEntity, public Component {
 public:
  explicit ZigbeeOccupancySensor(binary_sensor::BinarySensor *binary_sensor) : binary_sensor_(binary_sensor) {}

  void setup() override;
  void dump_config() override;

 protected:
  binary_sensor::BinarySensor *binary_sensor_;
};
#endif

}  // namespace esphome::zigbee
#endif
