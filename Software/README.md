# OpenFAN Controller - Software


## How to run the software?

There are many ways to run the OpenFAN software.

### Running from source [Win/Linux/Mac]

On any OS, if you have Python 3.9 (or higher) and PIP installed, you can run from source code.

1. Clone this repository and navigate to `Software/Python` folder.
2. Install Python dependencies by running `pip install -r requirements.txt`
3. Run the main application with `python webserver.py`
4. Open `http://localhost:3000` to access the Web GUI
<br><br>

### Running with Docker [Windows/Linux/Mac]

You can run OpenFAN in a Docker container.

Since with OpenFAN you can control fans remotely (via API and/or Web GUI), this can be very helpful for remotely managing fans on your servers or media stations.

To create a Docker container, log into your machine and run following commands

1. docker build github.com/sasakaranovic/openfancontroller -t sasakaranovic/openfan
2. docker run --name OpenFAN -p 3000:3000 --device=/dev/ttyACM0 -e OPENFANCOMPORT=/dev/ttyACM0 sasakaranovic/openfan:latest
3. Make sure you can access the server running this container and configure your firewall to allow port `3000` (if necessary)
4. Open `http://server-ip:3000` to access the Web GUI
<br><br>

### Using Fan Control [Windows]

You can use your OpenFAN directly from [Fan Control](https://getfancontrol.com/).

Fan Control is a highly focused fan controlling software for Windows.

To use OpenFAN with Fan Control, you can download the `FanControl.OpenFAN` plugin.

1. Install [Fan Control](https://getfancontrol.com/)
2. Download [FanControl.OpenFAN](https://github.com/SasaKaranovic/FanControl.OpenFan) plugin
3. Copy `FanControl.OpenFan.dll` to Fan Control's `Plugins` folder. (You might need to "unlock" the dll in its properties.)
4. Restart Fan Control
5. Fan Control will display all OpenFAN fan controls and RPM sensors
<br><br>



## How to debug/develop the software?

OpenFAN Controller is written in Python. In order to run the code, you will need to install Python 3.9 or higher.

After that, you will need to install the PIP Python package manager.

### Install dependencies

In order to install project dependencies you can open a terminal and navigate to the OpenFAN `Software/Python` directory.

Then type `pip install -r requirements.txt`

This will install all the necessary dependencies.


### How to run the server application

In your terminal, navigate to the `Software/Python` directory of OpenFAN and type `python webserver.py`

This will start the OpenFAN server. After this you can start using the gui through web browser by openning `https://localhost:3000` or use the API as described in the documentation.


### Running without Python or Docker?

There are multiple ways of converting a python code to an executable (ie. `py2exe`, `pyinstaller` etc).

There are many tutorials on how to do this depending on your operating system.

In the future, I will try to use GitHub Actions to generate binaries and installers that you can use to easily install and run OpenFAN software.
