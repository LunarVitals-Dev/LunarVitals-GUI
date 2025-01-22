/*
 * Copyright (c) 2018 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

/** @file
 *  @brief Nordic UART Bridge Service (NUS) sample
 */
#include "adc.h"

#define ADC_REF_VOLTAGE_MV 600 // Internal reference in mV
#define ADC_GAIN (1.0 / 6.0)    // Gain of 1/6
#define ADC_RESOLUTION 4096     // 12-bit resolution
#define NUMOFADCCHANNELS 2
/* ADC channel configuration via Device Tree */


/* ADC buffer and sequence configuration */
static int16_t buf;
static struct adc_sequence sequence = {
    .buffer = &buf,
    .buffer_size = sizeof(buf), 
    /* Optional calibration */
    //.calibrate = true,
};

int32_t convert_to_mv(int16_t raw_value) {
    return (int32_t)((raw_value * ADC_REF_VOLTAGE_MV * (1.0 / ADC_GAIN)) / ADC_RESOLUTION);
}

void adc_init(){
	for(int i = 0; i < NUMOFADCCHANNELS; i++){
		int err;
		const struct adc_dt_spec *adc_channel = &adc_channels[i];
		if (!adc_is_ready_dt(adc_channel)) {
			printf("ADC controller device %s not ready\n", adc_channel->dev->name);
			return;
		}

		/* Configure ADC channel */
		int err1 = adc_channel_setup_dt(adc_channel);
		if (err1 < 0) {
			printf("Could not setup ADC channel (%d)\n", err);
			return;
		}

		/* Initialize ADC sequence */
		err1 = adc_sequence_init_dt(adc_channel, &sequence);
		if (err1 < 0) {
			printf("Could not initialize ADC sequence (%d)\n", err);
			return;
		}
	}
}

void get_adc_data() {
    for (int i = 0; i < NUMOFADCCHANNELS; i++) {
        const struct adc_dt_spec *adc_channel = &adc_channels[i];
        
        // Read ADC data for the current channel
        int err1 = adc_read(adc_channel->dev, &sequence);
        if (err1 < 0) {
            printf("ADC read failed for channel %d (%d)\n", i, err1);
        } else {
            // Convert the raw value to millivolts
            int32_t val_mv = convert_to_mv(buf);
            
            // Get the current uptime in milliseconds
            uint32_t timestamp = k_uptime_get();
            
            // Format the message to send via Bluetooth
            char message[50];
            snprintf(message, sizeof(message), "Channel %d: %d mV, Timestamp: %u\r\n", i, val_mv, timestamp);
            printf(message);
            // Send the message over Bluetooth
            send_message_to_bluetooth(message);
        }
    }
}
