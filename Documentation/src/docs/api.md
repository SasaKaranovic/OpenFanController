# OpenFAN API Documentation


OpenFAN provides an API that allows you to interact with it remtely or integrate OpenFAN into another system.

You can use this for example to monitor/log the fan RPM, or to apply different FAN profiles based on system temperature/load etc. You could also use it for detection of stalled/blocked fans or to coordinate multiple OpenFan instances.


## Configuration

The API server runs on port `3000` and accepts HTTP GET/POST requests.
In order to send requests and read responses, you will use the machine IP address. If the API server is running on the locally, you can access it via `localhost` or `127.0.0.1`.

Assuming you are running OpenFAN locally, the base API URL can be accessed at `http://localhost:3000/api/v0` and at the same time you would be able to access the GUI interface via your web-broser on `http://localhost:3000`.

The OpenAPI server will serve both the API and the GUI at the same time.

!!! note annotate "config.yaml"

    If port `3000` is already in use or you wish to use a different port, you can change it in the `config.yaml` file.


## Access remotely over network
If you are accessing/controling a remote OpenFAN, you would use the IP address of the remote machine on which OpenFAN is running. For example if you want to access OpenFAN API on a networked machine that has IP address `192.168.0.55` you would use `http://192.168.0.55:3000/api/v0` as the API base URL and `http://192.168.0.55:3000` to access the GUI interface.

!!! danger annotate "Security!"

    OpenFAN API does NOT use any encryption or authentication. So make sure that you limit access to the API via your firewall .

## Messaging

All transactions begin with the client sending a `HTTP/GET` or `HTTP/POST` request to the OpenFAN API server.

All responses from the server are JSON formatted and *always* contain three keys: status, message and data. Although they can be empty/null if they should be ignored (ie. there is an error, status and message keys will be populated but data will be null).

Response always has the following structure:

```json
{
    "status": "...",
    "message": "...",
    "data": { }
}
```

---

## Fan Status - `/api/v0/fan/status`


Use this function to get fan status (RPM values) from the server.


### Example: Get RPM of all fans

> `GET` - `http://localhost:3000/api/v0/fan/status`




Response format (JSON)

```json
{
    "status": "ok",
    "message": "",
    "data": {
        "0": 1009,
        "1": 0,
        "2": 1007,
        "3": 0,
        "4": 1011,
        "5": 0,
        "6": 0,
        "7": 1009,
        "8": 0,
        "9": 1007
    }
}
```


---


## Fan Set RPM - `/api/v0/fan/{fan}/rpm?value={rpm}`

Use this function to set fan number `{fan}` to RPM value of `{rpm}`.



!!! note annotate "Note"

    Fan index must be a value from `1-10`

    RPM value must be within `[500-9000]` range.

### Example: Set fan #1 to 1200 PRM:

> `GET` - `http://localhost:3000/api/v0/fan/1/rpm?value=1200`

Reponse is a JSON object

```json
{
    "status": "ok",
    "message": "Update queued. Fan:1 RPM:1200",
    "data": null
}
```

---


## Fan Set PWM - `/api/v0/fan/{fan}/pwm?value={rpm}`

Use this function to set **PWM** of fan number `{fan}` to `{pwm}` percent.



!!! note annotate "Note"

    Fan index must be a value from `1-10`

    RPM value must be within `[0-100]` range. Where 0 means off (or lowest speed possible) and 100 means fully on.

### Example: Set fan #1 to 60% PMW:

> `GET` - `http://localhost:3000/api/v0/fan/1/pwm?value=60`


Reponse is a JSON object

```json
{
    "status": "ok",
    "message": "Update queued. Fan:1 PWM:60",
    "data": null
}
```

---


## Fan Profiles List - `/api/v0/profiles/list`

Use this function to retrieve a list of all the fan profiles that are available.

New fan profiles can be created through the GUI (recommened) or via API.


### Example: Retrieve available fan profiles

> `GET` - `http://localhost:3000/api/v0/profiles/list`


Reponse is a JSON object

```json
{
    "status": "ok",
    "message": "There are 3 FAN profiles available.",
    "data": [
        {
            "type": "rpm",
            "values": [
                1000,
                1000,
                1000,
                1000,
                1000,
                1000,
                1000,
                1000,
                1000,
                1000
            ],
            "name": "1000 RPM"
        },
        {
            "type": "PWM",
            "values": [
                100,
                100,
                100,
                100,
                100,
                100,
                100,
                100,
                100,
                100
            ],
            "name": "MadMax"
        },
        {
            "type": "RPM",
            "values": [
                1200,
                1200,
                1200,
                1200,
                1200,
                1200,
                1200,
                1200,
                1200,
                1200
            ],
            "name": "1200RPM"
        }
    ]
}
```

Above is an example response containing available fan profiles. The server has 3 fan profiles that have been previously defined.

Each profile has `name`, `type` and `values` keys.

`name` key is the name that has been given to this profile and is used to uniquely identify it. There can not be two profiles with the same name. This also allows us to easily overwrite/update profiles by specifying the same name.

`type` indicates if the values in the profile are to be treated as `RPM` values or `PWM`. Given that lowest `RPM` is 500RPM and highest PWM is 100%, we can easily distinguish between RPM/PWM profile so this key is more for quality of life and potentially catching typos and edge cases (ie. During profile creation setting RPM to 70 instead of 700).

`values` is an array of exactly 10 elements each corresponding to fans 1-10. These values will be assigned to each fan and be used as RPM/PWM value depending on `type`.


!!! note annotate "How are profiles stored?"

    All fan profiles are stored as plain-text inside `config.yaml` file.
    If you directly add/remove/modify a profile inside `config.yaml` file, you will have to restart the server app in order for changes to take effect. You can also easily create/update/remove profiles via the provided GUI app.

    By backing up your `config.yaml` you will also back up all of your fan profiles.


---


## Fan Profile Apply - `/api/v0/profiles/set?name={profile_name}`

Use this function to apply a `{profile_name}` fan profile. This profile has to be created first (either through GUI (recommended) or via API).


!!! note annotate "Profile names"

    It is recommended that you limit you profile names to 'standard' ASCII characters and properly encode any spaces, dashes and any other special characters.

### Example: Apply a fan profile named `1000RPM`

> `GET` - `http://localhost:3000/api/v0/profiles/set?name=?value=1000RPM`


Reponse is a JSON object
```json
{
    "status": "ok",
    "message": "Profile `1000RPM` activated. Fan1=1000 RPM Fan2=1000 RPM Fan3=1000 RPM Fan4=1000 RPM Fan5=1000 RPM Fan6=1000 RPM Fan7=1000 RPM Fan8=1000 RPM Fan9=1000 RPM Fan10=1000 RPM.",
    "data": null
}
```

---

## Get System Information - `/api/v0/info`

Use this function to get information about the OpenFAN hardware, firmware and software version.

This function can be used to identify

- which hardware OpenFAN is running on
- what is the hardware architecture
- what is the firmware version curently running on the device
- what is the protocol version used for communication

It will also provide software information like release date and version.

### Example: Get system information

> `GET` - `http://localhost:3000/api/v0/info`


Reponse is a JSON object

```json
{
    "status": "ok",
    "message": "System information",
    "data": {
        "hardware": "HW_REV:03
                     MCU:PICO2040
                     USB:NATIVE
                     FAN_CHANNELS_TOTAL:10
                     FAN_CHANNELS_ARCH:5+5
                     FAN_CHANNELS_DRIVER:EMC2305",

        "firmware": "FW_REV:01
                     PROTOCOL_VERSION:01",

        "software": "Version: 0.1
                     Build:2023-09-29"
    }
}
```
---

