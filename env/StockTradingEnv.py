import random
import json
import gym
from gym import spaces
import pandas as pd
import numpy as np
from render.StockTradingGraph import StockTradingGraph

INITIAL_ACCOUNT_BALANCE = 10000
LOOKBACK_WINDOW_SIZE = 40


class StockTradingEnv(gym.Env):
    """A stock trading environment for OpenAI gym"""
    metadata = {'render.modes': ['live', 'file', 'none']}
    visualization = None

    def __init__(self, config):
        self.df = config['df']
        self.render_title = config['render_title']
        self.lookback_window_size = LOOKBACK_WINDOW_SIZE
        self.initial_balance = INITIAL_ACCOUNT_BALANCE
        self.commission = 0.00075
        self.serial = False
        self.action_space = spaces.Box(
            low=np.array([0, 0]), high=np.array([3, 1]), dtype=np.float16)
        self.observation_space = spaces.Box(
            low=-np.finfo(np.float32).max, high=np.finfo(np.float32).max, shape=(18, ), dtype=np.float16)

    def _next_observation(self):
        frame = np.zeros(12)

        np.put(frame, [0,1,2,3,4,5,6,7,8.9,10,11], [
            self.df.loc[self.current_step: self.current_step + 1, 'open'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'high'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'low'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'close'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'volumefrom'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'MOM'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'RSI'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'HT_DCPERIOD'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'EMA'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'WILLR'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'BBANDS_upper'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'PPO'].values,
        ])

        obs = np.append(frame, [
            [self.balance],
            [self.btc_bought],
            [self.btc_sold],
            [self.cost],
            [self.sales],
            [self.net_worth]
        ])

        return obs

    def _take_action(self, action):
        current_price = random.uniform(
            self.df.loc[self.current_step, "open"], self.df.loc[self.current_step, "close"])

        action_type = action[0]
        amount = action[1]

        self.btc_bought = 0
        self.btc_sold = 0
        self.cost = 0
        self.sales = 0

        if action_type < 1:

            self.btc_bought = self.balance * amount / current_price
            self.cost = self.btc_bought * current_price * (1 + self.commission)
            self.shares_held += self.btc_bought
            self.balance -= self.cost

        elif action_type < 2:

            self.btc_sold = self.shares_held * amount
            self.sales = self.btc_sold * current_price * (1 - self.commission)
            self.shares_held -= self.btc_sold
            self.balance += self.sales

        if self.btc_sold > 0 or self.btc_bought > 0:
            self.trades.append({'step': self.current_step,
                                'amount': self.btc_sold if self.btc_sold > 0 else self.btc_bought, 'total': self.sales if self.btc_sold > 0 else self.cost,
                                'type': "sell" if self.btc_sold > 0 else "buy"})

        self.net_worth = self.balance + self.shares_held * current_price
        self.buy_and_hold = self.initial_bought * current_price

    def step(self, action):
        # Execute one time step within the environment
        self._take_action(action)
        self.current_step += 1

        net_worth_and_buyhold_mean = (self.net_worth + self.buy_and_hold) / 2
        reward = (self.net_worth - self.buy_and_hold) / net_worth_and_buyhold_mean
        # print('\nnet',self.net_worth,'buyandhold',self.buy_and_hold,'btc_bought',self.btc_bought,'balance',self.balance,'shares_held',self.shares_held,'balance on sold',self.balance,'reward', reward)
        done = self.net_worth <= 0 or self.balance <= 0 or self.current_step >= len(
            self.df.loc[:, 'open'].values)

        obs = self._next_observation()

        return obs, reward, done, {}

    def reset(self):
        # Reset the state of the environment to an initial state
        self.balance = INITIAL_ACCOUNT_BALANCE
        self.net_worth = INITIAL_ACCOUNT_BALANCE
        self.shares_held = 0
        self.btc_bought = 0
        self.btc_sold = 0
        self.cost = 0
        self.sales = 0
        self.current_step = 0
        self.first_price = self.df.loc[0, "close"]

        self.initial_bought = self.initial_balance / self.first_price
        self.trades = []

        return self._next_observation()

    def _render_to_file(self, filename='render.txt'):
        profit = self.net_worth - INITIAL_ACCOUNT_BALANCE

        file = open(filename, 'a+')

        file.write('Step: {}\n'.format(self.current_step))
        file.write('Balance: {}\n'.format(self.balance))
        file.write('Shares held: {}\n'.format(self.shares_held))
        file.write('Avg cost for held shares: {}\n'.format(self.cost))
        file.write('Net worth: {}\n'.format(self.net_worth))
        file.write('Buy and hold strategy: {}\n'.format(self.buy_and_hold))
        file.write('Profit: {}\n\n'.format(profit))

        file.close()

    def render(self, mode='live', **kwargs):
        # Render the environment to the screen
        if mode == 'file':
            self._render_to_file(kwargs.get('filename', 'render.txt'))

        elif mode == 'live':
            if self.visualization == None:
                self.visualization = StockTradingGraph(self.df, self.render_title)

            if self.current_step > LOOKBACK_WINDOW_SIZE:
                self.visualization.render(
                self.current_step, self.net_worth, self.buy_and_hold, self.trades, window_size=LOOKBACK_WINDOW_SIZE)

    def close(self):
        if self.visualization != None:
            self.visualization.close()
            self.visualization = None
