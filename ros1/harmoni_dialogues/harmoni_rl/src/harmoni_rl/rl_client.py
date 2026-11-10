import os
import ast
import pandas as pandas
import d3rlpy
import gym
import rospy
import random
import json
from gym import spaces
import pandas as pd
import numpy as np
from sklearn import preprocessing as pre
from d3rlpy.dataset import MDPDataset
from d3rlpy.algos import DQN, DoubleDQN, NFQ, SAC, DDPG


N_DISCRETE_ACTIONS = 3
N_DISCRETE_OBSERVATIONS = 11
MIN_REWARD = -20
MAX_REWARD = 20

class RLActionsName:
    ACTION1 = "1" #do nothing
    ACTION2 = "2" #ask follow up question
    ACTION3 = "3" #move to the next episode




class PPEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self, observations, rewards):
        super(PPEnv, self).__init__()

        self.observation = observations
        #self.action = 
        self.reward = rewards
        self.reward_range = (MIN_REWARD, MAX_REWARD)
        self.action_space = spaces.Discrete(N_DISCRETE_ACTIONS)#spaces.Box(low=0, high=1, shape=(N_DISCRETE_ACTIONS, ), dtype=np.float32)#spaces.Discrete(N_DISCRETE_ACTIONS)
        self.observation_space = spaces.Box(low=0, high=100.0, shape=(N_DISCRETE_OBSERVATIONS, ), dtype=np.float32)#spaces.Discrete(N_DISCRETE_OBSERVATIONS)
        print(self.action_space, self.observation_space)
        #print(self.action[1])

    def _next_observation(self):
        # Append additional data and scale each value to between 0-1
        #reshape array so that it works with sklearn
        len_obs = len(self.observation)
        #self.observation = self.observation.reshape(-1, 1)
        #n_features = int(len(self.observation)/len_obs)
        #normalize all values to be between 0 and 1
        #obs = pre.MinMaxScaler().fit_transform(self.observation)
        #self.observation = obs.reshape(len_obs, n_features)
        ob = np.array(self.observation)
        print(f'Observation: {self.observation}')
        print(f'Reward: {self.reward}')
        return ob

   

    def step(self, action):
        # Execute one time step within the environment
        print(action)
        reward = self.reward
        done = True
        obs = self._next_observation()
        return obs, reward, done, {}

    def reset(self):
        # Set the current step to a random point within the data frame
        return self._next_observation()

    def render(self, mode='human', close=False):
        # Render the environment to the screen
        print(f'Observation: {self.observation}')
        print(f'Reward: {self.reward}')

class RLCore():
    def __init__(self):
        super(RLCore, self).__init__()

    def setup(self, model_dir, model_name, dataset, participant_name, session):
        # setup algorithm
        
        dataset = MDPDataset.load(dataset)
        self.dqn = DQN(use_gpu = False)
        # initialize neural networks before loading parameters
        self.dqn.build_with_dataset(dataset)
        # load pretrained policy
        if session == 1:
            self.dqn.load_model(model_dir + model_name)
            self.first_time = True
        else:
            self.dqn.load_model(model_dir + participant_name+ "-" + model_name)
            self.first_time = False
        self.model_dir = model_dir
        self.model_name = model_name
        self.participant_name = participant_name
        
        

    def start_training(self, env, observations, logdir):
       
        # experience replay buffer
        self.buffer = d3rlpy.online.buffers.ReplayBuffer(maxlen=100000, env=env)
        # exploration strategy
        # in this tutorial, epsilon-greedy policy with static epsilon=0.3
        self.explorer = d3rlpy.online.explorers.ConstantEpsilonGreedy(0.3)
        self.dqn.fit_online(
            env,
            self.buffer,
            self.explorer,
            n_steps=1,  # train for 100K steps
            logdir = logdir,
            #eval_env=eval_env,
            #n_steps_per_epoch=1,  # evaluation is performed every 1K steps
            #update_start_step=1,  # parameter update starts after 1K steps
        )
        observation = np.array(observations)
        action = self.dqn.predict([observation])[0]
        self.dqn.save_model(self.model_dir + self.participant_name+ "-" + self.model_name )
        if self.first_time:
            self.dqn.load_model(self.model_dir + self.participant_name+ "-" + self.model_name )
            self.first_time = False
        return str(action + 1)

    def test(self):
        action = random.choices(["1", "2", "3"])
        return action[0]

    def batch_rl(self, observation):
        observation = np.array(observation)
        action = self.dqn.predict([observation])[0]
        return str(action + 1)

