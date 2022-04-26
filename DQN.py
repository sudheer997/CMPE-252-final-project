import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from gym import wrappers

from tensorflow.python.keras import Sequential
from tensorflow.python.keras.layers import Dense
from tensorflow.keras.optimizers import Adam

from replay_buffer import ReplayBuffer


def CreateDeepQNetwork(lr, num_actions, input_dims, fc1, fc2):
    q_net = Sequential()
    q_net.add(Dense(fc1, input_dim=input_dims, activation='relu'))
    q_net.add(Dense(fc2, activation='relu'))
    q_net.add(Dense(num_actions, activation=None))
    q_net.compile(optimizer=Adam(learning_rate=lr), loss='mse')

    return q_net


class Agent:
    def __init__(self, lr, discount_factor, num_actions, epsilon, batch_size, input_dims, update_rate,
                 epsilon_decay, epsilon_final):
        self.action_space = [i for i in range(num_actions)]
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay if epsilon_decay else 0.001
        self.epsilon_final = epsilon_final if epsilon_final else 0.01
        self.update_rate = update_rate if update_rate else 120
        self.step_counter = 0
        self.buffer = ReplayBuffer(1000000, input_dims)
        self.batch_size = batch_size
        self.q_net = CreateDeepQNetwork(lr, num_actions, input_dims, 128, 128)
        self.q_target_net = CreateDeepQNetwork(lr, num_actions, input_dims, 128, 128)

    def policy(self, current_state):
        # Return the action using epsilon greedy policy
        if np.random.random() < self.epsilon:
            action = np.random.choice(self.action_space)
        else:
            # Get the max action for the current state using DQN network
            state = np.array([current_state])
            actions = self.q_net(state)
            action = tf.math.argmax(actions, axis=1).numpy()[0]
        return action

    def train(self):
        # copy the main network to target network after every update rate number of iterations
        if self.step_counter % self.update_rate == 0:
            self.q_target_net.set_weights(self.q_net.get_weights())

        # Get the sample batch from the replay buffer for training the model.
        state_batch, action_batch, reward_batch, new_state_batch, done_batch = \
            self.buffer.sample_buffer(self.batch_size)

        q_predicted = self.q_net(state_batch)
        q_next = self.q_target_net(new_state_batch)
        q_max_next = tf.math.reduce_max(q_next, axis=1, keepdims=True).numpy()
        q_target = np.copy(q_predicted)

        for idx in range(done_batch.shape[0]):
            target_q_val = reward_batch[idx]
            if not done_batch[idx]:
                # Bellman equation
                target_q_val += self.discount_factor*q_max_next[idx]
            q_target[idx, action_batch[idx]] = target_q_val
        loss = self.q_net.train_on_batch(state_batch, q_target)
        self.step_counter += 1

    def train_model(self, env, num_episodes, graph):

        scores, episodes, avg_scores, obj = [], [], [], []
        goal = 200
        min_episodes_criterion = 100
        count = 0
        f = 0
        txt = open("saved_networks.txt", "w")

        for i in range(num_episodes):
            done = False
            score = 0.0
            state = env.reset()
            while not done:
                action = self.policy(state)
                new_state, reward, done, _ = env.step(action)
                score += reward
                self.buffer.store_tuples(state, action, reward, new_state, done)
                state = new_state
                if not (self.buffer.counter < self.batch_size):
                    self.train()
                    # After every batch of training update the epsilon value
                    self.epsilon = self.epsilon - self.epsilon_decay if self.epsilon > self.epsilon_final else \
                        self.epsilon_final
            scores.append(score)
            obj.append(goal)
            episodes.append(i)
            avg_score = np.mean(scores[-100:])
            avg_scores.append(avg_score)
            print("Episode {0}/{1}, Score: {2}, AVG Score: {3}".format(i, num_episodes, score,
                                                                             avg_score))
            if avg_score >= 200:
                count += 1
            else:
                count = 0
            if count > min_episodes_criterion:
                self.q_net.save(("saved_networks/dqn_model{0}".format(f)))
                self.q_net.save_weights(("saved_networks/dqn_model{0}/net_weights{0}.h5".format(f)))
                txt.write(
                    "Save {0} - Episode {1}/{2}, Score: {3} , AVG Score: {4}\n".format(f, i, num_episodes,
                                                                                            score, avg_score))
                f += 1
                print("Network saved")
                break
        txt.close()
        return episodes, scores, avg_scores, obj

    def test(self, env, num_episodes, file_type, file, graph):
        if file_type == 'tf':
            self.q_net = tf.keras.models.load_model(file)
        elif file_type == 'h5':
            self.train_model(env, 5, False)
            self.q_net.load_weights(file)
        self.epsilon = 0.0
        scores, episodes, avg_scores, obj = [], [], [], []
        goal = 200
        score = 0.0
        # env = wrappers.Monitor(env, "./dqn_results", force=True)
        for i in range(num_episodes):
            state = env.reset()
            done = False
            episode_score = 0.0
            while not done:
                env.render()
                action = self.policy(state)
                new_state, reward, done, _ = env.step(action)
                episode_score += reward
                state = new_state
            score += episode_score
            scores.append(episode_score)
            obj.append(goal)
            episodes.append(i)
            avg_score = np.mean(scores[-100:])
            avg_scores.append(avg_score)

        if graph:
            df = pd.DataFrame({'x': episodes, 'Score': scores, 'Average Score': avg_scores, 'Solved Requirement': obj})

            plt.plot('x', 'Score', data=df, marker='', color='blue', linewidth=2, label='Score')
            plt.plot('x', 'Average Score', data=df, marker='', color='orange', linewidth=2, linestyle='dashed',
                     label='AverageScore')
            plt.plot('x', 'Solved Requirement', data=df, marker='', color='red', linewidth=2, linestyle='dashed',
                     label='Solved Requirement')
            plt.legend()
            plt.savefig('LunarLander_Test.png')

        env.close()
