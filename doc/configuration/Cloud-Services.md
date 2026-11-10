# Cloud Services

_What is needed to connect to cloud services._

Only set up the services you plan to use. HARMONI reads credentials from three places on the host,
all mounted in the containers by docker compose:

| Where | Used by |
|-------|---------|
| `HARMONI/.env` (copy of [`.env.example`](https://github.com/micolspitale93/HARMONI/blob/dev/harmoni2.0/.env.example), created by `./harmoni.sh ros2 setup` or `./harmoni.sh ros1 setup`) | OpenAI ChatGPT, Azure OpenAI Assistants, Azure Speech |
| `~/.aws` | AWS Polly (TTS), AWS Lex (bot) |
| `~/.gcp/private-keys.json/private-keys.json` | Google STT, Google Dialogflow |

`.env` is ignored by git: never commit your keys.




## Setup Amazon Accounts
(If you are planning to use Lex or Polly) Set up AWS account following these steps: 

Create an Amazon Web Services account. AWS has a 1 year free trial that includes a limited number of Polly usages.
Keep this in mind so you do not get charged money at the end of the year.

Once you've created an account, create an IAM user to access Polly and/or Lex.

    * Give the IAM user access permissions to AWS Polly and/or Lex.
    * Give the IAM user access keys. Be sure to save the secret key as you only have one chance to look at it.
    
https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html - Use this link to install the AWS CLI on your PC.

> **_NOTE:_** If you have already your credentials, you can follow the instructions from here!!

Then, in the terminal,
```bash
$ sudo apt-get install awscli
$ aws --version
$ aws configure
# Enter the IAM user access and secret keys here.
```

Note: The docker compose scripts expect your aws keys to be in ~/.aws



To check if your keys configured correctly, you can run the following:
```bash
$ aws configure
```

The result will print as follows (click the Enter button to move forward without editing the keys if they are setup properly):

```bash
AWS Access Key ID [****************XXXX]: 
AWS Secret Access Key [****************XXXX]: 
Default region name [XX-XXXX-X]: 
Default output format [json]: 
```


## Setup Google Accounts
If you are planning on using dialogflow or other google services (like speech to text):

You need to save your google credentials as described at the end of this section.
When you activate google account API, you can create credentials for connecting HARMONI with your account, following this instraction.
Get the API key (https://developers.google.com/maps/documentation/maps-static/get-api-key)
You must have at least one API key associated with your project.

To get an API key:

* Go to the Google Cloud Platform Console.
* Click the project drop-down and select or create the project for which you want to add an API key.
* Click the menu button and select APIs & Services > Credentials.
* On the Credentials page, click + Create Credentials > Create ID client OAuth.
* Click Service Account, fill the input text with your name. Set the role to Editor, and click end.
* Click the menu button and select APIs & Services > Credentials. In the Service Account table (at the bottom of the page) the account you just created will be displayed. Click on edit. Click on add new keys, and save it.
* Click Close.
* The new API key is listed on the Credentials page under API Keys.
(Remember to restrict the API key before using it in production.)
* Save private-keys.json

> **_NOTE:_** If you have already your credentials, you can follow the instructions from here!!


Set credentials on HARMONI by saving the json key generated in the previous steps on the host as
`~/.gcp/private-keys.json/private-keys.json` (`./harmoni.sh ros1 setup` creates the folder for you):

```bash
$ mkdir -p ~/.gcp/private-keys.json
$ nano ~/.gcp/private-keys.json/private-keys.json
# Copy and paste the json content generated in the previous steps.
```

This is the path used by default in the `credential_path` parameter of the Google services
(`$(env HOME)/.gcp/private-keys.json/private-keys.json`).


Note: Secret keys and configurations are done locally and mounted to images through the Docker-Compose.yml files. If you run the compose files before generating the keys you may need to delete and recreate the .aws and .gcp folders, as they will have been created with root only permission. Otherwise you should be able to edit them directly.

To check if your keys are mounted correctly after having installed HARMONI, please check if the private-keys.json file exists in ~/.gcp/ by running the following in the container harmoni_full:
```bash
$ cd ~/.gcp
$ ls
```

If the result printed is a file it will be white and it means that everthing is setup correcly, while if it is a folder its colour will be purple (so please follow the steps reported in the Troubleshooting below).
I


## Setup OpenAI ChatGPT [after having installed HARMONI]
Set up your OpenAI account: https://platform.openai.com/

> **_NOTE:_** If you have already your credentials, you can follow the instructions from here!!


Then edit the `.env` file in the root of the HARMONI repository (created by `./harmoni.sh ros2 setup` or `./harmoni.sh ros1 setup`,
or copy `.env.example` to `.env`) and fill in:

```bash
OPENAI_ORGANIZATION=<your organization id>
OPENAI_API_KEY=<your api key>
```

You find both values in your OpenAI account settings.


## Setup Azure OpenAI Assistants (group interaction orchestrator)

The `assistant_service.py` of `harmoni_bot` uses the [Azure OpenAI Assistants API](https://learn.microsoft.com/azure/ai-services/openai/how-to/assistant).

1. In the [Azure portal](https://portal.azure.com) create an **Azure OpenAI** resource and deploy a model (e.g. `gpt-4o-mini`).
2. In Azure AI Foundry create an **Assistant** on that deployment. Use as instructions the orchestrator prompt
   (see the `PROMPT` constant in `harmoni_dialogues/harmoni_bot/src/harmoni_bot/assistant_service.py`) and copy its id (`asst_...`).
3. Add the endpoint and key of the resource (Keys and Endpoint page) to `.env`:
   ```bash
   AZURE_OPENAI_API_ENDPOINT=https://<your-resource>.openai.azure.com/
   AZURE_OPENAI_API_KEY=<your key>
   ```
4. Set the assistant id in `harmoni_dialogues/harmoni_bot/config/configuration.yaml`:
   ```yaml
   bot:
     default_param:
       assistant_id: "asst_..."
       participants: "Sarah, Jane, Alex"   # names of the participants
       num_speaker: 3
       scenario: "The topic of this group conversation is AI in society."
   ```
5. Test it with `rostest harmoni_bot assistant.test`.


## Setup Azure Speech (speaker diarization)

The `sd_azure_service.py` of `harmoni_stt` uses the Azure Speech
[conversation transcription](https://learn.microsoft.com/azure/ai-services/speech-service/get-started-stt-diarization) to know who is talking.

1. In the [Azure portal](https://portal.azure.com) create a **Speech** resource.
2. Add its key and region to `.env`:
   ```bash
   MICROSOFT_SPEECH_KEY=<your key>
   MICROSOFT_SPEECH_REGION=<region, e.g. westeurope>
   ```
3. Set the participants in `harmoni_detectors/harmoni_stt/config/sd_azure_configuration.yaml`
   (`names: "Sarah,Jane,Alex"`: the first speaker detected, `Guest-1`, is mapped to the first name, and so on).
4. Test it with `rostest harmoni_stt sd_azure.test` and speak when asked.


## Troubleshooting

If something went wrong and you cannot find the private-keys.json file in ~/.gcp/ (but instead you find a folder you can do the following)

```bash
$ cd ~
$ cd .gcp
$ cd private-keys.json
$ nano private-keys.json
# Copy and paste the json content generated in the previous steps.
```

Note that you then need to change the [configuration file](https://github.com/micolspitale93/HARMONI/blob/dev/harmoni2.0/harmoni_detectors/harmoni_stt/config/google_configuration.yaml) of the corresponding google service (speech to text) as follows:
```bash
stt:
  default_param:
    language_id: "en-UK" #"en-US"
    sample_rate: 48000 #16000 #44100 for wav audio file, 16000 for wav file from mic, 48000
    audio_channel: 1
    subscriber_id: "default"
    credential_path: "$(env HOME)/.gcp/private-keys.json/private-keys.json" #path where private keys are mounted, if the credentials mount correctly this should be "$(env HOME)/.gcp/private-keys.json"
    wait_duration: 2
    max_silence: 10 #s

```
