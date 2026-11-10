# HARMONI rl

This package wraps custom trained chatrl services that can be used with HARMONI.
You can run this module in the `harmoni_full` container.

Note that this is a custom RL model designed for a user study. You can substitute the model with yours, or even created your own new module service.

## Usage


The API for RL has:
- Request Name: ActionType: request
- Body: data(str)
- Response:
    - response (int): SUCCESS, or FAILURE 
    - message (str): response from the AWS lex

Dowload the custom model from the HARMONI path:
```  bash
sh ./harmoni_dialogues/harmoni_rl/get_rl_model.sh
```
Choice of model to be used can be specified in harmoni_rl/config/configuration.yaml

## Parameters

Parameters input for the aws lex service: 

| Parameters           | Definition | Values |
|----------------------|------------|--------|
|subscriber_id               |  id of the subscriber          |  str; "default"      |
|model_name              |   name of the model pre-trained         |   str; e.g., "dqn.pt"     |
|model_dir             |   directory where the model is stored         | str; e.g., "$(find harmoni_rl)/../../harmoni_models/rl/"       |
|dataset           |  directory where the dataset is stored             |str; e.g., "$(find harmoni_rl)/../../harmoni_models/rl/dataset.h5"       |
|log_dir           |  directory where the logs are stored             |str; e.g., "$(find harmoni_rl)/logs/"       |


## Testing

The module can be tested using
```  bash
rostest harmoni_rl rl.test
```

## Troubleshooting
If an error like that appears give permission to write to the harmoni_models folder (using the command `chmod +777`)
```  bash
This script should be run from the HARMONI directory in order to place the models in a parallel directory
mkdir: cannot create directory ‘harmoni_models’: Permission denied
``` 

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_rl.html)