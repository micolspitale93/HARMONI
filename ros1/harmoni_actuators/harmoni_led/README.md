# HARMONI LED

Shows the state of the dialogue with the LEDs of the robots: the Furhat LED (Furhat Remote API) and
the chest LEDs of the NAO (through the NAO bridge `apis_nao_node.py`, topic `/led_nao/set`).
In the group interaction, red means that the robots are processing and green that they are listening.

You can run this module in the `harmoni_full` container.

## Usage

The API for LED has:

- Request Name: ActionType: DO
- Body: data(str): the color, `"red"` or `"green"`
- Response:
    - response (int): SUCCESS, or FAILED

You can run the service as follows:
```roslaunch harmoni_led led_service.launch```

The NAO bridge (`rosrun harmoni_speaker apis_nao_node.py`, in the `harmoni_nao` container) must be running
for the NAO LEDs: the service sends it the NAO IP on `/nao/connect`.

## Parameters

Parameters in `config/configuration.yaml` (`led/default_param`):

| Parameters | Definition | Value |
|------------|------------|-------|
| furhat_robot_ip | IP address of the Furhat robot | str; e.g., "192.168.1.103" |
| nao_robot_ip | IP address of the NAO robot | str; e.g., "192.168.1.100" |

## Testing

Unit tests that do not need ROS nor robots (run from the `ros1/` folder):

```bash
python3 -m pytest harmoni_actuators/harmoni_led
```

On ROS 2 the same feedback is given by the `furhat_led` and `nao_led_http` backends of the core.

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_led.html)
