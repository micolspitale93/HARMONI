# HARMONI Web

Harmoni web supports the creation of a custom web interface for use with HARMONI.
You can run this module in the `harmoni_full`  container. 
## Usage


The following documentation refers to the web request.

The API for Web has:

- Request Name: ActionType: REQUEST
- Body: data(str):  string of json which contains two items: {"container_id": str, "set_view": str}
                container_id: id of the container found in the ./web/src/config/config.json file
                set_view: the content you want to set your container of (e.g., string of image location, text)
- Response:
    - response (int): SUCCESS, or FAILURE
    - message (str): content of the response message (e.g., what the user click on the GUI)



- Request Name: ActionType: DO
- Body: data(str):  string of json which contains two items: {"container_id": str, "set_view": str}
                container_id: id of the container found in the ./web/src/config/config.json file
                set_view: the content you want to set your container of (e.g., string of image location, text)
- Response:
    - response (int): SUCCESS, or FAILURE
    - message (str): no message in response for a DO method

You can run the service as follows: 
```roslaunch harmoni_web web_service.launch```

Then you have to open in a tab the webpage "http://172.18.3.4:8082/"


## Parameters
There are no parameters input for the web service: 


## Testing
To test that the amazon polly speaker has been configured properly, use the command ```rostest harmoni_web web.test```
Please remember to open in the tab of your browser the webpage "http://172.18.3.4:8082/"

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_web.html)