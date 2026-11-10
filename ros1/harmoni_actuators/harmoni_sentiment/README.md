# HARMONI Sentiment

Sentiment analysis service to get whether a text has a positive or negative sentiment using the huggingface transformers library.

You can run this module in the `harmoni_full` container.

## Usage

The following documentation refers to the sentiment request.

The API for Sentiment has:

- Request Name: ActionType: REQUEST
- Body: data(str): input text that you want to run the sentiment analysis
- Response:
    - response (int): SUCCESS, or FAILURE
    - message (str): response from the sentiment detector (e.g., )


You can run the service as follows: 
```roslaunch harmoni_sentiment sentiment_service.launch```

## Parameters

Parameters input for the sentiment service corresponds the the $instand_id_param which includes:

|Parameters| Definition| Value |
|---|-----------|------------|
| model_name  | model name of the huggingface library for sentiment analysis |  str; "roberta-base"   |

Change the model_name in config/configuration.yaml to desired model. Default is 'roberta-base'.

## Testing

Before running rostest ensure the model has been downloaded.
The local test will save a wav file of the speech specified in the sentiment.test test_sentiment_input parameter in the temp_data directory. 

Use the command ```rostest harmoni_sentiment sentiment.test``` which will detect hte sentiment from a sentence in the test input.



## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_sentiment.html)

