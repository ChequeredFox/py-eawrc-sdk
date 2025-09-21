# py-eawrc-sdk
SDK built with Python 3 to aid with access to EA WRC's live telemetry. 

# Install

- [Python 3.9+](https://www.python.org/downloads/)
- `pip install py-eawrc-sdk`


## Usage/Examples

NOTE - EA WRC must be launched at least once to generate telemmetry configuration files found in `%UserProfile%/Documents/My Games/WRC/telemetry/`

#### Basic Usage
```python
#!python3
import pyeawrcsdk
wrc = pyeawrcsdk.EAWRCSDK()
wrc.connect()
print(wrc['vehicle_speed'])
```

#### Simple Application Example
```python
#!python3
import eawrcsdk
import time

if __name__ == "__main__":
    wrc = eawrcsdk.EAWRCSDK()
    wrc.connect()
    while True:
        try:
            wrc.freeze_buffer_latest() #Freeze telemmetry data so all data retrieved is from the same telemmetry packet
            if wrc['game_total_time']: #check if data exists first
                ##
                ## application logic
                ##
                print(wrc['game_total_time'])
            time.sleep(1/30)
        except KeyboardInterrupt:
            break
    wrc.close()
    print("client closed")
```
## Feedback

Feel free to contact me if you'd like to contribute to this package. I'm relatively new to python and programming in general and created this package to provide core functionality to other python projects I'm working on. 

