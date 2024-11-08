import os
import numpy as np
import pandas as pd
import grid2op
from lightsim2grid import LightSimBackend
from dreamer.Utils.customReward import LossReward, MarginReward
from dreamer.Utils.converter import ActionConverter
#from .topology_agent import TopologyGreedy, TopologyRandom
from grid2op.Agent import TopologyGreedy
from grid2op.Reward import L2RPNSandBoxScore
from grid2op.Exceptions import *

class DataGeneration:
    def __init__(self, config) -> None:
        self.env = grid2op.make(config.env_name, reward_class=L2RPNSandBoxScore,
                                backend=LightSimBackend())
        self.config = config
        self.action_converter = ActionConverter(self.env)
        self.agent = TopologyGreedy(self.env.action_space)
        #self.agent = TopologyRandom(self.env)

    def topology_data_generation(self):
        num_episodes = len(self.env.chronics_handler.subpaths)
        
        steps = []
        obs_data = []
        action_data = []
        obs_next_data = []
        reward_data = []
        done_data = []

        for episode_id in range(num_episodes):
            print(f"Episode ID : {episode_id}")
            self.env.set_id(episode_id)
            obs = self.env.reset()
            reward = self.env.reward_range[0]
            done = False
            

            for i in range (self.env.max_episode_duration()):
                
                action = self.agent.act(obs, reward, done) #self.agent.act() #
                obs_, reward, done, _ = self.env.step(self.env.action_space({}))
                action_idx = self.action_converter.action_idx(action)

                # Append data for this step
                obs_data.append(obs.to_vect())
                action_data.append(action_idx)
                obs_next_data.append(obs_.to_vect())
                reward_data.append(reward)
                done_data.append(done)
                steps.append(i)

                # Update observation for the next step
                obs = obs_

                

                if done:
                    self.env.set_id(episode_id)
                    
                    obs = self.env.reset()
                    done = False
                    reward = self.env.reward_range[0]

                    self.env.fast_forward_chronics(i - 1)
                    
                    action = self.agent.act(obs, reward, done)
                    obs_, reward, done, _ = self.env.step(self.env.action_space({}))
                    action_idx = self.action_converter.action_idx(action)

                    obs_data.append(obs.to_vect())
                    action_data.append(action_idx)
                    obs_next_data.append(obs_.to_vect())
                    reward_data.append(reward)
                    done_data.append(done)
                    steps.append(i)

                    obs = obs_
                

        # Convert lists to np.array
        obs_data = np.array(obs_data, dtype=object)
        action_data = np.array(action_data, dtype=int)
        obs_next_data = np.array(obs_next_data, dtype=object)
        reward_data = np.array(reward_data, dtype=float)
        done_data = np.array(done_data, dtype=bool)
        steps_data = np.array(steps, dtype=int)

        # Save to .npz file
        np.savez("data_generation_output.npz", obs=obs_data, action=action_data, 
                 obs_next=obs_next_data, reward=reward_data, done=done_data, steps=steps_data)
            

    

    def generate_random_data(self):
        obs_data = []
        action_data = []
        obs_next_data = []
        reward_data = []
        done_data = []

        for i in range(self.config.episode_num):
            done = False
            reward = self.env.reward_range[0]
            obs = self.env.reset()

            while not done:
                action = self.agent.act(obs, reward, done)
                obs_, reward, done, _ = self.env.step(action)

                action_idx = self.action_converter.action_idx(action)

                # Append data for this step
                obs_data.append(obs.to_vect())
                action_data.append(action_idx)
                obs_next_data.append(obs_.to_vect())
                reward_data.append(reward)
                done_data.append(done)

                if done:
                    print("break")
                    break
