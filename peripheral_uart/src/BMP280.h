#ifndef BMP280_H
#define BMP280_H

#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/sys/printk.h>
#include <zephyr/kernel.h>
#include <stdint.h>

// HOW TO CONNECT: (BMP --> Nordic)
// SCK --> Pin 27
// SDI --> Pin 26
// SDO --> GND (for I2C Address 0x76)    *VDO --> VDD (makes I2C address 0x77)*
// CS --> VDD
// 3Vo --> VDD
// GND --> GND

#define BMP280_ADDR 0x76  // Adjust to 0x77 if SDO pin is high

// BMP280 Register Addresses
#define BMP280_REG_CALIB_START    0x88
#define BMP280_REG_CHIPID         0xD0
#define BMP280_REG_SOFTRESET      0xE0
#define BMP280_REG_CONTROL        0xF4
#define BMP280_REG_CONFIG         0xF5
#define BMP280_REG_PRESSURE_MSB   0xF7
#define BMP280_REG_TEMPERATURE_MSB 0xFA

void bmp280_init(const struct device *i2c_dev);
void read_bmp280_data(const struct device *i2c_dev);

#endif