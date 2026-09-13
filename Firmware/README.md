# OpenFAN Controller - Firmware


## How to install latest firmware onto the board?

OpenFAN Controller supports loading new firmware over USB.

Latest firmware is compiled through GitHub action and published under [releases](https://github.com/SasaKaranovic/OpenFanController/releases). Download the latest firmware version to your PC.

To load the latest firmware onto your board, follow the below steps:

1. Disconnect all fans and power from the board
2. Hold the BOOT button
3. Connect USB-C cable to OpenFAN
4. You should see a new USB drive on your PC
5. Drag and drop (or copy-paste) the OpenFAN firmware
6. Within few seconds, the drive will disappear and you should see the white LED on the OpenFAN blinking
7. The board should be flashed and ready to go now
8. As a precaution and just to be 100% sure, you should power cycle the OpenFAN before using it.


## How to build firmware?

OpenFAN controller uses Pico2040 as the main microcontroller.

In order to build the firmware, you will need to install and setup Pico-SDK first. After that you can run `build.sh` script or manually run through the following steps

- `cmake -B {path-to-pico-sdk-directory} -S {path-to-OpenFAN-firmware-src-directory}`
- `cmake -C build`

If everything runs successfully, you should see a `build` folder and inside there should be a `.uf2` file that you can use for firmware upgrade.

