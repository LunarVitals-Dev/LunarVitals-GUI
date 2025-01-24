#ifndef ADC_H
#define ADC_H


#include <uart_async_adapter.h>

#include <zephyr/types.h>
#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/usb/usb_device.h>

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <soc.h>

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/hci.h>

#include <bluetooth/services/nus.h>

#include <dk_buttons_and_leds.h>

#include <zephyr/settings/settings.h>

#include <stdio.h>
#include <string.h>

#include <zephyr/logging/log.h>

#include <bluetooth/services/nus.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/adc.h>

#define NUMOFADCCHANNELS 8
static const struct adc_dt_spec adc_channels[NUMOFADCCHANNELS] = {
    ADC_DT_SPEC_GET_BY_IDX(DT_PATH(zephyr_user), 0), // Channel 0
    ADC_DT_SPEC_GET_BY_IDX(DT_PATH(zephyr_user), 1), // Channel 1
    ADC_DT_SPEC_GET_BY_IDX(DT_PATH(zephyr_user), 2), // Channel 2
    ADC_DT_SPEC_GET_BY_IDX(DT_PATH(zephyr_user), 3), // Channel 3
    ADC_DT_SPEC_GET_BY_IDX(DT_PATH(zephyr_user), 4), // Channel 4
    ADC_DT_SPEC_GET_BY_IDX(DT_PATH(zephyr_user), 5), // Channel 5
    ADC_DT_SPEC_GET_BY_IDX(DT_PATH(zephyr_user), 6), // Channel 6
    ADC_DT_SPEC_GET_BY_IDX(DT_PATH(zephyr_user), 7), // Channel 7
};
int32_t convert_to_mv(int16_t raw_value);
void adc_init();

#endif