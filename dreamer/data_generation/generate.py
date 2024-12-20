import os
import dill
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
from dreamer.data_generation.agents import RandomTopologyAgent
import time
import random
from grid2op.Exceptions import NoForecastAvailable
from collections import defaultdict
from dreamer.Utils.logger import logging
import warnings
import cloudpickle
warnings.filterwarnings('ignore')



class DataGeneration:
    def __init__(self, config) -> None:
        self.env = grid2op.make(config.env_name, reward_class=L2RPNSandBoxScore,
                                backend=LightSimBackend())
        self.config = config
        self.action_converter = ActionConverter(self.env)
        self.agent = TopologyGreedy(self.env.action_space)
        self.random_topology = RandomTopologyAgent(self.action_converter.actions)
        #self.agent = TopologyRandom(self.env)
        num = len(self.env.chronics_handler.subpaths)

    def topology_data_generation(self, start = 0, folder_name="dreamer\\data_generation\\topo_data", **args):
        if args.get('end') is None:
            num_episodes = len(self.env.chronics_handler.subpaths)
        else:
            num_episodes = args['end']
        
        steps = []
        obs_data = []
        action_data = []
        obs_next_data = []
        reward_data = []
        done_data = []
               

        for episode_id in range(start, num_episodes):

            print(f"Episode ID : {episode_id}")
            self.env.set_id(episode_id)
            obs = self.env.reset()
            reward = self.env.reward_range[0]
            done = False
            

            for i in range (self.env.max_episode_duration()):
                
                try:
                    action = self.agent.act(obs, reward, done) #self.agent.act() #
                    obs_, reward, done, _ = self.env.step(action)
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
                        obs_, reward, done, _ = self.env.step(action)
                        action_idx = self.action_converter.action_idx(action)

                        obs_data.append(obs.to_vect())
                        action_data.append(action_idx)
                        obs_next_data.append(obs_.to_vect())
                        reward_data.append(reward)
                        done_data.append(done)
                        steps.append(i)

                        obs = obs_
                
                except NoForecastAvailable as e:
                    print(f"Grid2OpException encountered at step {i} in episode {episode_id}: {e}")
                    self.env.set_id(episode_id)
                    obs = self.env.reset()
                    self.env.fast_forward_chronics(i-1)
                    continue

                except Grid2OpException as e:
                    print(f"Grid2OpException encountered at step {i} in episode {episode_id}: {e}")
                    self.env.set_id(episode_id)
                    obs = self.env.reset()
                    self.env.fast_forward_chronics(i-1)
                    continue  

                
            # Save data at the end of the episode
            self.save_data(obs_data, action_data, obs_next_data, reward_data, done_data, steps, episode_id, folder_name)

            # Reset data lists for the next episode
            obs_data, action_data, obs_next_data, reward_data, done_data, steps = [], [], [], [], [], []

            """# Convert lists to np.array
            obs_data = np.array(obs_data, dtype=object)
            action_data = np.array(action_data, dtype=int)
            obs_next_data = np.array(obs_next_data, dtype=object)
            reward_data = np.array(reward_data, dtype=float)
            done_data = np.array(done_data, dtype=bool)
            steps_data = np.array(steps, dtype=int)

            # Save to .npz file
            np.savez(f"dreamer\\data_generation\\data_generation_output_{episode_id}.npz", obs=obs_data, action=action_data, 
                    obs_next=obs_next_data, reward=reward_data, done=done_data, steps=steps_data)"""
            

    
    
    def random_topology_data_generation(self, start=0, folder_name = "dreamer\\data_generation\\data"):
        num_episodes = len(self.env.chronics_handler.subpaths)
        
        steps = []
        obs_data = []
        action_data = []
        obs_next_data = []
        reward_data = []
        done_data = []

        for episode_id in range(start, num_episodes+1):
            print(f"Episode ID : {episode_id}")
            self.env.set_id(episode_id)
            obs = self.env.reset()
            

            for i in range (self.env.max_episode_duration()):
                try:
                    action = self.random_topology.act() #self.agent.act() #
                    obs_, reward, done, _ = self.env.step(action)
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

                        self.env.fast_forward_chronics(i - 1)
                        
                        action = self.random_topology.act()
                        obs_, reward, done, _ = self.env.step(action)
                        action_idx = self.action_converter.action_idx(action)

                        obs_data.append(obs.to_vect())
                        action_data.append(action_idx)
                        obs_next_data.append(obs_.to_vect())
                        reward_data.append(reward)
                        done_data.append(done)
                        steps.append(i)

                        obs = obs_
                except Grid2OpException as e:
                    print(f"Grid2OpException encountered at step {i} in episode {episode_id}: {e}")
                    self.env.set_id(episode_id)
                    obs = self.env.reset()
                    self.env.fast_forward_chronics(i)
                    continue  


            # Save data at the end of the episode
            self.save_data(obs_data, action_data, obs_next_data, reward_data, done_data, steps, episode_id, folder_name)

            # Reset data lists for the next episode
            obs_data, action_data, obs_next_data, reward_data, done_data, steps = [], [], [], [], [], []


    
    def save_trajectories(self, data, folder_name, episode_id):
        """
        Save the trajectory data for a specific episode using dill.

        Args:
            data (dict): A dictionary containing trajectory data (obs_data, action_data, etc.).
            folder_name (str): Directory where the data will be saved.
            episode_id (int): Episode ID to differentiate saved files.
        """
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        file_path = os.path.join(folder_name, f"episode_{episode_id}.pkl")
        
        with open(file_path, 'wb') as f:
            dill.dump(data, f)
        
        print(f"Saved trajectories for episode {episode_id} at {file_path}")





    def load_trajectory(self, file_path):
        """
        Load a trajectory data file.

        Args:
            file_path (str): Path to the saved trajectory file.

        Returns:
            dict: Loaded trajectory data.
        """
        with open(file_path, 'rb') as f:
            return dill.load(f)



    
    def random_topology_data_generation_as_method(self, start=0, folder_name="dreamer\\data_generation\\data"):
        num_episodes = len(self.env.chronics_handler.subpaths)

        for episode_id in range(start, num_episodes+1):
            print(f"Episode ID : {episode_id}")
            self.env.set_id(episode_id)
            obs = self.env.reset()

            # Initialize trajectory storage for this episode
            steps = []
            obs_data = []
            action_data = []
            obs_next_data = []
            reward_data = []
            done_data = []

            for i in range(self.env.max_episode_duration()):
                try:
                    action = self.random_topology.act()  # self.agent.act() #
                    obs_, reward, done, _ = self.env.step(action)
                    action_idx = self.action_converter.action_idx(action)

                    # Append data for this step
                    obs_data.append(obs)
                    action_data.append(action_idx)
                    obs_next_data.append(obs_)
                    reward_data.append(reward)
                    done_data.append(done)
                    steps.append(i)

                    # Update observation for the next step
                    obs = obs_

                    if done:
                        self.env.set_id(episode_id)
                        obs = self.env.reset()
                        self.env.fast_forward_chronics(i - 1)
                        
                        action = self.random_topology.act()
                        obs_, reward, done, _ = self.env.step(action)
                        action_idx = self.action_converter.action_idx(action)

                        obs_data.append(obs)
                        action_data.append(action_idx)
                        obs_next_data.append(obs_)
                        reward_data.append(reward)
                        done_data.append(done)
                        steps.append(i)

                        obs = obs_
                except Grid2OpException as e:
                    print(f"Grid2OpException encountered at step {i} in episode {episode_id}: {e}")
                    self.env.set_id(episode_id)
                    obs = self.env.reset()
                    self.env.fast_forward_chronics(i)
                    continue

            # Save trajectory data for this episode
            trajectory_data = {
                "obs_data": obs_data,
                "action_data": action_data,
                "obs_next_data": obs_next_data,
                "reward_data": reward_data,
                "done_data": done_data,
                "steps": steps
            }
            
            self.save_trajectories(trajectory_data, folder_name, episode_id)
 



        


    def save_data(self, obs_data, action_data, obs_next_data, reward_data, done_data, steps, episode_id, folder_name = "dreamer\\data_generation\\data"):
        """
        Save the episode data to a file. File is named according to episode_id for easy tracking.
        """
        
        os.makedirs(folder_name, exist_ok=True)
        filename = f"{folder_name}\\episode_{episode_id}_data.npz"
        np.savez(
            filename,
            obs=np.array(obs_data, dtype=object),
            action=np.array(action_data, dtype=int),
            obs_next=np.array(obs_next_data, dtype=object),
            reward=np.array(reward_data, dtype=float),
            done=np.array(done_data, dtype=bool),
            steps=np.array(steps, dtype=int)
        )
        print(f"Data saved for episode {episode_id} in {filename}")


    def generate_random_data(self):
        obs_data = []
        action_data = []
        obs_next_data = []
        reward_data = []
        done_data = []

        for i in range(self.config.episode_num):
            print(i)
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
        # Convert lists to np.array
        obs_data = np.array(obs_data, dtype=object)
        action_data = np.array(action_data, dtype=int)
        obs_next_data = np.array(obs_next_data, dtype=object)
        reward_data = np.array(reward_data, dtype=float)
        done_data = np.array(done_data, dtype=bool)

        # Save to .npz file
        np.savez("dreamer\\data_generation\\random_data_generation_output.npz", obs=obs_data, action=action_data, 
                 obs_next=obs_next_data, reward=reward_data, done=done_data)
        


    def topology_search(self, dst_step):
        obs = self.env.get_obs()
        min_rho, overflow_id = obs.rho.max(), obs.rho.argmax()
        #print("step-%s, line-%s(from bus-%d to bus-%d) overflows, max rho is %.5f" %
            #(dst_step, overflow_id, self.env.line_or_to_subid[overflow_id],
            #self.env.line_ex_to_subid[overflow_id], obs.rho.max()))
        all_actions = self.env.action_space.get_all_unitary_topologies_set(self.env.action_space)
        action_chosen = self.env.action_space({})
        tick = time.time()
        for action in all_actions:
            if not self.env._game_rules(action, self.env):
                continue
            obs_, _, done, _ = obs.simulate(action)
            if (not done) and (obs_.rho.max() < min_rho):
                min_rho = obs_.rho.max()
                action_chosen = action
        logging.info("find a greedy action and max rho decreases to %.5f, search duration: %.2f" %
            (min_rho, time.time() - tick))
        return action_chosen
    


    def get_substation_connections(self):
        """
        Returns a dictionary with each substation ID and the number of powerlines connected to it.

        Parameters:
        - env: Grid2Op environment instance

        Returns:
        - substation_connections: Dictionary with substation ID as key and connection count as value
        """
        # Initialize a dictionary to store the number of connections for each substation
        substation_connections = defaultdict(int)

        # Retrieve powerline-to-substation mappings
        line_or_to_subid = self.env.line_or_to_subid  # Array of origin substations for each powerline
        line_ex_to_subid = self.env.line_ex_to_subid  # Array of extremity substations for each powerline

        # Count connections for each substation
        for line_id in range(self.env.n_line):
            origin_substation = line_or_to_subid[line_id]
            extremity_substation = line_ex_to_subid[line_id]
            
            # Increment the connection count for each substation
            substation_connections[origin_substation] += 1
            substation_connections[extremity_substation] += 1

        return substation_connections
    


    def find_most_connected_substations(self, substation_connections, top_n=5):
        """
        Finds the top N substations with the highest number of powerline connections.

        Parameters:
        - substation_connections: Dictionary with substation ID as key and connection count as value
        - top_n: Number of top substations to return

        Returns:
        - List of tuples (substation_id, connection_count) sorted by connection count in descending order
        """
        # Sort substations by the number of connections in descending order
        sorted_substations = sorted(substation_connections.items(), key=lambda x: x[1], reverse=True)
        
        return sorted_substations[:top_n]




    def find_powerlines_connected_to_substations(self, target_substations):
        """
        Finds all powerline IDs that are connected to the given substations.

        Parameters:
        - env: Grid2Op environment instance
        - target_substations: List of substation IDs to check for connections

        Returns:
        - connected_powerlines: Dictionary where each substation ID is a key and 
        the value is a list of powerline IDs connected to that substation
        """
        connected_powerlines = {sub: [] for sub in target_substations}

        # Retrieve powerline-to-substation mappings
        line_or_to_subid = self.env.line_or_to_subid  # Origin substation for each powerline
        line_ex_to_subid = self.env.line_ex_to_subid  # Extremity substation for each powerline

        # Loop through each powerline to find connections to target substations
        for line_id in range(self.env.n_line):
            origin_substation = line_or_to_subid[line_id]
            extremity_substation = line_ex_to_subid[line_id]

            # Check if origin or extremity matches any target substation
            if origin_substation in target_substations:
                connected_powerlines[origin_substation].append(line_id)
            if extremity_substation in target_substations:
                connected_powerlines[extremity_substation].append(line_id)

        return connected_powerlines


    def line2attack(self):
        substation_connections = self.get_substation_connections()
        top_substations = self.find_most_connected_substations(substation_connections, top_n=5)
        target_substations = [item[0] for item in top_substations]

        LINES2ATTACK = []
        # Find powerlines connected to the target substations
        result = self.find_powerlines_connected_to_substations(target_substations)

        # Print the result
        for substation, lines in result.items():
            for i in lines:
                LINES2ATTACK.append(i)
        
        return LINES2ATTACK

    def teacher_generation(self, line2attack, NUM_EPISODES=1000, folder_name="dreamer\\data_generation\\teacher_data"):
        DATA_PATH = self.env.get_path_env()  # for demo only, use your own dataset
        SCENARIO_PATH = self.env.chronics_handler.path

        # Ensure the folder exists
        os.makedirs(folder_name, exist_ok=True)

        for episode in range(NUM_EPISODES):
            # Loop through all lines to attack
            for line_to_disconnect in line2attack:
                obs_list = []
                reward_list = []
                next_obs_list = []
                done_list = []
                action_list = []
                steps_list = []

                try:
                    # Use LightSimBackend if available
                    from lightsim2grid import LightSimBackend
                    backend = LightSimBackend()
                    env = grid2op.make(dataset=DATA_PATH, chronics_path=SCENARIO_PATH, backend=backend)
                except ImportError:
                    env = grid2op.make(dataset=DATA_PATH, chronics_path=SCENARIO_PATH)
                
                # Shuffle chronics for diversity
                env.chronics_handler.shuffle(shuffler=lambda x: x[np.random.choice(len(x), size=len(x), replace=False)])
                
                # Loop through all scenarios
                for chronic in range(len(os.listdir(SCENARIO_PATH))):
                    try:
                        env.reset()
                        dst_step = episode * 72 + random.randint(0, 72)  # Random sampling every 6 hours
                        logging.info('\n\n' + '*' * 50 + f'\nScenario[{env.chronics_handler.get_name()}]: '
                            f'at step[{dst_step}], disconnect line-{line_to_disconnect} '
                            f'(from bus-{env.line_or_to_subid[line_to_disconnect]} '
                            f'to bus-{env.line_ex_to_subid[line_to_disconnect]})')

                        # Fast forward to the target time step
                        env.fast_forward_chronics(dst_step - 1)
                        obs, reward, done, _ = env.step(env.action_space({}))
                        if done:
                            break
                        
                        # Disconnect the targeted line
                        new_line_status_array = np.zeros(obs.rho.shape, dtype=np.int32)
                        new_line_status_array[line_to_disconnect] = -1
                        action = env.action_space({"set_line_status": new_line_status_array})
                        obs, reward, done, _ = env.step(action)

                        if obs.rho.max() < 1:
                            # Skip if no further action is needed
                            continue
                        else:
                            # Find a greedy action
                            action_ = self.topology_search(env)
                            obs_, reward, done, _ = env.step(action_)
                            action_idx = self.action_converter.action_idx(action_)

                            # Append data for this step
                            obs_list.append(obs.to_vect())
                            next_obs_list.append(obs_.to_vect())
                            reward_list.append(reward)
                            done_list.append(done)
                            action_list.append(action_idx)
                            steps_list.append(dst_step)

                    except Exception as e:
                        print(f"Error Occured \n {e}")
                        continue

                # Save data for this line attack and episode
                file_suffix = f"line_{line_to_disconnect}_episode_{episode}.npz"
                self.save_data(obs_list, action_list, next_obs_list, reward_list, done_list, steps_list, file_suffix, folder_name)
                logging.info(f"Data saved in {folder_name} at {file_suffix}")
        
        """# Convert lists to np.array
        obs_data = np.array(obs_list, dtype=object)
        action_data = np.array(action_list, dtype=int)
        obs_next_data = np.array(next_obs_list, dtype=object)
        reward_data = np.array(reward_list, dtype=float)
        done_data = np.array(done_list, dtype=bool)

        # Save to .npz file
        np.savez("dreamer\\data_generation\\teacher_generation_output.npz", obs=obs_data, action=action_data, 
                 obs_next=obs_next_data, reward=reward_data, done=done_data)"""
