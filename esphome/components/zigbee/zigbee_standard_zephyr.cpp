#include "zigbee_standard_zephyr.h"
#if defined(USE_ZIGBEE) && defined(USE_NRF52)
#include <cmath>
#include "esphome/core/log.h"
extern "C" {
#include <zboss_api.h>
#include <zboss_api_addons.h>
#include <zb_nrf_platform.h>
#include <zigbee/zigbee_app_utils.h>
}

namespace esphome::zigbee {

static const char *const TAG = "zigbee.standard";

static void set_attribute(zb_uint8_t endpoint, zb_uint16_t cluster_id, zb_uint16_t attr_id, void *value) {
  zb_zcl_set_attr_val(endpoint, cluster_id, ZB_ZCL_CLUSTER_SERVER_ROLE, attr_id, static_cast<zb_uint8_t *>(value),
                      ZB_FALSE);
}

#ifdef USE_SENSOR
void ZigbeeStandardSensor::setup() {
  this->sensor_->add_on_state_callback([this](float state) { this->publish_(state); });
}

void ZigbeeStandardSensor::publish_(float state) {
  if (std::isnan(state))
    return;

  switch (this->kind_) {
    case StandardKind::TEMPERATURE: {
      // int16, units of 0.01 degC
      auto value = static_cast<zb_int16_t>(std::lround(state * 100.0f));
      set_attribute(this->endpoint_, ZB_ZCL_CLUSTER_ID_TEMP_MEASUREMENT, ZB_ZCL_ATTR_TEMP_MEASUREMENT_VALUE_ID, &value);
      break;
    }
    case StandardKind::HUMIDITY: {
      // uint16, units of 0.01 %
      float clamped = std::fmin(std::fmax(state, 0.0f), 100.0f);
      auto value = static_cast<zb_uint16_t>(std::lround(clamped * 100.0f));
      set_attribute(this->endpoint_, ZB_ZCL_CLUSTER_ID_REL_HUMIDITY_MEASUREMENT,
                    ZB_ZCL_ATTR_REL_HUMIDITY_MEASUREMENT_VALUE_ID, &value);
      break;
    }
    case StandardKind::ILLUMINANCE: {
      // ZCL 4.2.2.2: MeasuredValue = 10000 * log10(lux) + 1. log10(0) is undefined, so 0 lx is floored to 1 lx.
      float lux = state < 1.0f ? 1.0f : state;
      float scaled = 10000.0f * std::log10(lux) + 1.0f;
      auto value = static_cast<zb_uint16_t>(scaled > 65534.0f ? 65534.0f : scaled);  // 0xFFFF means invalid
      set_attribute(this->endpoint_, ZB_ZCL_CLUSTER_ID_ILLUMINANCE_MEASUREMENT,
                    ZB_ZCL_ATTR_ILLUMINANCE_MEASUREMENT_MEASURED_VALUE_ID, &value);
      break;
    }
    case StandardKind::CO2: {
      // single, a molar FRACTION (0.0-1.0), not ppm (ZCL 4.13)
      zb_single_t value = state / 1000000.0f;
      set_attribute(this->endpoint_, ZB_ZCL_CLUSTER_ID_CARBON_DIOXIDE_MEASUREMENT,
                    ZB_ZCL_ATTR_CARBON_DIOXIDE_MEASUREMENT_MEASURED_VALUE_ID, &value);
      break;
    }
    case StandardKind::PM25: {
      // single, ug/m3
      zb_single_t value = state;
      set_attribute(this->endpoint_, ZB_ZCL_CLUSTER_ID_PM2_5_MEASUREMENT,
                    ZB_ZCL_ATTR_PM2_5_MEASUREMENT_MEASURED_VALUE_ID, &value);
      break;
    }
  }
  ESP_LOGD(TAG, "Set attribute endpoint: %d, kind %d, value %f", this->endpoint_, static_cast<int>(this->kind_),
           state);
  this->parent_->force_report();
}

void ZigbeeStandardSensor::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Zigbee Standard Sensor\n"
                "  Endpoint: %d, kind %d",
                this->endpoint_, static_cast<int>(this->kind_));
}
#endif

#ifdef USE_BINARY_SENSOR
void ZigbeeOccupancySensor::setup() {
  this->binary_sensor_->add_on_state_callback([this](bool state) {
    zb_uint8_t value = state ? 1 : 0;
    set_attribute(this->endpoint_, ZB_ZCL_CLUSTER_ID_OCCUPANCY_SENSING, ZB_ZCL_ATTR_OCCUPANCY_SENSING_OCCUPANCY_ID,
                  &value);
    ESP_LOGD(TAG, "Set attribute endpoint: %d, occupancy %d", this->endpoint_, value);
    this->parent_->force_report();
  });
}

void ZigbeeOccupancySensor::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Zigbee Occupancy Sensor\n"
                "  Endpoint: %d",
                this->endpoint_);
}
#endif

}  // namespace esphome::zigbee

// ZBOSS declares these two init functions but only defines them when ZB_ALL_DEVICE_SUPPORT is set - a macro that is
// off in the shipped SDK ("use in testing purposes") and has no Kconfig - so linking a Carbon Dioxide or PM2.5
// cluster fails with an undefined reference. Same workaround (register no-op handlers) as the analog input one.
// Occupancy Sensing does not need it: its init is a NULL macro in the header.
#ifndef ZB_ALL_DEVICE_SUPPORT
void zb_zcl_carbon_dioxide_measurement_init_server(void) {
  zb_zcl_add_cluster_handlers(ZB_ZCL_CLUSTER_ID_CARBON_DIOXIDE_MEASUREMENT, ZB_ZCL_CLUSTER_SERVER_ROLE,
                              (zb_zcl_cluster_check_value_t) NULL, (zb_zcl_cluster_write_attr_hook_t) NULL,
                              (zb_zcl_cluster_handler_t) NULL);
}

void zb_zcl_pm2_5_measurement_init_server(void) {
  zb_zcl_add_cluster_handlers(ZB_ZCL_CLUSTER_ID_PM2_5_MEASUREMENT, ZB_ZCL_CLUSTER_SERVER_ROLE,
                              (zb_zcl_cluster_check_value_t) NULL, (zb_zcl_cluster_write_attr_hook_t) NULL,
                              (zb_zcl_cluster_handler_t) NULL);
}
#endif

#endif
