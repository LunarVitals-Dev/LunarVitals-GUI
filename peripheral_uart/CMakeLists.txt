#
# Copyright (c) 2018 Nordic Semiconductor
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(peripheral_uart)

# Add the src directory to include path
target_include_directories(app PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_sources(app PRIVATE
  src/main.c
  src/adc.c
  # src/BMP280.c
  # src/i2c.c
  # src/MLX90614.c
  # src/MPU6050.c
)

# # NORDIC SDK APP START
# target_sources(app PRIVATE
#   src/main.c
# )

# NORDIC SDK APP END
