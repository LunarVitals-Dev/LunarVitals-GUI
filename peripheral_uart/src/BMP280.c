#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/sys/printk.h>
#include <zephyr/kernel.h>
#include "bmp280.h"
#include "i2c.h"

// Calibration parameters
uint16_t dig_T1;
int16_t dig_T2, dig_T3;
uint16_t dig_P1;
int16_t dig_P2, dig_P3, dig_P4, dig_P5, dig_P6, dig_P7, dig_P8, dig_P9;
int32_t t_fine;

void bmp280_init(const struct device *i2c_dev) {
    uint8_t chip_id;

    // Read Chip ID
    if (i2c_read_register(i2c_dev, BMP280_ADDR, BMP280_REG_CHIPID, &chip_id) != 0 || chip_id != 0x58) {
        printk("Error: BMP280 not detected or invalid Chip ID\n");
        return;
    }
    printk("BMP280 detected. Chip ID: 0x%x\n", chip_id);

    // Reset the sensor
    i2c_write_register(i2c_dev, BMP280_ADDR, BMP280_REG_SOFTRESET, 0xB6);
    k_sleep(K_MSEC(100));

    // Read calibration data
    uint8_t calib_data[24];
    if (i2c_read_registers(i2c_dev, BMP280_ADDR, BMP280_REG_CALIB_START, calib_data, sizeof(calib_data)) != 0) {
        printk("Error: Failed to read calibration data\n");
        return;
    }

    // Parse calibration data
    dig_T1 = (calib_data[1] << 8) | calib_data[0];
    dig_T2 = (calib_data[3] << 8) | calib_data[2];
    dig_T3 = (calib_data[5] << 8) | calib_data[4];
    dig_P1 = (calib_data[7] << 8) | calib_data[6];
    dig_P2 = (calib_data[9] << 8) | calib_data[8];
    dig_P3 = (calib_data[11] << 8) | calib_data[10];
    dig_P4 = (calib_data[13] << 8) | calib_data[12];
    dig_P5 = (calib_data[15] << 8) | calib_data[14];
    dig_P6 = (calib_data[17] << 8) | calib_data[16];
    dig_P7 = (calib_data[19] << 8) | calib_data[18];
    dig_P8 = (calib_data[21] << 8) | calib_data[20];
    dig_P9 = (calib_data[23] << 8) | calib_data[22];

    // Configure sensor: normal mode, oversampling x1 for temp & pressure
    uint8_t ctrl_meas = (0x01 << 5) | (0x01 << 2) | 0x03;
    i2c_write_register(i2c_dev, BMP280_ADDR, BMP280_REG_CONTROL, ctrl_meas);
    i2c_write_register(i2c_dev, BMP280_ADDR, BMP280_REG_CONFIG, 0);
}

void read_bmp280_data(const struct device *i2c_dev) {
    uint8_t data[6];

    if (i2c_read_registers(i2c_dev, BMP280_ADDR, BMP280_REG_PRESSURE_MSB, data, sizeof(data)) != 0) {
        printk("Error: Failed to read BMP280 data\n");
        return;
    }

    int32_t adc_T = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4);
    int32_t adc_P = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4);

    // Temperature compensation
    int32_t var1 = ((((adc_T >> 3) - ((int32_t)dig_T1 << 1))) * ((int32_t)dig_T2)) >> 11;
    int32_t var2 = (((((adc_T >> 4) - ((int32_t)dig_T1)) * ((adc_T >> 4) - ((int32_t)dig_T1))) >> 12) * ((int32_t)dig_T3)) >> 14;
    t_fine = var1 + var2;
    float celsius = ((t_fine * 5 + 128) >> 8) / 100.0f;
    float fahrenheit =(celsius *  1.8) + 32.0;

    // Pressure compensation
    int64_t var1_p = ((int64_t)t_fine) - 128000;
    int64_t var2_p = var1_p * var1_p * (int64_t)dig_P6 + ((var1_p * (int64_t)dig_P5) << 17) + (((int64_t)dig_P4) << 35);
    var1_p = (((var1_p * var1_p * (int64_t)dig_P3) >> 8) + ((var1_p * (int64_t)dig_P2) << 12));
    var1_p = ((((int64_t)1 << 47) + var1_p) * (int64_t)dig_P1) >> 33;

    if (var1_p == 0) {
        printk("Error: Division by zero in pressure calculation\n");
        return;
    }

    int64_t p = ((((int64_t)1048576 - adc_P) << 31) - var2_p) * 3125 / var1_p;
    var1_p = (((int64_t)dig_P9) * (p >> 13) * (p >> 13)) >> 25;
    var2_p = (((int64_t)dig_P8) * p) >> 19;
    p = ((p + var1_p + var2_p) >> 8) + (((int64_t)dig_P7) << 4);

    float pressure = p / 25600.0f;  // Convert to hPa

    printk("Temperature: %.2f °C / %.2f °F, Pressure: %.2f hPa\n", celsius, fahrenheit, pressure);
}
