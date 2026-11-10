# HARMONI Custom Detector



## Setup

Dowload the custom model from the HARMONI path:
```  bash
sh ./harmoni_detectors/harmoni_detcustom/get_ir_custom_model.sh
```

## Usage

Run the following commands in order to run camera service and custom service :

```  bash
roslaunch harmoni_detcustom detcustom_service.launch
```

While in the harmoni_full_detector container, you can run opneface service:

```  bash
roslaunch harmoni_openface openface_service.launch
```

It returns a boolean with interaction rupture dection (1: present, 0: absent )

## Testing

To test the module use the following command

```  bash
rostest harmoni_detcustom detcustom.test
```
It utilizes mock harmoni_openface and harmoni_opensmile data as given in test_data/openface_data.txt and test_data/opensmile_data.txt respectively. Alternate data may be provided using the param test_detcustom_input_openface and test_detcustom_input_opensmile.

