#ifndef I2C_H
#define I2C_H
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/sys/printk.h>
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <stdint.h>
#include <stddef.h>

// General I2C read/write functions
int i2c_write_register(const struct device *i2c_dev, uint8_t dev_addr, uint8_t reg_addr, uint8_t data);
int i2c_read_register(const struct device *i2c_dev, uint8_t dev_addr, uint8_t reg_addr, uint8_t *data);
int i2c_read_registers(const struct device *i2c_dev, uint8_t dev_addr, uint8_t reg_addr, uint8_t *data, size_t len);
void i2c_init(void);
void i2c_read_data(void);

#endif
