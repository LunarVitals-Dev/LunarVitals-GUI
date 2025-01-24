#include "i2c.h"
#include "BMP280.h"
#include "MPU6050.h"
#include "MLX90614.h"
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/sys/printk.h>
#include <zephyr/kernel.h>

const struct device *i2c_dev0 = DEVICE_DT_GET(DT_NODELABEL(i2c0));
const struct device *i2c_dev1 = DEVICE_DT_GET(DT_NODELABEL(i2c1));

int i2c_write_register(const struct device *i2c_dev, uint8_t dev_addr, uint8_t reg_addr, uint8_t data) {
    uint8_t buffer[2] = {reg_addr, data};
    return i2c_write(i2c_dev, buffer, sizeof(buffer), dev_addr);
}

int i2c_read_register(const struct device *i2c_dev, uint8_t dev_addr, uint8_t reg_addr, uint8_t *data) {
    return i2c_write_read(i2c_dev, dev_addr, &reg_addr, 1, data, 1);
}

int i2c_read_registers(const struct device *i2c_dev, uint8_t dev_addr, uint8_t reg_addr, uint8_t *data, size_t len) {
    return i2c_write_read(i2c_dev, dev_addr, &reg_addr, 1, data, len);
}

void i2c_init(void) {
    if (!device_is_ready(i2c_dev0)) {
        printk("I2C0 device not ready\n");
        return;
    }

    if (!device_is_ready(i2c_dev1)) {
        printk("I2C1 device not ready\n");
        return;
    }

    mpu6050_init(i2c_dev0);
    bmp280_init(i2c_dev1);
}

void i2c_read_data(void) {
    read_mpu6050_data(i2c_dev0);
    read_mlx90614_data(i2c_dev0);
    read_bmp280_data(i2c_dev1);

    
}

