# OpenFAN Controller - Firmware


## How to install latest firmware onto the board?

OpenFAN Controller supports loading new firmware over USB.

Latest firmware release is stored in `Release Binaries` folder. Download the latest firmware version to your PC.

- Put your OpenFAN Controller into a bootloader mode.
- OpenFAN Controller will appear as a USB mass storage device on your PC.
- Copy the `.uf2` file to the OpenFAN Controller drive.
- After a few seconds, the mass storage device will disconnect and OpenFAN Controller COM port should appear.
- Your OpenFAN controller is ready to go.


## How to build firmware?

OpenFAN controller uses Pico2040 as the main microcontroller.

In order to build the firmware, you will need to install and setup Pico-SDK first. After that you can run `build.sh` script or manually run through the following steps

- `cmake -B {path-to-pico-sdk-directory} -S {path-to-OpenFAN-firmware-src-directory}`
- `cmake -C build`

If everything runs succesfully, you should see a `build` folder and inside there should be a `.uf2` file that you can use for firmware upgrade.


## GitHub Release

Not everyone wants to build the firmware from scratch, most people just want to get the OpenFAN running, and that's cool.

Once the project is publicly released, we will use a GitHub actions to automatically generate new firmware binaries (`.uf2` files) whenever there is a new version of the firmware.

These binaries can then be downloaded and used for firmware upload.
