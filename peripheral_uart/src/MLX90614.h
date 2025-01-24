#ifndef MLX90614_H
#define MLX90614_H

#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/sys/printk.h>
#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

// MLX90614 Registers
#define MLX90614_ADDR 0x5A // Default I2C address of MLX90614
#define MLX90614_TA 0x06 // Ambient temperature register
#define MLX90614_TOBJ1 0x07 // Object 1 temperature register

int read_mlx90614_register(const struct device *i2c_dev, uint8_t reg_addr, uint16_t *data);
void read_mlx90614_data(const struct device *i2c_dev);

#endif