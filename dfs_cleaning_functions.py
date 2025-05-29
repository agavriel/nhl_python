# Can we function all the data cleaning for the DFS model? I don't want to run 400 lines of code every day
import random
import numpy as np
import requests
from bs4 import BeautifulSoup as soup
import re
import pandas as pd
import time
import statsmodels.formula.api as smf
import statsmodels.api as sm
import matplotlib.pyplot as plt
#import seaborn as sns
from scipy.stats import poisson
import joblib
from itertools import permutations
from pulp import *
from nhl_scraper_functions import scrape_schedule_vegas
from nhl_scraper_functions import scrape_schedule

# Read the files in outside of the function?
# Play by play
r_pbp = pd.read_csv('2425_pbp.csv')

# Player TOI
r_p_toi = pd.read_csv('2425_p_toi.csv')

# Team TOI
r_t_toi = pd.read_csv('2425_teams.csv')

# Player IDs from the API scrapes
d_players = pd.read_csv('2425_d_players.csv')

# Goalie TOI
r_goalies = pd.read_csv('2425_goalies.csv')

# DK Slate file
r_dk = pd.read_csv('dk_salary_tracker.csv')

# Add the player primary key column for merges
r_dk['player_primary'] = r_dk['Name'] + '_' + r_dk['TeamAbbrev']

# Player lookup file
d_playerLookup = pd.read_csv('d_dktonhl_players.csv')

#slate_date = "1/1/2025"
#slate_day = "2025-01-01"

def clean_skater_model(slate_date, slate_day):

    # Filter the dk file to the day of games
    str_slate_date = str(slate_date)
    str_slate_day = str(slate_day)

    w_dk =\
        r_dk\
        .query("Slate == @str_slate_date")
    
    # Use the DK file to get (next) opponent for each team
    w_dk_opponents = w_dk.game_info.str.extract(r'(?P<away>[A-Z]{3})@(?P<home>[A-Z]{3}).*')

    w_dk =\
        pd.concat([w_dk, w_dk_opponents], axis = 1)
    
    # ID Opponent from home/away cols
    w_dk["p_opp_next"] = np.where(w_dk["TeamAbbrev"] == w_dk["home"], w_dk["away"], w_dk["home"])
    w_dk["p_venue_next"] = np.where(w_dk["TeamAbbrev"] == w_dk["home"], "home", "away")
 
    # Merge in NHL player ID
    w_dk =\
        w_dk\
        .merge(
            right = d_playerLookup,
            how = "left",
            left_on = ['player_primary'],
            right_on = ['player_primary']
        )
    
    # As debugging, print the players who have recorded any DFS points this year but have no matching ID
    print(
        w_dk\
            .query('nhl_playerId.isnull() & AvgPointsPerGame > 0')
    )
    
    # Pausing 4 seconds to break the function if anyone appears in the above QA
    print("Pausing four seconds to allow a computation interruption to update the lookup table")
    #time.sleep(4)

    # Modeling thoughts (what we need to build)

    # For DFS, I need to predict: Goals, Assists, Shots on Goal, Blocked Shots
    # Poisson 5 or mor shots, 3 or more goals, 3 or more points, 3 or more blocked shots (for bonus)

    # Distributing by strength is not important but factoring it in is (PP time for points, SH time for blocks)

    # Goalies:
    # Model win probability, total saves, total goals against, and poisson for 35+ saves    
    # Make a d_games df from the PBP to hold season, gcode, home, and away teams
    d_games = r_pbp[['season', 'game_id', 'game_date', 'home_team', 'away_team']]

    # Keep unique rows
    d_games = d_games.drop_duplicates()

    # Create a merge table for player IDs
    m_players = d_players[['season', 'game_id', 'ev_player_1', 'team_abbrev', 'positionCode', 'playerId']]

    # Conditions and choices for team to abbreviation, not sure why I missed that in the scraper function
    conditions = [r_p_toi.team == "ANAHEIM DUCKS",
            r_p_toi.team == "ARIZONA COYOTES",
            r_p_toi.team == "BOSTON BRUINS",
            r_p_toi.team == "BUFFALO SABRES",
            r_p_toi.team == "CALGARY FLAMES",
            r_p_toi.team == "CAROLINA HURRICANES",
            r_p_toi.team == "CHICAGO BLACKHAWKS",
            r_p_toi.team == "COLORADO AVALANCHE",
            r_p_toi.team == "COLUMBUS BLUE JACKETS",
            r_p_toi.team == "DALLAS STARS",
            r_p_toi.team == "DETROIT RED WINGS",
            r_p_toi.team == "EDMONTON OILERS",
            r_p_toi.team == "FLORIDA PANTHERS",
            r_p_toi.team == "LOS ANGELES KINGS",
            r_p_toi.team == "MONTRÉAL CANADIENS",
            r_p_toi.team == "MONTREAL CANADIENS",
            r_p_toi.team == "MINNESOTA WILD",
            r_p_toi.team == "NASHVILLE PREDATORS",
            r_p_toi.team == "NEW JERSEY DEVILS",
            r_p_toi.team == "NEW YORK ISLANDERS",
            r_p_toi.team == "NEW YORK RANGERS",
            r_p_toi.team == "OTTAWA SENATORS",
            r_p_toi.team == "PHILADELPHIA FLYERS",
            r_p_toi.team == "PITTSBURGH PENGUINS",
            r_p_toi.team == "SAN JOSE SHARKS",
            r_p_toi.team == "SEATTLE KRAKEN",
            r_p_toi.team == "ST. LOUIS BLUES",
            r_p_toi.team == "TAMPA BAY LIGHTNING",
            r_p_toi.team == "TORONTO MAPLE LEAFS",
            r_p_toi.team == "VANCOUVER CANUCKS",
            r_p_toi.team == "VEGAS GOLDEN KNIGHTS",
            r_p_toi.team == "WASHINGTON CAPITALS",
            r_p_toi.team == "WINNIPEG JETS",
            r_p_toi.team == "UTAH HOCKEY CLUB"]
    choices = ["ANA", "ARI", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET", "EDM", "FLA", "LAK", "MTL", "MTL", "MIN", "NSH", "NJD", 
        "NYI", "NYR", "OTT", "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "VAN", "VGK", "WSH", "WPG", "UTA"]

    r_p_toi["Abbrev"] = np.select(conditions, choices, default = r_p_toi.team)

    ############ TEAMS ############

    print("""
    
    
    Starting Team fact table building
    
    
    
    """)

    # And again for team toi?
    # Conditions and choices for team to abbreviation, not sure why I missed that in the scraper function
    conditions = [r_t_toi.team_name == "ANAHEIM DUCKS",
            r_t_toi.team_name == "ARIZONA COYOTES",
            r_t_toi.team_name == "BOSTON BRUINS",
            r_t_toi.team_name == "BUFFALO SABRES",
            r_t_toi.team_name == "CALGARY FLAMES",
            r_t_toi.team_name == "CAROLINA HURRICANES",
            r_t_toi.team_name == "CHICAGO BLACKHAWKS",
            r_t_toi.team_name == "COLORADO AVALANCHE",
            r_t_toi.team_name == "COLUMBUS BLUE JACKETS",
            r_t_toi.team_name == "DALLAS STARS",
            r_t_toi.team_name == "DETROIT RED WINGS",
            r_t_toi.team_name == "EDMONTON OILERS",
            r_t_toi.team_name == "FLORIDA PANTHERS",
            r_t_toi.team_name == "LOS ANGELES KINGS",
            r_t_toi.team_name == "MONTRÉAL CANADIENS",
            r_t_toi.team_name == "MONTREAL CANADIENS",
            r_t_toi.team_name == "MINNESOTA WILD",
            r_t_toi.team_name == "NASHVILLE PREDATORS",
            r_t_toi.team_name == "NEW JERSEY DEVILS",
            r_t_toi.team_name == "NEW YORK ISLANDERS",
            r_t_toi.team_name == "NEW YORK RANGERS",
            r_t_toi.team_name == "OTTAWA SENATORS",
            r_t_toi.team_name == "PHILADELPHIA FLYERS",
            r_t_toi.team_name == "PITTSBURGH PENGUINS",
            r_t_toi.team_name == "SAN JOSE SHARKS",
            r_t_toi.team_name == "SEATTLE KRAKEN",
            r_t_toi.team_name == "ST. LOUIS BLUES",
            r_t_toi.team_name == "TAMPA BAY LIGHTNING",
            r_t_toi.team_name == "TORONTO MAPLE LEAFS",
            r_t_toi.team_name == "VANCOUVER CANUCKS",
            r_t_toi.team_name == "VEGAS GOLDEN KNIGHTS",
            r_t_toi.team_name == "WASHINGTON CAPITALS",
            r_t_toi.team_name == "WINNIPEG JETS",
            r_t_toi.team_name == "UTAH HOCKEY CLUB"]
    choices = ["ANA", "ARI", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET", "EDM", "FLA", "LAK", "MTL", "MTL", "MIN", "NSH", "NJD", 
        "NYI", "NYR", "OTT", "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "VAN", "VGK", "WSH", "WPG", "UTA"]

    r_t_toi["Abbrev"] = np.select(conditions, choices, default = r_t_toi.team_name)

    # Having the opponent as an all encompassing factor is lazy bc it's locked in on the input data, duh

    # Need CA60, GA60, CF60 and GF60
        
    # Corsis and GFs for
    w_f_team =\
        r_pbp\
        .query("is_corsi > 0")\
        .groupby(["season", "game_id", "ev_team", "strength_cat"])\
        .agg({"is_corsi": ["sum"],
            "is_goal":["sum"]})

    w_f_team.columns =\
        list(map("_".join, w_f_team.columns))

    w_f_team.reset_index(inplace=True)

    w_f_team.rename(columns={'is_corsi_sum':'CF', 'is_goal_sum':'GF'}, inplace=True)

    # Corsis and GAs against

    # Create a pbp copy and add an opponent column. Agg off this then delete
    c_pbp = r_pbp.copy()

    c_pbp['against_team'] = np.where(c_pbp['ev_team'] == c_pbp['away_team'], c_pbp['home_team'], c_pbp['away_team'])

    w_a_team =\
        c_pbp\
        .query("is_corsi > 0")\
        .groupby(["season", "game_id", "against_team", "strength_cat"])\
        .agg({"is_corsi": ["sum"],
            "is_goal":["sum"]})

    w_a_team.columns =\
        list(map("_".join, w_a_team.columns))

    w_a_team.reset_index(inplace=True)

    w_a_team.rename(columns={'is_corsi_sum':'CA', 'is_goal_sum':'GA', 'against_team': 'ev_team'}, inplace=True)

    del c_pbp

    # pivot wider so we can merge to the toi table

    # for
    w_f_team = w_f_team.pivot(index =['season', 'game_id', 'ev_team'], columns='strength_cat', values = ['CF', 'GF'])

    w_f_team.columns =\
        list(map("_".join, w_f_team.columns))

    w_f_team.reset_index(inplace=True)

    # against
    # for
    w_a_team = w_a_team.pivot(index =['season', 'game_id', 'ev_team'], columns='strength_cat', values = ['CA', 'GA'])

    w_a_team.columns =\
        list(map("_".join, w_a_team.columns))

    w_a_team.reset_index(inplace=True)

    # Merge to the TOI table and delete working tables
    w_teams =\
        r_t_toi\
        .merge(
            right = w_f_team,
            how = "left",
            left_on = ['Abbrev', 'season', 'gcode'],
            right_on = ['ev_team', 'season', 'game_id']
        )\
        .drop(columns=['game_id', 'ev_team'])

    # Repeat against
    w_teams =\
        w_teams\
        .merge(
            right = w_a_team,
            how = "left",
            left_on = ['Abbrev', 'season', 'gcode'],
            right_on = ['ev_team', 'season', 'game_id']
        )\
        .drop(columns=['game_id', 'ev_team'])

    # Use d_games to get the venue flag and game date in
    w_teams =\
        w_teams\
        .merge(
            right = d_games,
            how = "left",
            left_on = ['season', 'gcode'],
            right_on = ['season', 'game_id']
        )\
        .drop(columns=['game_id'])

    w_teams['venue'] = np.where(w_teams['Abbrev'] == w_teams['home_team'], "home", "away")
    w_teams['opponent'] = np.where(w_teams['Abbrev'] == w_teams['home_team'], w_teams['away_team'], w_teams['home_team'])

    # Replace NaN with 0 so we can do math
    w_teams.fillna(0, inplace=True)

    # Calculate all situations CF, GF, CA, GA
    w_teams['CF_all'] = w_teams['CF_EV'] + w_teams['CF_junk'] + w_teams['CF_PP'] + w_teams['CF_SH']
    w_teams['CA_all'] = w_teams['CA_EV'] + w_teams['CA_junk'] + w_teams['CA_PP'] + w_teams['CA_SH']
    w_teams['GF_all'] = w_teams['GF_EV'] + w_teams['GF_junk'] + w_teams['GF_PP'] + w_teams['GF_SH']
    w_teams['GA_all'] = w_teams['GA_EV'] + w_teams['GA_junk'] + w_teams['GA_PP'] + w_teams['GA_SH']

    # Start the rolls? Let's just do EV and All YTD and YTD at venue, no five

    # Date to date
    w_teams['game_date'] = pd.to_datetime(w_teams['game_date'])

    # Arrange
    w_teams = w_teams.sort_values(by=["Abbrev", "game_date"])

    # Where is the next game's venue and gcode?
    w_teams['t_venue_next'] = w_teams.groupby(['Abbrev', 'season'])['venue'].shift(-1)
    w_teams['t_gcode_next'] = w_teams.groupby(['Abbrev', 'season'])['gcode'].shift(-1)
    w_teams['t_opp_next'] = w_teams.groupby(['Abbrev', 'season'])['opponent'].shift(-1)

    # Team toi
    w_teams['t_ytd_game_num'] = w_teams.groupby(['Abbrev', 'season']).cumcount()+1
    w_teams['t_ytd_ev_toi'] = w_teams.groupby(['Abbrev', 'season'])['ev_toi'].cumsum()
    w_teams['t_ytd_all_toi'] = w_teams.groupby(['Abbrev', 'season'])['tot_toi'].cumsum()

    # Corsis and Goals
    w_teams['t_ytd_cf_ev'] = w_teams.groupby(['Abbrev', 'season'])['CF_EV'].cumsum()
    w_teams['t_ytd_cf_all'] = w_teams.groupby(['Abbrev', 'season'])['CF_all'].cumsum()
    w_teams['t_ytd_ca_ev'] = w_teams.groupby(['Abbrev', 'season'])['CA_EV'].cumsum()
    w_teams['t_ytd_ca_all'] = w_teams.groupby(['Abbrev', 'season'])['CA_all'].cumsum()

    w_teams['t_ytd_gf_ev'] = w_teams.groupby(['Abbrev', 'season'])['GF_EV'].cumsum()
    w_teams['t_ytd_gf_all'] = w_teams.groupby(['Abbrev', 'season'])['GF_all'].cumsum()
    w_teams['t_ytd_ga_ev'] = w_teams.groupby(['Abbrev', 'season'])['GA_EV'].cumsum()
    w_teams['t_ytd_ga_all'] = w_teams.groupby(['Abbrev', 'season'])['GA_all'].cumsum()

    # All situations corsi sv% for the game model
    w_teams['t_ytd_csvp_all'] = 1 - (w_teams['t_ytd_ga_all'] / w_teams['t_ytd_ca_all'])

    # Venue
    #w_teams['t_ytd_v_game_num'] = w_teams.groupby(['Abbrev', 'season', 'venue']).cumcount()+1
    #w_teams['t_ytd_v_ev_toi'] = w_teams.groupby(['Abbrev', 'season', 'venue'])['ev_toi'].cumsum()
    #w_teams['t_ytd_v_all_toi'] = w_teams.groupby(['Abbrev', 'season', 'venue'])['tot_toi'].cumsum()

    # Corsis and Goals
    #w_teams['t_ytd_v_cf_ev'] = w_teams.groupby(['Abbrev', 'season', 'venue'])['CF_EV'].cumsum()
    #w_teams['t_ytd_v_cf_all'] = w_teams.groupby(['Abbrev', 'season', 'venue'])['CF_all'].cumsum()
    #w_teams['t_ytd_v_ca_ev'] = w_teams.groupby(['Abbrev', 'season', 'venue'])['CA_EV'].cumsum()
    #w_teams['t_ytd_v_ca_all'] = w_teams.groupby(['Abbrev', 'season', 'venue'])['CA_all'].cumsum()

    #w_teams['t_ytd_v_gf_ev'] = w_teams.groupby(['Abbrev', 'season', 'venue'])['GF_EV'].cumsum()
    #w_teams['t_ytd_v_gf_all'] = w_teams.groupby(['Abbrev', 'season', 'venue'])['GF_all'].cumsum()
    #w_teams['t_ytd_v_ga_ev'] = w_teams.groupby(['Abbrev', 'season', 'venue'])['GA_EV'].cumsum()
    #w_teams['t_ytd_v_ga_all'] = w_teams.groupby(['Abbrev', 'season', 'venue'])['GA_all'].cumsum()

    # Per 60
    w_teams['t_ytd_cf60_ev'] = (w_teams['t_ytd_cf_ev'] * 3600) / w_teams['t_ytd_ev_toi']
    w_teams['t_ytd_ca60_ev'] = (w_teams['t_ytd_ca_ev'] * 3600) / w_teams['t_ytd_ev_toi']
    w_teams['t_ytd_cf60_all'] = (w_teams['t_ytd_cf_all'] * 3600) / w_teams['t_ytd_all_toi']
    w_teams['t_ytd_ca60_all'] = (w_teams['t_ytd_ca_all'] * 3600) / w_teams['t_ytd_all_toi']

    w_teams['t_ytd_gf60_ev'] = (w_teams['t_ytd_gf_ev'] * 3600) / w_teams['t_ytd_ev_toi']
    w_teams['t_ytd_ga60_ev'] = (w_teams['t_ytd_ga_ev'] * 3600) / w_teams['t_ytd_ev_toi']
    w_teams['t_ytd_gf60_all'] = (w_teams['t_ytd_gf_all'] * 3600) / w_teams['t_ytd_all_toi']
    w_teams['t_ytd_ga60_all'] = (w_teams['t_ytd_ga_all'] * 3600) / w_teams['t_ytd_all_toi']

    #w_teams['t_ytd_v_cf60_ev'] = (w_teams['t_ytd_v_cf_ev'] * 3600) / w_teams['t_ytd_v_ev_toi']
    #w_teams['t_ytd_v_ca60_ev'] = (w_teams['t_ytd_v_ca_ev'] * 3600) / w_teams['t_ytd_v_ev_toi']
    #w_teams['t_ytd_v_cf60_all'] = (w_teams['t_ytd_v_cf_all'] * 3600) / w_teams['t_ytd_v_all_toi']
    #w_teams['t_ytd_v_ca60_all'] = (w_teams['t_ytd_v_ca_all'] * 3600) / w_teams['t_ytd_v_all_toi']

    #w_teams['t_ytd_v_gf60_ev'] = (w_teams['t_ytd_v_gf_ev'] * 3600) / w_teams['t_ytd_v_ev_toi']
    #w_teams['t_ytd_v_ga60_ev'] = (w_teams['t_ytd_v_ga_ev'] * 3600) / w_teams['t_ytd_v_ev_toi']
    #w_teams['t_ytd_v_gf60_all'] = (w_teams['t_ytd_v_gf_all'] * 3600) / w_teams['t_ytd_v_all_toi']
    #w_teams['t_ytd_v_ga60_all'] = (w_teams['t_ytd_v_ga_all'] * 3600) / w_teams['t_ytd_v_all_toi']

    # Keep what we want and close the fact table?
    f_teams = w_teams.copy()
    f_teams = f_teams[['team_name', 'Abbrev', 'season', 'gcode', 'venue',
    't_venue_next', 't_gcode_next', 't_opp_next',
    't_ytd_cf60_ev', 't_ytd_ca60_ev', 't_ytd_cf60_all', 't_ytd_ca60_all',
    't_ytd_gf60_ev', 't_ytd_ga60_ev', 't_ytd_gf60_all', 't_ytd_ga60_all']]
    #'t_ytd_v_cf60_ev', 't_ytd_v_ca60_ev', 't_ytd_v_cf60_all', 't_ytd_v_ca60_all',
    #'t_ytd_v_gf60_ev', 't_ytd_v_ga60_ev', 't_ytd_v_gf60_all', 't_ytd_v_ga60_all']]

    ############ SKATERS ############

    print("""
    
    
    Starting Skater fact table building
    
    
    """)

    # Fact table, Time on Ice
    w_p_toi = r_p_toi.copy()

    # Merge in the player IDs
    w_p_toi = w_p_toi\
        .merge(right = m_players,
        how = "left",
        left_on = ['season', 'gcode', 'ev_player_1', 'Abbrev'],
        right_on = ['season', 'game_id', 'ev_player_1', 'team_abbrev'],
        ) \
        .drop(['game_id', 'team_abbrev'], axis=1)

    # Apply home or away indicator

    w_p_toi = w_p_toi\
        .merge(right = d_games,
        how = "left",
        left_on = ['season', 'gcode'],
        right_on = ['season', 'game_id']
        ) \
        .drop(['game_id'], axis=1)

    w_p_toi["venue"] = np.where(w_p_toi["Abbrev"] == w_p_toi["home_team"], "home", "away")

    # Opponent
    w_p_toi["opponent"] = np.where(w_p_toi["Abbrev"] == w_p_toi["home_team"], w_p_toi['away_team'], w_p_toi['home_team'])

    # Start the player modelling from the PBP, ev_player_1 gives us shots and goals

    # FOUND ISSUE 12/1 BLOCKED SHOTS NOT PROPERLY FILLING THE PBP FOR EV1 EV2 OR IS.CORSI
    # FIXED 12/7 NEED TO RESCRAPE
    w_ev1 =\
        r_pbp\
        .query("is_corsi > 0")\
        .groupby(["season", "game_id", "ev_team", "ev_player_1", "strength_cat"])\
        .agg({"is_corsi": ["sum"], 
            "is_shot": ["sum"],
            "is_goal":["sum"]})

    w_ev1.columns =\
        list(map("_".join, w_ev1.columns))

    w_ev1.reset_index(inplace=True)

    w_ev1.rename(columns={'is_corsi_sum':'iCF', 'is_shot_sum':'iSF', 'is_goal_sum':'iGF'}, inplace=True)

    # Blocked shots
    w_blocks =\
        r_pbp\
        .query("event_type == 'BLOCK'")\
        .groupby(["season", "game_id", "ev_team", "ev_player_2", "strength_cat", "home_team", "away_team"])\
        .agg({"is_corsi": ["sum"]})

    w_blocks.columns =\
        list(map("_".join, w_blocks.columns))

    w_blocks.reset_index(inplace=True)

    # Flip the teams as this is from the shooters perspective, not the blocker
    w_blocks['opponent'] = np.where(w_blocks['ev_team'] == w_blocks['away_team'], w_blocks['home_team'], w_blocks['away_team'])

    w_blocks = w_blocks.drop(columns=['ev_team', 'away_team', 'home_team'], axis=1)

    w_blocks.rename(columns={'is_corsi_sum':'iBS', 'ev_player_2':'ev_player_1', 'opponent':'ev_team'}, inplace=True)

    # Primary assists
    w_a1 =\
        r_pbp\
        .query("event_type == 'GOAL'")\
        .groupby(["season", "game_id", "ev_team", "ev_player_2", "strength_cat"])\
        .agg({"is_goal": ["sum"]})

    w_a1.columns =\
        list(map("_".join, w_a1.columns))

    w_a1.reset_index(inplace=True)

    w_a1.rename(columns={'is_goal_sum':'iA1', 'ev_player_2':'ev_player_1'}, inplace=True)

    # Secondary assists
    w_a2 =\
        r_pbp\
        .query("event_type == 'GOAL'")\
        .groupby(["season", "game_id", "ev_team", "ev_player_3", "strength_cat"])\
        .agg({"is_goal": ["sum"]})

    w_a2.columns =\
        list(map("_".join, w_a2.columns))

    w_a2.reset_index(inplace=True)

    w_a2.rename(columns={'is_goal_sum':'iA2', 'ev_player_3':'ev_player_1'}, inplace=True)

    # Pivot wider the player box score DFs so we can merge to the Player TOI table

    # EV 1
    w_ev1 = w_ev1.pivot(index =['season', 'game_id', 'ev_team', 
                                        'ev_player_1'], columns='strength_cat', values = ['iCF', 'iSF', 'iGF'])

    w_ev1.columns =\
        list(map("_".join, w_ev1.columns))

    w_ev1.reset_index(inplace=True)

    # Blocks
    w_blocks = w_blocks.pivot(index =['season', 'game_id', 'ev_team',
                                        'ev_player_1'], columns='strength_cat', values = ['iBS'])

    w_blocks.columns =\
        list(map("_".join, w_blocks.columns))

    w_blocks.reset_index(inplace=True)

    # A1s
    w_a1 = w_a1.pivot(index =['season', 'game_id', 'ev_team', 
                                        'ev_player_1'], columns='strength_cat', values = ['iA1'])

    w_a1.columns =\
        list(map("_".join, w_a1.columns))

    w_a1.reset_index(inplace=True)

    # A2s
    w_a2 = w_a2.pivot(index =['season', 'game_id', 'ev_team', 
                                        'ev_player_1'], columns='strength_cat', values = ['iA2'])

    w_a2.columns =\
        list(map("_".join, w_a2.columns))

    w_a2.reset_index(inplace=True)

    # Merge player box scores to time on ice
    w_p_fact = w_p_toi.copy()

    # Ev 1 (attempts, shots, goals)
    w_p_fact =\
        w_p_fact\
        .merge(
            right = w_ev1,
            how = "left",
            left_on = ['ev_player_1', 'season', 'gcode', 'Abbrev'],
            right_on = ['ev_player_1', 'season', 'game_id', 'ev_team']
        )\
        .drop(['ev_team', 'game_id'], axis=1)

    # Blocks
    w_p_fact =\
        w_p_fact\
        .merge(
            right = w_blocks,
            how = "left",
            left_on = ['ev_player_1', 'season', 'gcode', 'Abbrev'],
            right_on = ['ev_player_1', 'season', 'game_id', 'ev_team']        
        )\
        .drop(['ev_team', 'game_id'], axis=1)

    # A1s
    w_p_fact =\
        w_p_fact\
        .merge(
            right = w_a1,
            how = "left",
            left_on = ['ev_player_1', 'season', 'gcode', 'Abbrev'],
            right_on = ['ev_player_1', 'season', 'game_id', 'ev_team']
        )\
        .drop(['ev_team', 'game_id'], axis=1)

    # A2s
    w_p_fact =\
        w_p_fact\
        .merge(
            right = w_a2,
            how = "left",
            left_on = ['ev_player_1', 'season', 'gcode', 'Abbrev'],
            right_on = ['ev_player_1', 'season', 'game_id', 'ev_team']
        )\
        .drop(['ev_team', 'game_id'], axis=1)

    # Replace NaN with 0
    w_p_fact.fillna(0, inplace=True)

    # Calculate all situations totals
    w_p_fact["iCF_all"] = w_p_fact['iCF_EV'] + w_p_fact['iCF_junk'] + w_p_fact['iCF_PP'] + w_p_fact['iCF_SH']
    w_p_fact["iSF_all"] = w_p_fact['iSF_EV'] + w_p_fact['iSF_junk'] + w_p_fact['iSF_PP'] + w_p_fact['iSF_SH']
    w_p_fact["iGF_all"] = w_p_fact['iGF_EV'] + w_p_fact['iGF_junk'] + w_p_fact['iGF_PP'] + w_p_fact['iGF_SH']

    w_p_fact["iBS_all"] = w_p_fact['iBS_EV'] + + w_p_fact['iBS_PP'] + w_p_fact['iBS_SH']

    w_p_fact["iA1_all"] = w_p_fact['iA1_EV'] + w_p_fact['iA1_PP'] + w_p_fact['iA1_SH']
    w_p_fact["iA2_all"] = w_p_fact['iA2_EV'] + w_p_fact['iA2_PP'] + w_p_fact['iA2_SH']

    # NHL Box points by strength and total
    w_p_fact['p_EV'] = w_p_fact['iGF_EV'] + w_p_fact['iA1_EV'] + w_p_fact['iA2_EV']
    w_p_fact['p_PP'] = w_p_fact['iGF_PP'] + w_p_fact['iA1_PP'] + w_p_fact['iA2_PP']
    w_p_fact['p_SH'] = w_p_fact['iGF_SH'] + w_p_fact['iA1_SH'] + w_p_fact['iA2_SH']
    w_p_fact['p_all'] = w_p_fact['iGF_all'] + w_p_fact['iA1_all'] + w_p_fact['iA2_all']

    # Calculate DK Points

    # Flags for bonuses

    # Shorthanded points
    w_p_fact['sh_bonus'] = np.where(w_p_fact['iGF_SH'] + w_p_fact['iA1_SH'] + w_p_fact['iA2_SH'] >= 1,
    (w_p_fact['iGF_SH'] + w_p_fact['iA1_SH'] + w_p_fact['iA2_SH']) * 2, 
    0)

    # Blocked shots
    w_p_fact['blk_bonus'] = np.where(w_p_fact['iBS_all'] >=3, 3, 0)

    # Hat-trick
    w_p_fact['ht_bonus'] = np.where(w_p_fact['iGF_all'] >= 3, 3, 0)

    # Shots
    w_p_fact['iSF_bonus'] = np.where(w_p_fact['iSF_all'] >= 5, 3, 0)

    # Points
    w_p_fact['p_bonus'] = np.where(w_p_fact['p_all'] >=3, 3, 0)

    # DraftKings Points
    w_p_fact['DK_Points'] = (w_p_fact['iGF_all'] * 8.5) +\
    ((w_p_fact['iA1_all'] + w_p_fact['iA2_all']) * 5) +\
    (w_p_fact['iSF_all'] * 1.5) +\
    (w_p_fact['iBS_all'] * 1.3) +\
    w_p_fact['sh_bonus'] +\
    w_p_fact['blk_bonus'] +\
    w_p_fact['ht_bonus'] +\
    w_p_fact['iSF_bonus'] +\
    w_p_fact['p_bonus']

    # Rolling 5. YTD at Venue. YTD.

    # Order by Player ID then game date
    model_players = w_p_fact.copy()

    # Convert string date to date
    model_players['game_date'] = pd.to_datetime(model_players['game_date'])
    model_players = model_players.sort_values(by=["playerId", "game_date"])

    # Year to date (all, EV, PP)
    # Ice time
    model_players['p_ytd_game_num'] = model_players.groupby(['playerId', 'season']).cumcount()+1
    model_players['p_ytd_ev_toi'] = model_players.groupby(['playerId', 'season'])['ev_time'].cumsum()
    model_players['p_ytd_sh_toi'] = model_players.groupby(['playerId', 'season'])['sh_time'].cumsum()
    model_players['p_ytd_pp_toi'] = model_players.groupby(['playerId', 'season'])['pp_time'].cumsum()

    # Per game
    model_players['p_ytd_ev_toigp'] = model_players['p_ytd_ev_toi'] / model_players['p_ytd_game_num']
    model_players['p_ytd_sh_toigp'] = model_players['p_ytd_sh_toi'] / model_players['p_ytd_game_num']
    model_players['p_ytd_pp_toigp'] = model_players['p_ytd_pp_toi'] / model_players['p_ytd_game_num']

    # Box score (corsi, shots, assists, blocks, dk points)
    model_players['p_ytd_icf_ev'] = model_players.groupby(['playerId', 'season'])['iCF_EV'].cumsum()
    model_players['p_ytd_icf_pp'] = model_players.groupby(['playerId', 'season'])['iCF_PP'].cumsum()
    model_players['p_ytd_icf_all'] = model_players.groupby(['playerId', 'season'])['iCF_all'].cumsum()

    model_players['p_ytd_isf_ev'] = model_players.groupby(['playerId', 'season'])['iSF_EV'].cumsum()
    model_players['p_ytd_isf_pp'] = model_players.groupby(['playerId', 'season'])['iSF_PP'].cumsum()
    model_players['p_ytd_isf_all'] = model_players.groupby(['playerId', 'season'])['iSF_all'].cumsum()
    model_players['p_ytd_isf_avg'] = model_players['p_ytd_isf_all'] / model_players['p_ytd_game_num']

    model_players['p_ytd_igf_ev'] = model_players.groupby(['playerId', 'season'])['iGF_EV'].cumsum()
    model_players['p_ytd_igf_pp'] = model_players.groupby(['playerId', 'season'])['iGF_PP'].cumsum()
    model_players['p_ytd_igf_all'] = model_players.groupby(['playerId', 'season'])['iGF_all'].cumsum()
    model_players['p_ytd_igf_avg'] = model_players['p_ytd_igf_all'] / model_players['p_ytd_game_num']

    model_players['p_ytd_a1_ev'] = model_players.groupby(['playerId', 'season'])['iA1_EV'].cumsum()
    model_players['p_ytd_a1_pp'] = model_players.groupby(['playerId', 'season'])['iA1_PP'].cumsum()
    model_players['p_ytd_a1_all'] = model_players.groupby(['playerId', 'season'])['iA1_all'].cumsum()

    model_players['p_ytd_a2_ev'] = model_players.groupby(['playerId', 'season'])['iA2_EV'].cumsum()
    model_players['p_ytd_a2_pp'] = model_players.groupby(['playerId', 'season'])['iA2_PP'].cumsum()
    model_players['p_ytd_a2_all'] = model_players.groupby(['playerId', 'season'])['iA2_all'].cumsum()

    model_players['p_ytd_iA_avg'] = (model_players['p_ytd_a1_all'] + model_players['p_ytd_a2_all']) / model_players['p_ytd_game_num']

    model_players['p_ytd_ibs_ev'] = model_players.groupby(['playerId', 'season'])['iBS_EV'].cumsum()
    model_players['p_ytd_ibs_sh'] = model_players.groupby(['playerId', 'season'])['iBS_SH'].cumsum()
    model_players['p_ytd_ibs_all'] = model_players.groupby(['playerId', 'season'])['iBS_all'].cumsum()
    model_players['p_ytd_ibs_avg'] = model_players['p_ytd_ibs_all'] / model_players['p_ytd_game_num']

    model_players['p_ytd_dk'] = model_players.groupby(['playerId', 'season'])['DK_Points'].cumsum()


    # Year to date, venue (all, EV, PP)
    # Ice time
    #model_players['p_ytd_v_game_num'] = model_players.groupby(['playerId', 'season', 'venue']).cumcount()+1
    #model_players['p_ytd_v_ev_toi'] = model_players.groupby(['playerId', 'season', 'venue'])['ev_time'].cumsum()
    #model_players['p_ytd_v_sh_toi'] = model_players.groupby(['playerId', 'season', 'venue'])['sh_time'].cumsum()
    #model_players['p_ytd_v_pp_toi'] = model_players.groupby(['playerId', 'season', 'venue'])['pp_time'].cumsum()

    # Per game
    #model_players['p_ytd_v_ev_toigp'] = model_players['p_ytd_v_ev_toi'] / model_players['p_ytd_v_game_num']
    #model_players['p_ytd_v_sh_toigp'] = model_players['p_ytd_v_sh_toi'] / model_players['p_ytd_v_game_num']
    #model_players['p_ytd_v_pp_toigp'] = model_players['p_ytd_v_pp_toi'] / model_players['p_ytd_v_game_num']

    # Box score (corsi, shots, assists, blocks, dk points)
    #model_players['p_ytd_v_icf_ev'] = model_players.groupby(['playerId', 'season', 'venue'])['iCF_EV'].cumsum()
    #model_players['p_ytd_v_icf_pp'] = model_players.groupby(['playerId', 'season', 'venue'])['iCF_PP'].cumsum()
    #model_players['p_ytd_v_icf_all'] = model_players.groupby(['playerId', 'season', 'venue'])['iCF_all'].cumsum()

    #model_players['p_ytd_v_isf_ev'] = model_players.groupby(['playerId', 'season', 'venue'])['iSF_EV'].cumsum()
    #model_players['p_ytd_v_isf_pp'] = model_players.groupby(['playerId', 'season', 'venue'])['iSF_PP'].cumsum()
    #model_players['p_ytd_v_isf_all'] = model_players.groupby(['playerId', 'season', 'venue'])['iSF_all'].cumsum()
    #model_players['p_ytd_v_isf_avg'] = model_players['p_ytd_v_isf_all'] / model_players['p_ytd_v_game_num']

    #model_players['p_ytd_v_igf_ev'] = model_players.groupby(['playerId', 'season', 'venue'])['iGF_EV'].cumsum()
    #model_players['p_ytd_v_igf_pp'] = model_players.groupby(['playerId', 'season', 'venue'])['iGF_PP'].cumsum()
    #model_players['p_ytd_v_igf_all'] = model_players.groupby(['playerId', 'season', 'venue'])['iGF_all'].cumsum()
    #model_players['p_ytd_v_igf_avg'] = model_players['p_ytd_v_igf_all'] / model_players['p_ytd_v_game_num']

    #model_players['p_ytd_v_a1_ev'] = model_players.groupby(['playerId', 'season', 'venue'])['iA1_EV'].cumsum()
    #model_players['p_ytd_v_a1_pp'] = model_players.groupby(['playerId', 'season', 'venue'])['iA1_PP'].cumsum()
    #model_players['p_ytd_v_a1_all'] = model_players.groupby(['playerId', 'season', 'venue'])['iA1_all'].cumsum()

    #model_players['p_ytd_v_a2_ev'] = model_players.groupby(['playerId', 'season', 'venue'])['iA2_EV'].cumsum()
    #model_players['p_ytd_v_a2_pp'] = model_players.groupby(['playerId', 'season', 'venue'])['iA2_PP'].cumsum()
    #model_players['p_ytd_v_a2_all'] = model_players.groupby(['playerId', 'season', 'venue'])['iA2_all'].cumsum()

    #model_players['p_ytd_v_iA_avg'] = (model_players['p_ytd_v_a1_all'] + model_players['p_ytd_v_a2_all']) / model_players['p_ytd_v_game_num']

    #model_players['p_ytd_v_ibs_ev'] = model_players.groupby(['playerId', 'season', 'venue'])['iBS_EV'].cumsum()
    #model_players['p_ytd_v_ibs_sh'] = model_players.groupby(['playerId', 'season', 'venue'])['iBS_SH'].cumsum()
    #model_players['p_ytd_v_ibs_all'] = model_players.groupby(['playerId', 'season', 'venue'])['iBS_all'].cumsum()
    #model_players['p_ytd_v_ibs_avg'] = model_players['p_ytd_v_ibs_all'] / model_players['p_ytd_v_game_num']

    #model_players['p_ytd_v_dk'] = model_players.groupby(['playerId', 'season', 'venue'])['DK_Points'].cumsum()

    # Rolling 5, venue agnostic
    model_players['p_five_ev_toi'] = model_players.groupby(['playerId', 'season'])['ev_time'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_sh_toi'] = model_players.groupby(['playerId', 'season'])['sh_time'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_pp_toi'] = model_players.groupby(['playerId', 'season'])['pp_time'].transform(lambda x: x.rolling(5, 5).sum())

    # Per game
    model_players['p_five_ev_toigp'] = model_players['p_five_ev_toi'] / 5
    model_players['p_five_sh_toigp'] = model_players['p_five_sh_toi'] / 5
    model_players['p_five_pp_toigp'] = model_players['p_five_pp_toi'] / 5

    # Box score (corsi, shots, assists, blocks, dk points)
    model_players['p_five_icf_ev'] = model_players.groupby(['playerId', 'season'])['iCF_EV'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_icf_pp'] = model_players.groupby(['playerId', 'season'])['iCF_PP'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_icf_all'] = model_players.groupby(['playerId', 'season'])['iCF_all'].transform(lambda x: x.rolling(5, 5).sum())

    model_players['p_five_isf_ev'] = model_players.groupby(['playerId', 'season'])['iSF_EV'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_isf_pp'] = model_players.groupby(['playerId', 'season'])['iSF_PP'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_isf_all'] = model_players.groupby(['playerId', 'season'])['iSF_all'].transform(lambda x: x.rolling(5, 5).sum())

    model_players['p_five_igf_ev'] = model_players.groupby(['playerId', 'season'])['iGF_EV'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_igf_pp'] = model_players.groupby(['playerId', 'season'])['iGF_PP'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_igf_all'] = model_players.groupby(['playerId', 'season'])['iGF_all'].transform(lambda x: x.rolling(5, 5).sum())

    model_players['p_five_a1_ev'] = model_players.groupby(['playerId', 'season'])['iA1_EV'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_a1_pp'] = model_players.groupby(['playerId', 'season'])['iA1_PP'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_a1_all'] = model_players.groupby(['playerId', 'season'])['iA1_all'].transform(lambda x: x.rolling(5, 5).sum())

    model_players['p_five_a2_ev'] = model_players.groupby(['playerId', 'season'])['iA2_EV'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_a2_pp'] = model_players.groupby(['playerId', 'season'])['iA2_PP'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_a2_all'] = model_players.groupby(['playerId', 'season'])['iA2_all'].transform(lambda x: x.rolling(5, 5).sum())

    model_players['p_five_ibs_ev'] = model_players.groupby(['playerId', 'season'])['iBS_EV'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_ibs_sh'] = model_players.groupby(['playerId', 'season'])['iBS_SH'].transform(lambda x: x.rolling(5, 5).sum())
    model_players['p_five_ibs_all'] = model_players.groupby(['playerId', 'season'])['iBS_all'].transform(lambda x: x.rolling(5, 5).sum())

    model_players['p_five_dk'] = model_players.groupby(['playerId', 'season'])['DK_Points'].transform(lambda x: x.rolling(5, 5).sum())

    # Keep players most recent row

    # Make sure it's sorted by playerId and then date because we are doing a lazy MAX here
    model_players = model_players.sort_values(by=["playerId", "game_date"])
    model_players = model_players.groupby('playerId').last().reset_index()

    # Debugging print status
    print("Switching from model cleansing to merging in DK info")

    # Merge in the DK info for tonight's venue/opponent
    m_dk = w_dk.drop(columns=['Name + ID', 'Name', 'ID', 'Roster Position', 'game_info', 'TeamAbbrev', 
    'AvgPointsPerGame', 'Slate', 'away', 'home'])

    model_players =\
        model_players\
        .merge(
            right = m_dk,
            how = "left",
            left_on = ['playerId'],
            right_on = ['nhl_playerId']
        )
    
    # Remove anyone without a salary holding only active players on this slate
    model_players.dropna(subset=['Salary'], inplace=True)

    # Now drop any NA rows so we can run the model fit
    model_players.dropna(inplace=True)

    # Force player position as string and then split between forwards and defense
    model_players['positionCode'] = model_players['positionCode'].astype(str)

    # Merge in the team metrics

    # Get the most recent line per team and merge to p_opp_next
    f_teams = f_teams.groupby('Abbrev').last().reset_index()

    # Clean fact teams for merge
    m_teams = f_teams.copy()
    m_teams = m_teams.drop(columns=['team_name', 'gcode', 'venue', 't_venue_next', 't_opp_next', 'season', 't_gcode_next'])

    # Merge to model_players
    model_players =\
        model_players\
        .merge(
            right = m_teams,
            how = "left",
            left_on = ['p_opp_next'],
            right_on = ['Abbrev']
        )\
        .drop(columns=['Abbrev_y'])

    model_players.rename(columns={'Abbrev_x':'Abbrev'}, inplace=True)

    model_players_f =\
        model_players\
        .query("positionCode != 'D'")

    model_players_d =\
        model_players\
        .query("positionCode == 'D'")

    # Clean dataframes for merging after the models run on the model_players dfs
    f_defense = model_players_d[['playerId', 'team', 'Abbrev', 'full_name', 'Position', 'Salary', 'p_opp_next']]
    f_forwards = model_players_f[['playerId', 'team', 'Abbrev', 'full_name', 'Position', 'Salary', 'p_opp_next']]

    # Defense
    # Load the models
    dfs_assists_fit_d = joblib.load('dfs_assists_fit_d.joblib')
    dfs_blocks_fit_d = joblib.load('dfs_blocks_fit_d.joblib')
    dfs_goals_fit_d = joblib.load('dfs_goals_fit_d.joblib')
    dfs_shots_fit_d = joblib.load('dfs_shots_fit_d.joblib')

    predictions_d_assists = dfs_assists_fit_d.predict(model_players_d)
    predictions_d_blocks = dfs_blocks_fit_d.predict(model_players_d)
    predictions_d_goals = dfs_goals_fit_d.predict(model_players_d)
    predictions_d_shots = dfs_shots_fit_d.predict(model_players_d)

    # Col bind into the dataframe
    f_defense = pd.concat([f_defense, predictions_d_assists.rename('x_assists')], axis=1)
    f_defense = pd.concat([f_defense, predictions_d_blocks.rename('x_blocks')], axis=1)
    f_defense = pd.concat([f_defense, predictions_d_goals.rename('x_goals')], axis=1)
    f_defense = pd.concat([f_defense, predictions_d_shots.rename('x_shots')], axis=1)

    # Calculate the DK points from the AVERAGES
    f_defense['x_dk_lazy'] = (f_defense['x_goals'] * 8.5) + (f_defense['x_assists'] * 5) + (f_defense['x_shots'] * 1.5) + (f_defense['x_blocks'] * 1.3)
    f_defense['x_value_lazy'] =  f_defense['x_dk_lazy'] / (f_defense['Salary']/1000)

    # Forwards
    # Load the models
    dfs_assists_fit_f = joblib.load('dfs_assists_fit_f.joblib')
    dfs_blocks_fit_f = joblib.load('dfs_blocks_fit_f.joblib')
    dfs_goals_fit_f = joblib.load('dfs_goals_fit_f.joblib')
    dfs_shots_fit_f = joblib.load('dfs_shots_fit_f.joblib')

    predictions_f_assists = dfs_assists_fit_f.predict(model_players_f)
    predictions_f_blocks = dfs_blocks_fit_f.predict(model_players_f)
    predictions_f_goals = dfs_goals_fit_f.predict(model_players_f)
    predictions_f_shots = dfs_shots_fit_f.predict(model_players_f)

    # Col bind into the dataframe
    f_forwards = pd.concat([f_forwards, predictions_f_assists.rename('x_assists')], axis=1)
    f_forwards = pd.concat([f_forwards, predictions_f_blocks.rename('x_blocks')], axis=1)
    f_forwards = pd.concat([f_forwards, predictions_f_goals.rename('x_goals')], axis=1)
    f_forwards = pd.concat([f_forwards, predictions_f_shots.rename('x_shots')], axis=1)

    # Calculate the DK points from the AVERAGES
    f_forwards['x_dk_lazy'] = (f_forwards['x_goals'] * 8.5) + (f_forwards['x_assists'] * 5) + (f_forwards['x_shots'] * 1.5) + (f_forwards['x_blocks'] * 1.3)
    f_forwards['x_value_lazy'] =  f_forwards['x_dk_lazy'] / (f_forwards['Salary']/1000)

    # Merge the forward and defense tables together
    f_skaters = pd.concat([f_defense, f_forwards])

    # Add today's date to the fact skaters table
    f_skaters['slate'] = slate_date

    print("""
    
    SKATERS ARE FINISHED, BEGINNING GOALIE MANIPULATION
    
    """)

    # I think for goalies all I care about is their historical normal shots against
    # saves, sv%, and how many shots and goals the team they are playing puts up?

    w_g_pbp = r_pbp.copy()

    # ID which goalie faced the corsi
    w_g_pbp['ev_goalie'] = np.where(w_g_pbp['ev_team'] == w_g_pbp['away_team'], w_g_pbp['HomeGoalie'], w_g_pbp['AwayGoalie'])
    w_g_pbp['against_team'] = np.where(w_g_pbp['ev_team'] == w_g_pbp['away_team'], w_g_pbp['home_team'], w_g_pbp['away_team'])


    w_g_box =\
        w_g_pbp\
        .query("is_corsi > 0")\
        .groupby(["season", "game_id", "against_team", "ev_goalie"])\
        .agg({"is_corsi": ["sum"], 
            "is_shot": ["sum"],
            "is_goal":["sum"]})

    w_g_box.columns =\
        list(map("_".join, w_g_box.columns))

    w_g_box.reset_index(inplace=True)

    w_g_box.rename(columns={'is_corsi_sum':'CA', 'is_goal_sum':'GA', 'is_shot_sum': 'SA', 'against_team':'Abbrev'}, inplace=True)

    # Work the merge to the goalie toi df

    # Bring team info from d_players into the goalie box
    # If the teams don't match, remove the row

    # Remove the first 7 characters from ev_goalie (removes 'Goalie ')
    w_g_box['ev_goalie'] = w_g_box['ev_goalie'].str[7:]

    # Match the goalie name in d_players to w_g_box
    d_players['goalie_merge'] = d_players['first_name'].str.upper() + ' ' + d_players['last_name'].str.upper() + ' ' + d_players['sweaterNumber'].astype(str)

    m_goalies =\
        d_players\
        .query("positionCode == 'G'")

    m_goalies = m_goalies[['playerId', 'team_abbrev', 'goalie_merge', 'season', 'game_id']]

    w_g_box =\
        w_g_box\
        .merge(
            right = m_goalies,
            how = "left",
            left_on = ['season', 'game_id', 'ev_goalie'],
            right_on = ['season', 'game_id', 'goalie_merge']
        )\
        .drop(columns=['goalie_merge'])

    # Remove rows where the goalie stats df does not equal the player df
    # The player df is more reliable, so this will eliminate junk rows

    w_g_box['team_check'] = np.where(w_g_box['Abbrev'] != w_g_box['team_abbrev'], 1, 0)
    w_g_box =\
        w_g_box\
        .query('team_check == 0')\
        .drop(columns=['team_check', 'team_abbrev'])

    # Merge in TOI from r_goalies
    m_goalies = r_goalies.copy()

    m_goalies = m_goalies[['full_name', 'season', 'gcode', 'tot_toi']]

    w_g_box =\
        w_g_box\
        .merge(
            right = m_goalies,
            how = "left",
            left_on = ['season', 'game_id', 'ev_goalie'],
            right_on = ['season', 'gcode', 'full_name']
        )\
        .drop(columns=['gcode', 'full_name'])

    # Bring in d_games so we can get game date and the home/away flag
    w_g_box =\
        w_g_box\
        .merge(
            right = d_games,
            how = "left",
            left_on = ['season', 'game_id'],
            right_on = ['season', 'game_id']
        )

    # Flag home/away
    #w_g_box['venue'] = np.where(w_g_box['Abbrev'] == w_g_box['home_team'], 'home', 'away')
    #w_g_box['opponent'] = np.where(w_g_box['Abbrev'] == w_g_box['home_team'], w_g_box['away_team'], w_g_box['home_team'])

    # Sort by player id and game date so we can start manipulating this df
    w_g_box['game_date'] = pd.to_datetime(w_g_box['game_date'])
    w_g_box = w_g_box.sort_values(by=["playerId", "game_date"])

    # Only include games where goalies played at least 50 minutes for the sake of the model
    #w_g_box =\
    #    w_g_box\
    #    .query('tot_toi >= 3000')

    # next venue, opponent, game_id
    #w_g_box['g_venue_next'] = w_g_box.groupby(['Abbrev', 'season', 'playerId'])['venue'].shift(-1)
    #w_g_box['g_gcode_next'] = w_g_box.groupby(['Abbrev', 'season', 'playerId'])['game_id'].shift(-1)
    #w_g_box['g_opp_next'] = w_g_box.groupby(['Abbrev', 'season', 'playerId'])['opponent'].shift(-1)

    #w_g_box['g_sa_next'] = w_g_box.groupby(['Abbrev', 'season', 'playerId'])['SA'].shift(-1)
    #w_g_box['g_ga_next'] = w_g_box.groupby(['Abbrev', 'season', 'playerId'])['GA'].shift(-1)

    # Roll metrics for YTD and 5
    model_goalies = w_g_box.copy()

    model_goalies['g_ytd_toi'] = model_goalies.groupby(['season', 'playerId'])['tot_toi'].cumsum()

    model_goalies['g_ytd_ca'] = model_goalies.groupby(['season', 'playerId'])['CA'].cumsum()
    model_goalies['g_ytd_sa'] = model_goalies.groupby(['season', 'playerId'])['SA'].cumsum()
    model_goalies['g_ytd_ga'] = model_goalies.groupby(['season', 'playerId'])['GA'].cumsum()

    model_goalies['g_five_toi'] = model_goalies.groupby(['season', 'playerId'])['tot_toi'].transform(lambda x: x.rolling(5, 5).sum())

    model_goalies['g_five_ca'] = model_goalies.groupby(['season', 'playerId'])['CA'].transform(lambda x: x.rolling(5, 5).sum())
    model_goalies['g_five_sa'] = model_goalies.groupby(['season', 'playerId'])['SA'].transform(lambda x: x.rolling(5, 5).sum())
    model_goalies['g_five_ga'] = model_goalies.groupby(['season', 'playerId'])['GA'].transform(lambda x: x.rolling(5, 5).sum())

    # Calculate rolling sv%
    model_goalies['g_ytd_svp'] = (model_goalies['g_ytd_sa'] - model_goalies['g_ytd_ga']) / model_goalies['g_ytd_sa']
    model_goalies['g_five_svp'] = (model_goalies['g_five_sa'] - model_goalies['g_five_ga']) / model_goalies['g_five_sa']

    # Per 60 the counting stats
    model_goalies['g_ytd_ca60'] = (model_goalies['g_ytd_ca'] * 3600) / model_goalies['g_ytd_toi']
    model_goalies['g_ytd_sa60'] = (model_goalies['g_ytd_sa'] * 3600) / model_goalies['g_ytd_toi']
    model_goalies['g_ytd_ga60'] = (model_goalies['g_ytd_ga'] * 3600) / model_goalies['g_ytd_toi']

    model_goalies['g_five_ca60'] = (model_goalies['g_five_ca'] * 3600) / model_goalies['g_five_toi']
    model_goalies['g_five_sa60'] = (model_goalies['g_five_sa'] * 3600) / model_goalies['g_five_toi']
    model_goalies['g_five_ga60'] = (model_goalies['g_five_ga'] * 3600) / model_goalies['g_five_toi']

    # Make sure it's sorted by playerId and then date because we are doing a lazy MAX here
    model_goalies = model_goalies.sort_values(by=["playerId", "game_date"])
    model_goalies = model_goalies.groupby('playerId').last().reset_index()

    model_goalies =\
        model_goalies\
        .merge(
            right = m_dk,
            how = "left",
            left_on = ['playerId'],
            right_on = ['nhl_playerId']
        )

    # Remove anyone without a salary holding only active players on this slate
    model_goalies.dropna(subset=['Salary'], inplace=True)

    # Rename from player tagging (p_) to goalie tagging (g_)
    model_goalies.rename(columns={'p_opp_next':'g_opp_next', 'p_venue_next':'g_venue_next'}, inplace=True)

    # Now drop any NA rows so we can run the model fit
    model_goalies.dropna(inplace=True)

    # Merge team information
    model_goalies =\
        model_goalies\
        .merge(
            right = m_teams,
            how = "left",
            left_on = ['g_opp_next'],
            right_on = ['Abbrev']
        )\
        .drop(columns=['Abbrev_y'])

    model_goalies.rename(columns={'Abbrev_x':'Abbrev', 'ev_goalie':'full_name'}, inplace=True)


    # Clean dataframe for merging after the models run on the model_goalies df
    f_goalies = model_goalies[['playerId', 'Abbrev', 'full_name', 'Position', 'Salary', 'g_opp_next']]

    # Load the models
    dfs_sa_fit_g = joblib.load('dfs_sa_fit_g.joblib')
    dfs_ga_fit_g = joblib.load('dfs_ga_fit_g.joblib')

    # Make predictions and then col bind into the fact df
    predictions_g_sa = dfs_sa_fit_g.predict(model_goalies)
    predictions_g_ga = dfs_ga_fit_g.predict(model_goalies)

    f_goalies = pd.concat([f_goalies, predictions_g_sa.rename('x_sa')], axis=1)
    f_goalies = pd.concat([f_goalies, predictions_g_ga.rename('x_ga')], axis=1)

    # Calculate saves and then DK points (without win probability right now)
    f_goalies['x_saves'] = f_goalies['x_sa'] - f_goalies['x_ga']

    # Check for saves bonus
    f_goalies['x_saves_b'] = np.where(f_goalies['x_saves'] >=35, 3, 0)

    print("""

    Scraping Vegas odds for goalies from the NHL site (debug line 1062)

    """)

    # scrape vegas odds for win probability in goalie projections
    f_odds = scrape_schedule_vegas(slate_day)

    # Merge odds to goalies
    f_goalies =\
        f_goalies\
        .merge(
            right = f_odds,
            how = "left",
            left_on = ['Abbrev'],
            right_on = ['Abbrev']
        )

    # DK Points (lazy)
    f_goalies['x_dk_lazy'] = (f_goalies['x_saves'] * 0.7) + (f_goalies['x_ga'] * -3.5) + f_goalies['x_saves_b'] + (f_goalies['w_probability'] * 6)
    f_goalies['x_value_lazy'] =  f_goalies['x_dk_lazy'] / (f_goalies['Salary']/1000)

    # Add today's date to the fact skaters table
    f_goalies['slate'] = slate_date

    print("""
    

    Finding potential correlation spots in the slate by predicting cf/ca gf/ga for each matchup


    """)

    # Game prediction model
    w_games = w_teams.copy()
    w_games = w_games[['team_name', 'Abbrev', 'game_date',
    't_ytd_cf60_ev', 't_ytd_ca60_ev', 't_ytd_cf60_all', 't_ytd_ca60_all',
    't_ytd_gf60_ev', 't_ytd_ga60_ev', 't_ytd_gf60_all', 't_ytd_ga60_all',
    't_ytd_csvp_all']]

    # Keep team max row
    w_games = w_games.sort_values(by=["Abbrev", "game_date"])
    w_games = w_games.groupby('Abbrev').last().reset_index()

    # Load in today's slate from the NHL
    print("scraping the nhl schedule as part of the game modeling, code line 1114")
    r_nhl_slate = scrape_schedule(slate_day)

    # Merge the home team data to the NHL slate
    f_games =\
        r_nhl_slate\
        .merge(
            how = "left",
            right = w_games,
            left_on = ['home_abbrev'],
            right_on = ['Abbrev']
        )
    
    # Clean w_games to be from the away team perspective
    w_t_a_merge = w_games.copy()
    w_t_a_merge.rename(columns={'t_ytd_cf60_ev':'a_ytd_cf60_ev',
    't_ytd_cf60_ev':'a_ytd_cf60_ev',
    't_ytd_ca60_ev':'a_ytd_ca60_ev',
    't_ytd_cf60_all':'a_ytd_cf60_all',
    't_ytd_ca60_all':'a_ytd_ca60_all',
    't_ytd_gf60_ev':'a_ytd_gf60_ev',
    't_ytd_ga60_ev':'a_ytd_ga60_ev',
    't_ytd_gf60_all':'a_ytd_gf60_all',
    't_ytd_ga60_all':'a_ytd_ga60_all',
    't_ytd_csvp_all':'a_ytd_csvp_all'
    }, inplace=True)

    # Merge into f_games
    f_games =\
        f_games\
        .merge(
            how = "left",
            right = w_t_a_merge,
            left_on = ['away_abbrev'],
            right_on = ['Abbrev']
        )
    
    # Apply the predictions to f games
    dfs_cf_fit_t = joblib.load('dfs_cf_fit_t.joblib')
    dfs_ca_fit_t = joblib.load('dfs_ca_fit_t.joblib')
    dfs_gf_fit_t = joblib.load('dfs_gf_fit_t.joblib')
    dfs_ga_fit_t = joblib.load('dfs_ga_fit_t.joblib')

    # Make predictions and then col bind into the fact df
    predictions_t_cf = dfs_cf_fit_t.predict(f_games)
    predictions_t_ca = dfs_ca_fit_t.predict(f_games)
    predictions_t_gf = dfs_gf_fit_t.predict(f_games)
    predictions_t_ga = dfs_ga_fit_t.predict(f_games)

    f_games = pd.concat([f_games, predictions_t_cf.rename('x_cf')], axis=1)
    f_games = pd.concat([f_games, predictions_t_ca.rename('x_ca')], axis=1)
    f_games = pd.concat([f_games, predictions_t_gf.rename('x_gf')], axis=1)
    f_games = pd.concat([f_games, predictions_t_ga.rename('x_ga')], axis=1)

    # Form into a readable df
    f_games = f_games[['home_abbrev', 'away_abbrev', 'game_id', 'game_date_x',
    'x_cf', 'x_ca', 'x_gf', 'x_ga']]

    f_games['x_pace'] = f_games['x_cf'] + f_games['x_ca']
    f_games['x_goals'] = f_games['x_gf'] + f_games['x_ga']
    f_games.rename(columns={'game_date_x':'game_date'}, inplace=True)
    f_games = f_games.sort_values(by=['x_goals'], ascending=False)

    # Round cols
    f_games = f_games.round(2)

    print("""
    
    Game Summary
    
    """)
    print(f_games)

    # Calculate player role ytd and rolling 5 based on EV and PP TOI
    # Help when trying to find the value plays to fill the roster

    print("""
        
    Evaluating player roles based on EV/PP TOI
    Debug line 1193    
        
    """)

    # Get the teams rolling 5 and ytd ev and pp toi from w_teams
    w_t_roles = w_teams.copy()

    # So far, only ytd ev toi is rolled so we need to do more rolling here
    w_t_roles = w_t_roles[['team_name', 'Abbrev', 'season', 'gcode', 'game_date', 
    'ev_toi', 'pp_toi']]

    # Rename toi cols so we know it's the time not the player
    w_t_roles.rename(columns={'ev_toi':'t_ev_toi', 'pp_toi':'t_pp_toi'}, inplace=True)

    # Start building the player df we'll merge the team data to
    w_p_roles = w_p_fact.copy()

    w_p_roles = w_p_roles[['gcode', 'game_date', 'playerId', 'Abbrev', 'positionCode', 'ev_time', 'pp_time']]

    # Arrange and roll
    w_p_roles['game_date'] = pd.to_datetime(w_p_roles['game_date'])
    w_p_roles = w_p_roles.sort_values(by=['playerId', 'game_date'])

    # Merge in the team
    # Makes more sense to merge the team TOI to the player dataframe bc I don't care
    # if a player missed a game, I want to know their role when they play
    f_p_roles = w_p_roles.copy()
    
    f_p_roles =\
        f_p_roles\
        .merge(
            right = w_t_roles,
            how = "left",
            left_on = ['gcode', 'Abbrev'],
            right_on = ['gcode', 'Abbrev']
        )

    # Roll players
    f_p_roles['p_ytd_ev_toi'] = f_p_roles.groupby(['playerId', 'Abbrev'])['ev_time'].cumsum()
    f_p_roles['p_ytd_pp_toi'] = f_p_roles.groupby(['playerId', 'Abbrev'])['pp_time'].cumsum()

    f_p_roles['p_five_ev_toi'] = f_p_roles.groupby(['playerId', 'Abbrev'])['ev_time'].transform(lambda x: x.rolling(5,5).sum())
    f_p_roles['p_five_pp_toi'] = f_p_roles.groupby(['playerId', 'Abbrev'])['pp_time'].transform(lambda x: x.rolling(5,5).sum())

    # Roll teams
    f_p_roles['t_ytd_ev_toi'] = f_p_roles.groupby(['season', 'Abbrev', 'playerId'])['t_ev_toi'].cumsum()
    f_p_roles['t_ytd_pp_toi'] = f_p_roles.groupby(['season', 'Abbrev', 'playerId'])['t_pp_toi'].cumsum()

    f_p_roles['t_five_ev_toi'] = f_p_roles.groupby(['season', 'Abbrev', 'playerId'])['t_ev_toi'].transform(lambda x: x.rolling(5,5).sum())
    f_p_roles['t_five_pp_toi'] = f_p_roles.groupby(['season', 'Abbrev', 'playerId'])['t_pp_toi'].transform(lambda x: x.rolling(5,5).sum())
    
    # Divide the player TOI by the team TOI to get a percentage
    f_p_roles['ev_ytd'] = f_p_roles['p_ytd_ev_toi'] / f_p_roles['t_ytd_ev_toi']
    f_p_roles['ev_five'] = f_p_roles['p_five_ev_toi'] / f_p_roles['t_five_ev_toi']

    f_p_roles['pp_ytd'] = f_p_roles['p_ytd_pp_toi'] / f_p_roles['t_ytd_pp_toi']
    f_p_roles['pp_five'] = f_p_roles['p_five_pp_toi'] / f_p_roles['t_five_pp_toi']

    # Limit dataframe to the cols we care about
    f_p_roles = f_p_roles[['game_date_x', 'playerId', 'Abbrev', 'positionCode', 'ev_ytd', 'ev_five', 'pp_ytd', 'pp_five']]

    # Get most current row for each player
    # Make sure it's sorted by playerId and then date because we are doing a lazy MAX here
    f_p_roles = f_p_roles.sort_values(by=["playerId", "game_date_x"])
    f_p_roles = f_p_roles.groupby('playerId').last().reset_index()

    # Drop NAs
    f_p_roles.dropna(inplace=True)

    # Future state: Calculate percentiles and categorize players
    # For now, just having the % of TOI is probably good enough for this use-case

    # Merge the roles data to the fact skater table
    m_p_roles = f_p_roles.copy()
    m_p_roles = m_p_roles[['playerId', 'ev_ytd', 'ev_five', 'pp_ytd', 'pp_five']]

    f_skaters =\
        f_skaters\
        .merge(
            right = m_p_roles,
            how = "left",
            left_on = ['playerId'],
            right_on = ['playerId']
        )



    # Manipulate a 'solver' equivalent and print the optimal lineup assuming a $8000 goalie
    # Until we actually do goalie projections, I guess

    # Copied from https://medium.com/ml-everything/using-python-and-linear-programming-to-optimize-fantasy-football-picks-dc9d1229db81

#    print("""
    
    
#    Working on the 'optimal' lineup locking UTIL in as a winger until we can solve that
        
    
#    """)

#    w_solver = f_skaters.copy()
#    w_solver = w_solver[['Position', 'full_name', 'Salary', 'x_dk_lazy']]

#    w_g_solver = f_goalies.copy()
#    w_g_solver = w_g_solver[['Position','full_name', 'Salary', 'x_dk_lazy']]

#    w_solver = pd.concat([w_solver, w_g_solver])

    # Make wingers 'W'
#    w_solver['Position'] = np.where((w_solver['Position'] == 'LW') | (w_solver['Position'] == 'RW'), 'W', w_solver['Position'])
    
    # Remove problem children (injuries)
    #w_solver =\
    #    w_solver\
    #    .query("full_name != 'JONATHAN DROUIN 27'")

#    salaries = {}
#    points = {}

#    SALARY_CAP = 50000

    # Just makes a dictionary variable for name, salary and name,points
#    for pos in w_solver.Position.unique():
#        available_pos = w_solver[w_solver.Position == pos]
#        salary = list(available_pos[["full_name","Salary"]].set_index("full_name").to_dict().values())[0]
#        point = list(available_pos[["full_name","x_dk_lazy"]].set_index("full_name").to_dict().values())[0]
#        salaries[pos] = salary
#        points[pos] = point

#        pos_num_available = {
#            "D": 2,
#            "W": 4,
#            "C": 2,
#            "G": 1
#        }

    # Sets the binary for the solver
#    _vars = {k: LpVariable.dict(k, v, cat="Binary") for k, v in points.items()}

#    prob = LpProblem("Fantasy", LpMaximize)
#    rewards = [] # total points
#    costs = [] # total salary
#    position_constraints = []

    # Setting up the optimal points lineup
#    for k, v in _vars.items():
#        costs += lpSum([salaries[k][i] * _vars[k][i] for i in v])
#        rewards += lpSum([points[k][i] * _vars[k][i] for i in v])
#        prob += lpSum([_vars[k][i] for i in v]) <= pos_num_available[k]

#    prob += lpSum(rewards)
#    prob += lpSum(costs) <= SALARY_CAP

#    def summary(prob):
#        div = '---------------------------------------\n'
#        print("Variables:\n")
#        score = str(prob.objective)
#        constraints = [str(const) for const in prob.constraints.values()]
#        for v in prob.variables():
#            score = score.replace(v.name, str(v.varValue))
#            constraints = [const.replace(v.name, str(v.varValue)) for const in constraints]
#            if v.varValue != 0:
#                print(v.name, "=", v.varValue)
#        print(div)
#        print("Constraints:")
#        for constraint in constraints:
#            constraint_pretty = " + ".join(re.findall("[0-9.]*\*1.0", constraint))
#            if constraint_pretty != "":
#                print("{} = {}".format(constraint_pretty, eval(constraint_pretty)))
#        print(div)
#        print("Score:")
#        score_pretty = " + ".join(re.findall("[0-9.]+\*1.0", score))
#        print("{} = {}".format(score_pretty, eval(score)))

#    prob.solve()
#    summary(prob)

    return f_skaters, f_goalies, f_games