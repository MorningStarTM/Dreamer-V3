import os
import time
import random
import grid2op
import numpy as np
import pandas as pd
from dreamer.data_generation.generate import DataGeneration



class Teacher:
    def __init__(self, config) -> None:
        self.config = config
        self.dt = DataGeneration(self.config)
        self.env = self.dt.env

        self.DATA_PATH = self.env.get_path_env() #'C:\\Users\\Ernest\\data_grid2op\\l2rpn_wcci_2022'  # for demo only, use your own dataset
        self.SCENARIO_PATH = self.env.chronics_handler.path #'C:\\Users\\Ernest\\data_grid2op\\l2rpn_wcci_2022'
        self.SAVE_PATH = 'dreamer\\asr'


        substation_connections = self.dt.get_substation_connections(self.env)
        top_substations = self.dt.find_most_connected_substations(substation_connections, top_n=12)
        target_substations = [item[0] for item in top_substations]
        self.LINES2ATTACK = [] #[0, 1, 5, 7, 9, 16, 17, 4, 9, 13, 14, 18]

        result = self.dt.find_powerlines_connected_to_substations(target_substations)

        # Print the result
        for substation, lines in result.items():
            for i in lines:
                self.LINES2ATTACK.append(i)

        self.NUM_EPISODES = 1  # each scenario runs 100 times for each attack (or to say, sample 100 points)


    def topology_search(self, dst_step):
        obs = self.env.get_obs()
        min_rho, overflow_id = obs.rho.max(), obs.rho.argmax()
        print("step-%s, line-%s(from bus-%d to bus-%d) overflows, max rho is %.5f" %
            (dst_step, overflow_id, self.env.line_or_to_subid[overflow_id],
            self.env.line_ex_to_subid[overflow_id], obs.rho.max()))
        all_actions = self.env.action_space.get_all_unitary_topologies_change(self.env.action_space)
        action_chosen = self.env.action_space({})
        tick = time.time()
        for action in all_actions:
            if not self.env._game_rules(action, self.env):
                continue
            obs_, _, done, _ = obs.simulate(action)
            if (not done) and (obs_.rho.max() < min_rho):
                min_rho = obs_.rho.max()
                action_chosen = action
        print("find a greedy action and max rho decreases to %.5f, search duration: %.2f" %
            (min_rho, time.time() - tick))
        return action_chosen



    def save_sample(self, obs, action, obs_, dst_step, line_to_disconnect, save_path):
        if action == self.env.action_space({}):
            return None  # not necessary to save a "do nothing" action
        act_or, act_ex, act_gen, act_load = [], [], [], []
        for key, val in action.as_dict()['change_bus_vect'][
            action.as_dict()['change_bus_vect']['modif_subs_id'][0]].items():
            if val['type'] == 'line (extremity)':
                act_ex.append(key)
            elif val['type'] == 'line (origin)':
                act_or.append(key)
            elif val['type'] == 'load':
                act_load.append(key)
            else:
                act_gen.append(key)
        pd.concat(
            (
                pd.DataFrame(
                    np.array(
                        [self.env.chronics_handler.get_name(), dst_step, line_to_disconnect,
                        self.env.line_or_to_subid[line_to_disconnect],
                        self.env.line_ex_to_subid[line_to_disconnect], str(np.where(obs.rho > 1)[0].tolist()),
                        str([i for i in np.around(obs.rho[np.where(obs.rho > 1)], 2)]),
                        action.as_dict()['change_bus_vect']['modif_subs_id'][0], act_or, act_ex, act_gen, act_load,
                        obs.rho.max(), obs.rho.argmax(), obs_.rho.max(), obs_.rho.argmax()]).reshape([1, -1])),
                pd.DataFrame(np.concatenate((obs.to_vect(), obs_.to_vect(), action.to_vect())).reshape([1, -1]))
            ),
            axis=1
        ).to_csv(os.path.join(save_path, 'Experiences1.csv'), index=0, header=0, mode='a')



    def generate(self):
        for episode in range(self.NUM_EPISODES):
            # traverse all attacks
            for line_to_disconnect in self.LINES2ATTACK:
                try:
                    # if lightsim2grid is available, use it.
                    from lightsim2grid import LightSimBackend
                    backend = LightSimBackend()
                    env = grid2op.make(dataset=self.DATA_PATH, chronics_path=self.SCENARIO_PATH, backend=backend)
                except:
                    env = grid2op.make(dataset=self.DATA_PATH, chronics_path=self.SCENARIO_PATH)
                env.chronics_handler.shuffle(shuffler=lambda x: x[np.random.choice(len(x), size=len(x), replace=False)])
                # traverse all scenarios
                for chronic in range(len(os.listdir(self.SCENARIO_PATH))):
                    env.reset()
                    dst_step = episode * 72 + random.randint(0, 72)  # a random sampling every 6 hours
                    print('\n\n' + '*' * 50 + '\nScenario[%s]: at step[%d], disconnect line-%d(from bus-%d to bus-%d]' % (
                        env.chronics_handler.get_name(), dst_step, line_to_disconnect,
                        env.line_or_to_subid[line_to_disconnect], env.line_ex_to_subid[line_to_disconnect]))
                    # to the destination time-step
                    env.fast_forward_chronics(dst_step - 1)
                    obs, reward, done, _ = env.step(env.action_space({}))
                    if done:
                        break
                    # disconnect the targeted line
                    new_line_status_array = np.zeros(obs.rho.shape, dtype=np.int32)
                    new_line_status_array[line_to_disconnect] = -1
                    action = env.action_space({"set_line_status": new_line_status_array})
                    obs, reward, done, _ = env.step(action)
                    if obs.rho.max() < 1:
                        # not necessary to do a dispatch
                        continue
                    else:
                        # search a greedy action
                        action = self.topology_search(env)
                        obs_, reward, done, _ = env.step(action)
                        self.save_sample(obs, action, obs_, dst_step, line_to_disconnect, self.SAVE_PATH)