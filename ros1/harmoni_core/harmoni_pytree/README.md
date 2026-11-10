# HARMONI Pytree

PyTree is one among the several ways to implement behaviour trees.  
A tree in pytree is made of two elements: nodes and leaves.
Nodes can be of different nature but in general they belong to the family of composites (sequence, parallel, selector). The management of these elements it’s not something that users have to do, everything has already been done by the creators of pytree. 
Leaves come from a single element called “behaviour” and these are the components that users can create. Even if pytree made some basic behaviours available for us (you can find some of them [here](https://py-trees.readthedocs.io/en/devel/modules.html#module-py_trees.behaviours)), developers are required to create their own behaviours ([skeleton of behaviour](https://py-trees.readthedocs.io/en/devel/behaviours.html#skeleton)). We provide some leaves that represent the pytree version of clients of HARMONI.

## Setup

 For graphicviz run:
 
```bash 
$ sudo apt install graphviz
``` 
## Usage

The execution of a tree is done by ticking it.<br />
A tick starts from the root and then is propagated down in the tree up to leaves. Leaves will perform their tasks and in the end compute a state that will be returned and propagated back until the root.<br />
As mentioned before a tree is composed of nodes and leaves. Since all the leaves are behaviours that have their own class we suggest creating a different script for the body that will import all the behaviours that it needs (an example [here](https://py-trees.readthedocs.io/en/devel/trees.html#skeleton))
You can notice that after creating the tree all you need to do is call the function `behaviour_tree.tick_tock()` that will take care of ticking the tree. Parameters `pre_tick_handler` and `post_tick_handler` are used to lick functions that will be executed respectively before and after the tickling of the tree. In general they are used to see the status of the tree and additional information like the content of the blackboards.
We suggest adding a special element of the family of visitors that is called *snapshot visitor*. This component is used combined with `display.unicode_tree` to also show the statue of the visited element in the tree.<br />
You can add it by adding the following lines in the declaration of the behaviour tree

```  
snapshot_visitor = py_trees.visitors.SnapshotVisitor()
behaviour_tree.visitors.append(snapshot_visitor)
```
and then adding in the parameter `visited` in `dispaly.unicode_tree`  like that

```  
py_trees.display.unicode_tree(
            root=behaviour_tree.root,
            visited=snapshot_visitor.visited)
```
You can also decide to manually tick the tree by running `behaviour_tree.tick()` instead of `tick_tock()` function. 
PyTree offers a lot of components and useful tools that developers can use in their trees but here we will mention **composites** and **blackboards**. We recommend reading the documentation for understand all the concepts:   [https://py-trees.readthedocs.io/en/devel/behaviours.html](https://py-trees.readthedocs.io/en/devel/behaviours.html)

### Composites

Composites are responsible for directing the path traced through the tree on a given tick (execution). They are the factories (Sequences and Parallels) and decision makers (Selectors) of a behaviour tree.
Composite behaviours typically manage children and apply some logic to the way they execute and return a result, but generally don’t do anything themselves. Perform the checks or actions you need to do in the non-composite behaviours.
[https://py-trees.readthedocs.io/en/devel/composites.html#composites](https://py-trees.readthedocs.io/en/devel/composites.html#composites)

### Blackboards

Blackboards are not a necessary component of behaviour tree implementations, but are nonetheless, a fairly common mechanism for sharing data between behaviours in the tree.
[https://py-trees.readthedocs.io/en/devel/blackboards.html#blackboards](https://py-trees.readthedocs.io/en/devel/blackboards.html#blackboards)

## Leaves Available
We have implemented a set of leaves that can be used and easily integrated in your behaviour tree.


### Microphone

This leaf is the harmoni_microphone client which starts (ON) the sensing from the microphone. It has the following blackboard clients:

BlackBoard Client  [writer]:
Client Data
- namespace: SensorNameSpace.microphone.name
- name: SensorNameSpace.microphone.name
- read: set()
- write: {'/result'}

Variables
- /microphone/result: py_trees.common.Status

### Facial Expressions


This leaf is the harmoni_face client which does (DO) the facial expressions. It has the following blackboard clients:

BlackBoard Client 1  [reader]:
Client Data
- namespace: ActuatorNameSpace.face.name
- name: ActuatorNameSpace.face.name
- read:  {'/face_exp'}
- write: set() 

Variables
- /face/face_exp: "[{'start': 1, 'type': 'viseme', 'id': 'POSTALVEOLAR'}]"



BlackBoard Client 2  [reader]:
Client Data
- namespace: PyTreeNameSpace.scene.name
- name: PyTreeNameSpace.scene.name
- read:  {'/nlp'}
- write: set() 

Variables
- /scene/nlp: 0


### TTS AWS Polly

This leaf is the harmoni_tts client which requests (REQUEST) the synthetisation of the text. It has the following blackboard clients:


BlackBoard Client 1 [reader]:
Client Data
- namespace: DialogueNameSpace.bot.name
- name: DialogueNameSpace.bot.name
- read:  {'/result'}
- write: set() 

Variables
- /bot/result: "{'message': 'Hi, my name is QT'}

BlackBoard Client 2 [reader]:
Client Data
- namespace: PyTreeNameSpace.scene.name
- name: PyTreeNameSpace.scene.name
- read:  {'/scene/nlp'}
- write: set() 

Variables
- /scene/nlp: 0


BlackBoard Client 3 [writer]:
Client Data
- namespace: ActuatorNameSpace.tts.name
- name: ActuatorNameSpace.tts.name
- read:  set()
- write: {'/tts/result'}

Variables
- /tts/result: "{
            "audio_frame": audio_frame,
            "audio_data": data_array,
            "behavior_data": str(behaviours),
           }"



### Web
This leaf is the harmoni_web client which does (DO) the visualisation on the web GUI. It has the following blackboard clients:

BlackBoard Client 1 [reader]:
Client Data
- namespace: ActuatorNameSpace.web.name
- name: ActuatorNameSpace.web.name
- read:  {'/web/image'}
- write: set() 

Variables
- /web/image: "[{'component_id':'img_only', 'set_content':'https://www.google.it/images/branding/googlelogo/2x/googlelogo_color_160x56dp.png'},{'component_id':'raccolta_container', 'set_content': ''}]"



If you want to use the API REQUEST instead, you can create ad-hoc web leaf, or just edit the current one. 



### Voice Activity Detection (VAD)

This leaf is the harmoni_vad client which start (ON) the voice activity detection. It has the following blackboard clients:

BlackBoard Client 1 [reader]:
Client Data
- namespace: DetectorNameSpace.vad.name
- name: DetectorNameSpace.vad.name
- read:  set() 
- write: {'/vad/result'}

Variables
- /vad/result: TODO


### Speaker

This leaf is the harmoni_speaker client which play (DO) the audio data or the audio file. It has the following blackboard clients:


BlackBoard Client 1 [reader]:
Client Data
- namespace: ActuatorNameSpace.tts.name
- name: ActuatorNameSpace.tts.name
- read:  {'/tts/result'}
- write: set() 

Variables
- /tts/result:"{
            "audio_frame": audio_frame,
            "audio_data": data_array,
            "behavior_data": str(behaviours),
           }" or "/root/harmoni_catkin_ws/src/HARMONI/harmoni_actuators/harmoni_tts/temp_data/tts.wav"


BlackBoard Client 2 [reader]:
Client Data
- namespace: PyTreeNameSpace.scene.name
- name: PyTreeNameSpace.scene.name
- read:  {'/scene/nlp'}
- write: set() 

Variables
- /scene/nlp: 0


### Sentiment

This leaf is the harmoni_sentiment client which requests (REQUEST) to analyse the sentiment of a text. It has the following blackboard clients:


BlackBoard Client 1 [writer]:
Client Data
- namespace: ActuatorNameSpace.sentiment.name
- name: ActuatorNameSpace.sentiment.name
- read:  set()
- write: {'/sentiment/result'}

Variables
- /sentiment/result:"[{'label': 'LABEL_1', 'score': 0.5187261700630188}]"


BlackBoard Client 2 [reader]:
Client Data
- namespace: DialogueNameSpace.bot.name
- name: DialogueNameSpace.bot.name + '/' + PyTreeNameSpace.trigger.name
- read:  {'/bot/result'}
- write: set() 

Variables
- /bot/result: "{'message': 'i really hate you'}"



### Image AI (YOLO)

This leaf is the harmoni_imageai client which requests (REQUEST) to detect something (in the test example it is to detect a person). It has the following blackboard clients:


BlackBoard Client 1 [writer]:
Client Data
- namespace: DetectorNameSpace.imageai_yolo.name
- name: DetectorNameSpace.imageai_yolo.name
- read:  set()
- write: {'/imageai_yolo/result'}

Variables
- /imageai_yolo/result:"person"


### OpenSmile

This leaf is the harmoni_opensmile client which start (ON) to detect and extract audio features. It has the following blackboard clients:


BlackBoard Client  [writer]:
Client Data
- namespace: DetectorNameSpace.opensmile.name
- name: DetectorNameSpace.opensmile.name
- read: set()
- write: {'/opensmile/result'}

Variables
- /opensmile/result: py_trees.common.Status


### OpenFace

This leaf is the harmoni_openface client which start (ON) to detect and extract facial action units. It has the following blackboard clients:


BlackBoard Client  [writer]:
Client Data
- namespace: DetectorNameSpace.openface.name
- name: DetectorNameSpace.openface.name
- read: set()
- write: {'/openface/result'}

Variables
- /openface/result: py_trees.common.Status


### Reinforcement Learning

This leaf is the harmoni_rl client which request (REQUEST) to make a decision on the following action to take. It has the following blackboard clients:


BlackBoard Client 1 [reader and writer]:
Client Data
- namespace: PyTreeNameSpace.scene.name
- name: PyTreeNameSpace.scene.name
- read:  {'/scene/rl', '/scene/exercise'}
- write: {'/scene/action'}

Variables
- /scene/rl: 1
- /scene/action: 1
- /scene/exercise: 3


BlackBoard Client 2 [writer]:
Client Data
- namespace: DialogueNameSpace.rl.name
- name: DialogueNameSpace.rl.name
- read:  set()
- write: {'/rl/result'}

Variables
- /rl/result: "3" ##action to make


### Lips Sync

This leaf is the harmoni_face client which does (DO) the lips synchronisation. It has the following blackboard clients:


BlackBoard Client 1  [reader]:
Client Data
- namespace: ActuatorNameSpace.tts.name
- name: ActuatorNameSpace.tts.name
- read:  {'/tts/result'}
- write: set() 

Variables
- /tts/result: "{
            "audio_frame": audio_frame,
            "audio_data": data_array,
            "behavior_data": str(behaviours),
           }" or "/root/harmoni_catkin_ws/src/HARMONI/harmoni_actuators/harmoni_tts/temp_data/tts.wav"


### Google STT
This leaf is the harmoni_stt client which requests (REQUEST) to trascribe the audio data. It has the following blackboard clients:


BlackBoard Client 1 [reader and writer]:
Client Data
- namespace: PyTreeNameSpace.scene.name
- name: PyTreeNameSpace.scene.name
- read:  {'/scene/nlp'}
- write: set()

Variables
- /scene/nlp: 0


BlackBoard Client 2 [writer]:
Client Data
- namespace: DetectorNameSpace.stt.name
- name: DetectorNameSpace.stt.name
- read:  set()
- write: {'/stt/result'}

Variables
- /stt/result: "Hi" ##depending on what you are saying via the microphone

### Gesture

This leaf is the harmoni_gesture client which plays (DO) a gesture on the robot. It has the following blackboard clients:


BlackBoard Client 1  [reader]:
Client Data
- namespace: ActuatorNameSpace.gesture.name
- name: ActuatorNameSpace.gesture.name
- read:  {'/gesture/result'}
- write: set() 

Variables
- /gesture/result: "{'gesture':'QT/bye', 'timing': 0.5}" ## in the case of QT robot

### External Speaker

This leaf is the harmoni_speaker client which play (DO) the audio data or the audio file from an external speaker. It has the following blackboard clients:


BlackBoard Client 1 [reader]:
Client Data
- namespace: PyTreeNameSpace.scene.name
- name: PyTreeNameSpace.scene.name
- read:  {'/scene/sound'}
- write: set() 

Variables
- /scene/sound: "/root/harmoni_catkin_ws/src/HARMONI/harmoni_actuators/harmoni_tts/temp_data/tts.wav"

### DeepMind STT

This leaf is the harmoni_stt client which requests (REQUEST) to trascribe the audio data. It has the following blackboard clients:


BlackBoard Client 1 [writer]:
Client Data
- namespace: DetectorNameSpace.stt.name
- name: DetectorNameSpace.stt.name
- read:  set()
- write: {'/stt/result'}

Variables
- /stt/result: "Hi" ##depending on what you are saying via the microphone

### ChatGPT

This leaf is the harmoni_stt client which requests (REQUEST) to chatgpt to complete the dialogues and respond to the user. It has the following blackboard clients:


BlackBoard Client 1 [reader]:
Client Data
- namespace: PyTreeNameSpace.scene.name
- name: PyTreeNameSpace.scene.name
- read:  {'/scene/nlp', '/scene/utterance', '/scene/request'}
- write: set()

Variables
- /scene/nlp: 0
- /scene/utterance: "['*user* Can you help me out with a code?']"
- /scene/request: True


BlackBoard Client 2 [writer]:
Client Data
- namespace: DialogueNameSpace.bot.name
- name: DialogueNameSpace.bot.name
- read:  set()
- write: {'/bot/result', '/bot/feeling', '/bot/sentiment'}

Variables
- /bot/result: "" 
- /bot/feeling: "" 
- /bot/sentiment: "" 

### Camera

This leaf is the harmoni_camera client which starts (ON) the sensing from the videocamera. It has the following blackboard clients:

BlackBoard Client  [writer]:
Client Data
- namespace: SensorNameSpace.camera.name
- name: SensorNameSpace.camera.name
- read: set()
- write: {'/camera/result'}

Variables
- /camera/result: py_trees.common.Status

### Facial Expression Recognition (FER)

This leaf is the harmoni_camera client which starts (ON) the recognition of facial expressions. It has the following blackboard clients:

BlackBoard Client  [writer]:
Client Data
- namespace: DetectorNameSpace.fer.name
- name: DetectorNameSpace.fer.name
- read: set()
- write: {'/fer/result'}

Variables
- /fer/result: py_trees.common.Status

### LLM Assistant (group interaction)

This leaf (`leaves/assistant_service.py`) is the client of the harmoni_bot Assistant service (REQUEST). When the
current scene is LLM driven (`nlp != 0`) it sends the utterance of the participants and parses the JSON answer
of the orchestrator with `parse_agent_response` (which also accepts python-like dicts and plain text). It has the following blackboard clients:

- scene (READ): `utterance`, `nlp`
- bot (WRITE): `result`, `agent` (Mover/Opposer), `addressee`, `speak` (0 if the robots should stay silent)
- tts (WRITE): `result` (the sentence to say)

### Script Group Dialogue

This leaf (`leaves/script_group_dialogue_service.py`) moves the group interaction to the next scene of
`resources/group_interaction.json` and writes `scene/utterance`, `scene/nlp` and `scene/agent`.
See the [Group Interaction tutorial](https://harmoni-20.readthedocs.io/en/latest/tutorials/Group-Interaction.html).

### Diarization STT

This leaf (`leaves/sd_azure_service.py`) is the client of the Azure diarization STT (REQUEST) and writes the
transcription (`"<name>: <text>"`) on `stt/result`.

## Testing

Here are the steps that you can follow in order to run a demo of pytree in HARMONI. This demo show how work a small three with just two behaviours: microphone and stt.

1.  Create a valid google credential of using stt service: [https://cloud.google.com/speech-to-text/docs/before-you-begin#setting_up_your_google_cloud_platform_project](https://cloud.google.com/speech-to-text/docs/before-you-begin#setting_up_your_google_cloud_platform_project)
2.  Run the following command in the container to start the demo:

     ```  bash
     roslaunch harmoni_pytree mic_and_stt.launch
     ```

You will see some information about the structure of the tree and the way in which pytree engines tick the tree. Some blackboards are used to show the results of the leaves and in particular in backboards stt/result shows the result of the speech to text services.
### Unit tests

The leaves of the group interaction have unit tests that do not need ROS (run from the repository root):

```  bash
python3 -m pytest harmoni_core/harmoni_pytree
```
