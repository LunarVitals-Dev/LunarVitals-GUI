#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/sys/printk.h>
#include <zephyr/kernel.h>
#include "mlx90614.h"
#include "i2c.h"

int read_mlx90614_register(const struct device *i2c_dev, uint8_t reg_addr, uint16_t *data) {
    uint8_t buffer[3];
    int ret = i2c_write_read(i2c_dev, MLX90614_ADDR, &reg_addr, 1, buffer, 3);
    if (ret < 0) {
        return ret;
    }
    *data = (buffer[0] | (buffer[1] << 8)); // Combine high and low byte
    return 0;
}

void read_mlx90614_data(const struct device *i2c_dev) {
    uint16_t ambient_temp_raw, object_temp_raw;
    float ambient_temp, object_temp;

    // Read ambient temperature
    if (read_mlx90614_register(i2c_dev, MLX90614_TA, &ambient_temp_raw) == 0) {
        ambient_temp = ambient_temp_raw * 0.02 - 273.15; // Convert to Celsius
        printk("Ambient Temperature: %.2f °C\n", ambient_temp);
    } else {
        printk("Failed to read ambient temperature\n");
    }

    // Read object temperature
    if (read_mlx90614_register(i2c_dev, MLX90614_TOBJ1, &object_temp_raw) == 0) {
        object_temp = object_temp_raw * 0.02 - 273.15; // Convert to Celsius
        printk("Object Temperature: %.2f °C\n", object_temp);
    } else {
        printk("Failed to read object temperature\n");
    }
}