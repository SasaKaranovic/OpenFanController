# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.13)

include($ENV{PICO_SDK_PATH}/pico_sdk_init.cmake)

project(OpenFAN_Firmware)

set(PROJECT_DIR_PATH ${CMAKE_CURRENT_LIST_DIR} CACHE PATH "Project directory" FORCE)
message("PROJECT_DIR_PATH is ${PROJECT_DIR_PATH}")

pico_sdk_init()

add_executable(OpenFAN_Firmware
               ${PROJECT_DIR_PATH}/Lib/Logger/logger.c
               ${PROJECT_DIR_PATH}/Application/fan_control.c
               ${PROJECT_DIR_PATH}/Application/host_communication.c
               ${PROJECT_DIR_PATH}/Application/emc230x.c
               ${PROJECT_DIR_PATH}/Application/usb_cdc.c
               ${PROJECT_DIR_PATH}/Application/usb-descriptors.c
               ${PROJECT_DIR_PATH}/Application/main.c
           )



target_include_directories(OpenFAN_Firmware PUBLIC
    ${PROJECT_DIR_PATH}/Lib/Logger
	${PROJECT_DIR_PATH}/Application
	${PICO_SDK_PATH}/lib/tinyusb/src)

target_link_libraries(OpenFAN_Firmware
	hardware_flash
	pico_multicore
	pico_stdlib
    hardware_i2c
	tinyusb_device)

pico_add_extra_outputs(OpenFAN_Firmware)
