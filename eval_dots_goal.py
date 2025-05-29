import numpy as np
#from bs4 import BeautifulSoup as soup
import pandas as pd
#import statsmodels.formula.api as smf
#import statsmodels.api as sm
#import matplotlib.pyplot as plt
#import seaborn as sns
#from scipy.stats import poisson
#from itertools import permutations
from pulp import *

# These two inputs will need to be generated from the PBP to fully automate this...
# Manually input goal scorer
goal_scorer = '8482720'

# Manually input goal scoring team
goal_team = 'TOR'

r_dots = pd.read_json('2024020945_ev259.json', convert_dates=False)
timestamps = r_dots['timeStamp'].astype(str)

# Learn what this does!!
df_reset = r_dots['onIce'].apply(pd.Series)

# Bind timestamps here?
df_reset = pd.concat([timestamps, df_reset], axis=1)

df_final = df_reset.stack().reset_index(name='values')

df_final2 = df_final['values'].apply(pd.Series)

# Drop down the timestamp
w_dots = df_final2.copy()

# Rename the timestamp col by position since it's listed as '0'
w_dots.rename(columns={ w_dots.columns[0]: "timestamp" }, inplace = True)
w_dots['timestamp'] = w_dots['timestamp'].ffill()

# Remove any row without an x (this should likely just get rid of
# the extra timestamp row from the pivot)
w_dots = w_dots.dropna(subset=['x'])

# Force factor columns to strings
cols_converting = ['id', 'playerId', 'sweaterNumber', 'teamId', 'teamAbbrev']
w_dots[cols_converting] = w_dots[cols_converting].astype(str)

# Identify the timestamp where the puck crosses the goal line within the goal frame
# How correct is this? Hard to say...

# Goals are 11 feet from the end boards and 40 inches deep
# NHL rink is 200 feet X axis
# NHL rink is 85 feet Y axis
# In ID'ing where the goal is, Y won't change but X will

w_dots['puck_in_net'] = np.where((w_dots['id'] == '1.0') & (w_dots['x'] <= 132) & (w_dots['x'] >= 92) & (w_dots['y'] >= 474) & (w_dots['y'] <= 546) |
(w_dots['id'] == '1.0') & (w_dots['x'] >= 2268) & (w_dots['x'] <= 2308) & (w_dots['y'] >= 474) & (w_dots['y'] <= 546), 1, np.nan)

# ID the first instance of the puck in the net
# We'll work backwards from here to then find the moment where the
# puck started moving away from the goal scorer as a proxy
# for when the shot was taken

goal_timestamp = w_dots[w_dots['puck_in_net'] == 1.00].iloc[0]
goal_timestamp = goal_timestamp['timestamp']

w_dots['goal_timestamp'] = np.where(w_dots['timestamp'] == goal_timestamp, 1, np.nan)

# Filter the dots data set for the goal scorer and the puck only
w_scorer =\
    w_dots\
    .query("playerId == @goal_scorer | id == '1.0'")

# Move the puck x / y to the player line and calculate distance
# d=√((x2 – x1)² + (y2 – y1)²)

w_scorer['shifted_x'] = w_scorer['x'].shift(-1)
w_scorer['shifted_y'] = w_scorer['y'].shift(-1)

# Remove the puck
w_scorer =\
    w_scorer\
    .query("id != '1.0'")

# From the player POV only does this make sense
w_scorer['puck_distance'] = np.sqrt(((w_scorer['shifted_x'] - w_scorer['x'])**2) + ((w_scorer['shifted_y'] - w_scorer['y'])**2))

# ID the last time the puck only gets further from the skater before the goal timestamp
# This is what we think the moment of the 'shot' is

# Remove everything after the goal timestamp
w_scorer =\
    w_scorer\
    .query("timestamp < @goal_timestamp")

# Find rows where the puck is further from the player in the next timestamp
w_scorer['puck_further'] = np.where(w_scorer['puck_distance'] < w_scorer['puck_distance'].shift(1), "closer", "further")

# Based on that, potential timestamps for the shot are where the puck changes from closer to further
# This is an assumption we'll need to test
w_scorer['shot_proxy'] = np.where((w_scorer['puck_further'] == "closer") & (w_scorer['puck_further'].shift(-1) == "further"), 1, 0)

# Proxy the last time the puck moves from the player as the shot attempt timestmap
shot_timestamp = w_scorer[w_scorer['shot_proxy'] == 1].iloc[-1]
shot_timestamp = shot_timestamp['timestamp']

# Apply the shot_timestamp identifier to the full dots df
w_dots['shot_timestamp'] = np.where(w_dots['timestamp'] == shot_timestamp, 1, np.nan)

# Filter the data set for the goal scorer and the other team's skaters at the time of
# release as generated in the above DF

w_defender = w_dots.copy()

w_defender =\
    w_defender\
    .query('shot_timestamp == 1 & id != "1.0" & (playerId == @goal_scorer | teamAbbrev != @goal_team)')

# Hold goal scorer x y and then use it to compute distance of all the defenders
condition = w_defender['playerId'] == goal_scorer
scorer_x = w_defender.loc[condition, 'x'].values
scorer_y = w_defender.loc[condition, 'y'].values

# Calculate distance using these variables in w_defender
w_defender['distance_to_goal_scorer'] = np.sqrt(((scorer_x - w_defender['x'])**2) + ((scorer_y - w_defender['y'])**2))

# Remove the goal scorer and pull the minimum value in distance
# this is the defender who can be proxied as "accountable" for the goal

w_defender =\
    w_defender\
    .query('playerId != @goal_scorer')

closest_defender = w_defender[w_defender['distance_to_goal_scorer'] == w_defender['distance_to_goal_scorer'].min()]

w_defender = w_defender[['playerId', 'sweaterNumber', 'teamAbbrev', 'distance_to_goal_scorer']]






#test =\
#    w_dots\
#    .query('id == "1.0"')