# HARMONI Bot

This package wraps different chatbot services that can be used with HARMONI. Currently we support AWS Lex, Google Dialogflow, ChatGPT and the OpenAI Assistants API (on Azure), used as orchestrator of the group interaction. Rasa is a high priority on our roadmap for local chatbot functionality.

You can run this module in the `harmoni_full` container.


## Usage

### AWS Lex
The API for AWS Lex Bot has:
- Request Name: ActionType: DO
- Body: data(str)
- Response:
    - response (int): SUCCESS, or FAILURE 
    - message (str): response from the AWS lex


### Google DialogFlow
The API for Google DialogFlow has:
- Request Name: ActionType: REQUEST
- Body: data(str)
- Response:
    - response (int): SUCCESS, or FAILURE 
    - message (str): response from the dialogflow


### ChatGPT
The API for ChatGPT has:
- Request Name: ActionType: REQUEST
- Body: data(str): input text
- Response:
    - response (int): SUCCESS, or FAILURE 
    - message (str): response from the chatgpt


### OpenAI Assistant (Azure)
The Assistant service keeps the whole conversation in an Assistants API *thread* and, at each turn, asks the
assistant (the orchestrator of the group interaction) whether one of the robots should intervene.

The API for the Assistant has:
- Request Name: ActionType: REQUEST
- Body: data(str): string representation of a python list of messages in the form `"*<role>* <content>"`,
  e.g. `"['*user* Sarah: I think AI will change education']"`. Only the last message is appended to the thread.
- Response:
    - response (int): SUCCESS, or FAILED
    - message (str): the assistant answer. For the orchestrator (`service_id: default`) it is a JSON object:
      `{"intervene": bool, "agent": "Mover" | "Opposer", "response": str, "explanation": str, "addressee": str}`.
      On any error (API, connection, rate limit, malformed input) the state is FAILED and the message is
      "Can you please repeat what you said?".

The answer is also published on `/harmoni/dialoging/bot/<service_id>`. The orchestrator publishes the id of the
thread on `/harmoni/dialoging/bot/<service_id>/thread_id`, so that other assistants (e.g. `mover`, `opposer`)
can join the same conversation.

Credentials (`AZURE_OPENAI_API_ENDPOINT`, `AZURE_OPENAI_API_KEY`) are read from the `.env` file in the root of the
repository, see [Cloud Services](https://harmoni-20.readthedocs.io/en/latest/configuration/Cloud-Services.html).

You can run the service with the following command (the Assistant is the default, select the others with
`use_aws_lex:=true use_assistant:=false`, `use_google:=true ...`, `use_chatgpt:=true ...`):
```roslaunch harmoni_bot bot_service.launch```

## Parameters

### AWS Lex 
Parameters input for the aws lex service: 

| Parameters           | Definition | Values |
|----------------------|------------|--------|
|user_id               |   name of the use in your AWS Lex         |str; e.g., "Micol"        |
|bot_name              |   the name of the bot you have created in AWS Lex         |  str; e.g., "QTRobot"      |
|bot_alias             |   the alias name of your published bot in AWS Lex         |  str; e.g., "DemoBot"     |
|region_name           |   the region of your AWS         |  str; e.g., "eu-west-2"      |


### Google DialogFlow 

| Parameters           | Definition | Values |
|----------------------|------------|--------|
|project_id               |  the ID of your project in the Cloud Service from Google        |str; e.g., "agent1-ewhnht"     |
|language              |   the language for your dialogue         |  str; e.g., "it"     |
|session_id             |   the name of your session        |  str; e.g., "test_bot"  |
|credential_path           |   path where your credentials are stored      |  str; e.g., "$(find harmoni_stt)/config/private-keys.json"      |


### OpenAI ChatGPT

| Parameters           | Definition | Values |
|----------------------|------------|--------|
|model                 |  OpenAI model         |str; e.g., "gpt-4o-mini"     |

### OpenAI Assistant

| Parameters           | Definition | Values |
|----------------------|------------|--------|
|assistant_id          |  id of the assistant created on Azure OpenAI       |str; e.g., "asst_..."     |
|service_id            |  `default` for the orchestrator (creates the thread), any other id joins the thread of the orchestrator  |str; e.g., "default"     |
|participants          |  names of the participants, added to the assistant instructions       |str; e.g., "Sarah, Jane, Alex"     |
|num_speaker           |  number of participants       |int; e.g., 3     |
|scenario              |  topic of the conversation, added to the assistant instructions       |str     |

## Testing.



AWS Lex module can be tested using

```  bash
rostest harmoni_bot lex.test
```

ChatGPT module can be tested using

```  bash
rostest harmoni_bot chatgpt.test
```

The OpenAI Assistant can be tested using (requires the Azure credentials)

```  bash
rostest harmoni_bot assistant.test
```

Unit tests that do not need ROS nor credentials (run from the repository root):

```  bash
python3 -m pytest harmoni_dialogues/harmoni_bot
```



## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_bot.html)