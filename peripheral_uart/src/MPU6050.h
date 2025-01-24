#ifndef MPU6050_H
#define MPU6050_H

#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/sys/printk.h>
#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

// MPU6050 Registers
#define MPU6050_ADDR 0x68          // Default I2C address of MPU6050
#define DEVICE_ID 0x75
#define PWR_MGMT_1   0x6B
#define ACCEL_XOUT_H 0x3B
#define GYRO_XOUT_H  0x43

void mpu6050_init(const struct device *i2c_dev);
void read_mpu6050_data(const struct device *i2c_dev);

#endif