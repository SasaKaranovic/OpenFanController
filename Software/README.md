# OpenFAN Controller - Software


## How to run/debug/develop the software?

OpenFAN Controller is written in Python. In order to run the code, you will need to install Python 3.7 or higher.

After that, you will need to install the PIP Python package manager.

### Install dependencies

In order to install project dependencies you can open a terminal and navigate to the OpenFAN `Software/Python` directory.

Then type `pip install -r requirements.txt`

This will install all the necessary dependencies.


### How to run the server application

In your terminal, navigate to the `Software/Python` directory of OpenFAN and type `python webserver.py`

This will start the OpenFAN server. After this you can start using the gui through web browser by openning `https://localhost:3000` or use the API as described in the documentation.


### Running in Docker

You can OpenFAN in a Docker container. You will need to give correct USB access to docker container.

For example:

`docker build github.com/sasakaranovic/openfancontroller -t sasakaranovic/openfan`

`docker run --name OpenFAN -p 3000:3000 --device=/dev/ttyACM0 sasakaranovic/openfan:latest`


### Running without Python or Docker?

There are multiple ways of converting a python code to an executable (ie. py2exe, pyinstaller etc).

There are many tutorials on how to do this.

In the future, we will try to use GitHub Actions to generate binaries that you can use to more easily install and run OpenFAN software.
