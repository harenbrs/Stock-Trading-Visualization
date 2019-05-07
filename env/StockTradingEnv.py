import random
import json
import gym
from gym import spaces
import pandas as pd
import numpy as np

from render.StockTradingGraph import StockTradingGraph

MAX_ACCOUNT_BALANCE = 2147483647
MAX_NUM_SHARES = 2147483647
MAX_SHARE_PRICE = 5000
MAX_OPEN_POSITIONS = 5
MAX_STEPS = 20000

INITIAL_ACCOUNT_BALANCE = 10000

LOOKBACK_WINDOW_SIZE = 40


# def factor_pairs(val):
#     return [(i, val / i) for i in range(1, int(val**0.5)+1) if val % i == 0]


class StockTradingEnv(gym.Env):
    """A stock trading environment for OpenAI gym"""
    metadata = {'render.modes': ['live', 'file', 'none']}
    visualization = None

    def __init__(self, config):
        # super(StockTradingEnv, self).__init__()

        self.df = config['df']
        self.render_title = config['render_title']
        # self.reward_range = (0, MAX_ACCOUNT_BALANCE)
        self.lookback_window_size = 40
        self.initial_balance = INITIAL_ACCOUNT_BALANCE
        self.commission = 0.00075
        self.serial = False

        # Actions of the format Buy x%, Sell x%, Hold, etc.
        # self.action_space = spaces.MultiDiscrete([3, 10])

        self.action_space = spaces.Box(
            low=np.array([0, 0]), high=np.array([3, 1]), dtype=np.float16)

        # Prices contains the OHCL values for the last five prices
        self.observation_space = spaces.Box(
            low=-np.finfo(np.float32).max, high=np.finfo(np.float32).max, shape=(18, ), dtype=np.float16)

    # def _adjust_prices(self, df):
    #     # adjust_ratio = df['Adjusted_Close'] / df['Close']

    #     df['Open'] = df['Open'] * adjust_ratio
    #     df['High'] = df['High'] * adjust_ratio
    #     df['Low'] = df['Low'] * adjust_ratio
    #     df['Close'] = df['Close'] * adjust_ratio

    #     return df

    def _next_observation(self):
        frame = np.zeros(12)

        # Get the stock data points for the last 5 days and scale to between 0-1
        # CRITICAL POINT HERE
        # =================
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
        # print(obs)

        return obs

    def _take_action(self, action):
        current_price = random.uniform(
            self.df.loc[self.current_step, "open"], self.df.loc[self.current_step, "close"])

        action_type = action[0]
        amount = action[1]
        # print('amount', amount)

        self.btc_bought = 0
        self.btc_sold = 0
        self.cost = 0
        self.sales = 0

        if action_type < 1:

            self.btc_bought = self.balance * current_price * amount
            self.cost = self.btc_bought * current_price * (1 + self.commission)
            self.btc_held += self.btc_bought
            self.balance -= self.cost
            # print('btc_bought',self.btc_bought)
            # print('balance',self.balance)



        elif action_type < 2:

            self.btc_sold = self.btc_held * amount
            self.sales = self.btc_sold * current_price * (1 - self.commission)
            self.btc_held -= self.btc_sold
            self.balance += self.sales
            # print('btc_held',self.btc_held)
            # print('balance on sold',self.balance)

        if self.btc_sold > 0 or self.btc_bought > 0:
            self.trades.append({'step': self.current_step,
                                'amount': self.btc_sold if self.btc_sold > 0 else self.btc_bought, 'total': self.sales if self.btc_sold > 0 else self.cost,
                                'type': "sell" if self.btc_sold > 0 else "buy"})

        self.net_worth = self.balance + self.btc_held * current_price
        self.buy_and_hold = self.initial_bought * current_price

    def step(self, action):
        # Execute one time step within the environment
        self._take_action(action)

        self.current_step += 1

        # delay_modifier = (self.current_step / MAX_STEPS)

        # reward = self.balance * delay_modifier + self.current_step
        net_worth_and_buyhold_mean = (self.net_worth + self.buy_and_hold) / 2
        reward = (self.net_worth - self.buy_and_hold) / net_worth_and_buyhold_mean
        done = self.net_worth <= 0 or  self.balance <= 0 or self.current_step >= len(
            self.df.loc[:, 'open'].values)

        obs = self._next_observation()

        return obs, reward, done, {}

    def reset(self):
        # Reset the state of the environment to an initial state
        self.balance = INITIAL_ACCOUNT_BALANCE
        self.net_worth = INITIAL_ACCOUNT_BALANCE
        self.btc_held = 0
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
        # file.write('Shares held: {} (Total sold: {})\n'.format(self.shares_held, self.total_shares_sold))
        # file.write('Avg cost for held shares: {} (Total sales value: {})\n'.format(self.cost_basis, self.total_sales_value))
        # file.write('Net worth: {} (Max net worth: {})\n'.format(self.net_worth, self.max_net_worth))
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
