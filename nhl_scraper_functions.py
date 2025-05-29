import random
import numpy as np
import requests
from bs4 import BeautifulSoup as soup
import re
import pandas as pd
import time

# example api link https://api-web.nhle.com/v1/gamecenter/2023020010/play-by-play

# Inputs for testing prior to creating function
#season = '20222023'
#gcode = '21253'

def scrape_single_game(season, gcode):

    # Inputs for testing prior to creating function
    #season = '20222023'
    #gcode = '21253'
    
    # Build pbp URL
    url = 'https://www.nhl.com/scores/htmlreports/' + season + '/' + 'PL0' + gcode + '.HTM'

    # Get request
    r_html = requests.get(url)

    # Build in redundancy for 403 errors
    while r_html.status_code == 403:
        print("403 error " + season + " " + gcode + " pausing 2 seconds and retrying")
        time.sleep(2)

        r_html = requests.get(url)

    # Parsing the HTML
    r_html_pbp = r_html.text

    # Clean the nonbreaking spaces
    r_html_pbp = re.sub("&nbsp;", ", ", r_html_pbp)

    # Remove line breaks
    # r_html_pbp = re.sub("\r\n", "", r_html_pbp)
    
    # Game metadata holders    
    season = season
    gcode = gcode

    # Capture Teams in game
    # Empty dictionary
    teams = {}
    pat_teams = re.compile(r'([A-Za-z]*) On Ice')
    teams = pat_teams.findall(r_html_pbp)
    team1 = teams[0]
    team2 = teams[1]

    # Pull home and away here as well just in case it's not always team1
    #<td align="center" style="font-size: 10px;font-weight:bold">NEW YORK RANGERS<br>Game 1 Away Game 1</td>
    venues = {}
    pat_venue = re.compile(r'<td align="center" style="font-size: 10px;font-weight:bold">([A-Z É]*)<br>Game [0-9]* ([A-Za-z]*) Game [0-9]*</td>')
    venues = pat_venue.findall(r_html_pbp)
    venues = pd.DataFrame(venues)
    venues = venues.rename(columns={venues.columns[0]: 'team_name'})
    venues = venues.rename(columns={venues.columns[1]: 'venue'})

    # Sort venues so Away is always row 0
    venues = venues.sort_values(by='venue', ascending=True)

    # Conditions and choices for teams
    conditions = [venues.team_name == "ANAHEIM DUCKS",
        venues.team_name == "ARIZONA COYOTES",
        venues.team_name == "BOSTON BRUINS",
        venues.team_name == "BUFFALO SABRES",
        venues.team_name == "CALGARY FLAMES",
        venues.team_name == "CAROLINA HURRICANES",
        venues.team_name == "CHICAGO BLACKHAWKS",
        venues.team_name == "COLORADO AVALANCHE",
        venues.team_name == "COLUMBUS BLUE JACKETS",
        venues.team_name == "DALLAS STARS",
        venues.team_name == "DETROIT RED WINGS",
        venues.team_name == "EDMONTON OILERS",
        venues.team_name == "FLORIDA PANTHERS",
        venues.team_name == "LOS ANGELES KINGS",
        venues.team_name == "MONTRÉAL CANADIENS",
        venues.team_name == "MONTREAL CANADIENS",
        venues.team_name == "MINNESOTA WILD",
        venues.team_name == "NASHVILLE PREDATORS",
        venues.team_name == "NEW JERSEY DEVILS",
        venues.team_name == "NEW YORK ISLANDERS",
        venues.team_name == "NEW YORK RANGERS",
        venues.team_name == "OTTAWA SENATORS",
        venues.team_name == "PHILADELPHIA FLYERS",
        venues.team_name == "PITTSBURGH PENGUINS",
        venues.team_name == "SAN JOSE SHARKS",
        venues.team_name == "SEATTLE KRAKEN",
        venues.team_name == "ST. LOUIS BLUES",
        venues.team_name == "TAMPA BAY LIGHTNING",
        venues.team_name == "TORONTO MAPLE LEAFS",
        venues.team_name == "VANCOUVER CANUCKS",
        venues.team_name == "VEGAS GOLDEN KNIGHTS",
        venues.team_name == "WASHINGTON CAPITALS",
        venues.team_name == "WINNIPEG JETS",
        venues.team_name == "UTAH HOCKEY CLUB"]
    choices = ["ANA", "ARI", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET", "EDM", "FLA", "LAK", "MTL", "MTL", "MIN", "NSH", "NJD", 
    "NYI", "NYR", "OTT", "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "VAN", "VGK", "WSH", "WPG", "UTA"]

    venues["Abbrev"] = np.select(conditions, choices, default = venues.team_name)
    venues = venues.drop_duplicates(subset="team_name")
    venues = venues.reset_index()

    away_team = venues._get_value(0, 'Abbrev')
    home_team = np.where(away_team == team1, team2, team1)

    del teams
    del pat_teams
    del pat_venue

    # Capture game date
    game_date = {}
    pat_gd = re.compile(r'<td align="center" style="font-size: 10px;font-weight:bold">[A-Za-z]*, ([A-Za-z0-9, ]*)</td>')
    game_date = pat_gd.findall(r_html_pbp)
    game_date = game_date[0]

    del pat_gd

    # Capture Venue need a comma after 'at' for 20232024 (and beyond?)
    # Adding an optional because some games don't have the venue in the pbp so the loop breaks
    venue = {}
    pat_venue = re.compile(r'.*Attendance [0-9, ]*at[, ]?([A-Za-z,:.0-9 -]*)</td>')
    venue = pat_venue.findall(r_html_pbp)

    if len(venue) > 0:
        venue = venue[0]
    else:
        venue = ""

    del pat_venue

    # THE BEHAVIOR OF CAPTURING MULTIPLE REGEX GROUPS IN ONE PATTERN IS SUUUUPER INTERESTING. CAN WE DO THIS ALL IN ONE SHOT?
    all_events = {}
    pat_all_events = re.compile(r'<tr id="(PL\-[0-9]*)" class="[a-z]*Color">\r\n<td align="center" class="[a-z]*? \+ bborder">([0-9]*)</td>\r\n<td class="[a-z]*? \+ bborder" align="center">([1-3])</td>\r\n<td class="[a-z]*? \+ bborder" align="center">([A-Za-z, ]*)</td>\r\n<td class="[a-z]*? \+ bborder" align="center">([0-9:]*)<br>([0-9:]*)</td>\r\n<td class="[a-z]*? \+ bborder" align="center">([A-Z]*)</td>\r\n<td class="[a-z]*? \+ bborder">(.*)</td>')
    all_events = pat_all_events.findall(r_html_pbp)

    # Start df build?
    r_pbp = pd.DataFrame(all_events, columns = ["play_id", "event_num", "period",
                                                "strength", "time_elapsed", "time_remaining",
                                                "event_type", "event_description"])

    # Remove line breaks so we can do (.*) without consequence in regex?
    r_html_pbp_nospace = re.sub("\r\n", "", r_html_pbp)

    # PL Number tag
    r_html_pbp_nospace = re.sub(r'<tr id="(PL\-[0-9]*)" class="[a-z]*Color">', r'e;\1', r_html_pbp_nospace)

    # Players
    # K'Andre Miller is messy (K\'ANDRE MILLER) Try to fix in future and make sure to change regex below '\\\''
    r_html_pbp_nospace = re.sub(r'<font style="cursor:hand;" title="([A-Za-z ]+) - ([A-Za-zÀ-ÖØ-öø-ÿ Ë.  \\\' -]*)">([0-9]+)', r'p;\1;\2;\3', r_html_pbp_nospace)

    # Bborder where the html shifts from on-ice team 1 to on-ice team 2
    r_html_pbp_nospace = re.sub(r'</td><td class="[a-z +]*? \+ bborder">', r'n;next_team', r_html_pbp_nospace)

    # PLs or Players or next team Identifer for on ice:
    simplified_pbp = {}
    pat_simplify = [r'e;PL\-[0-9]*', r'p;[A-Za-z ]*;[A-Za-zÀ-ÖØ-öø-ÿ Ë.  \\\' -]*;[0-9]+', r'n;next_team']
    pat_simplify_regex = re.compile('|'.join(pat_simplify))
    simplified_pbp = pat_simplify_regex.findall(r_html_pbp_nospace)

    # Make a dataframe so my brain can manipulate and comprehend?
    on_ice_df = pd.DataFrame(simplified_pbp)

    # Merge the event to on ice df so we can remove the anthem event
    anthem_merge = r_pbp[['play_id', 'event_type']]
    anthem_merge2 = anthem_merge.copy()
    anthem_merge2['play_id'] = 'e;' + anthem_merge2['play_id']

        
    # Helpful renaming col by index
    on_ice_df = on_ice_df.rename(columns={on_ice_df.columns[0]: 'initial_load'})

    on_ice_df =\
        on_ice_df\
            .merge(anthem_merge2,
               how='left',
               left_on="initial_load",
               right_on='play_id')

    # Fill down and remove anthem
    on_ice_df['event_type'] = on_ice_df['event_type'].ffill()
    on_ice_df =\
        on_ice_df\
        .query('event_type != "ANTHEM" & event_type != "PSTR"')

    # Remove helper column
    on_ice_df = on_ice_df.drop('event_type', axis=1)

    # New column where we'll run the PL IDs
    on_ice_df["PL"] = np.where(on_ice_df["initial_load"].str.contains('e;PL-'), on_ice_df["initial_load"], np.nan)

    # Fill the pl down
    on_ice_df["PL"] = on_ice_df["PL"].ffill()

    # Lag the initial load column so we can ID if a n;next_team follows a PL
    on_ice_df["id_lag"] = on_ice_df['initial_load'].shift(2)

    # Column of ones?
    on_ice_df["helper"] = np.where(on_ice_df['initial_load'].str.contains('p;'), 1, np.nan)

    # Is team 1 the away team?
    venue_helper = list(venues)
    if venues.iat[0,2] == team1: 
        venue_check = 1
    else:
        venue_check = 0

    # Count the players? Can we do it in one shot? This method STINKS and will add computational time...

    on_ice_df["b_check_one"] = np.where(on_ice_df['initial_load'].str.contains('p;'), 1, np.nan)
    on_ice_df["a_check_two"] = np.where(on_ice_df['id_lag'].str.contains('e;PL-'), 1, np.nan)

    on_ice_df["h_check_two"] = np.where(on_ice_df['initial_load'].shift(1) == "n;next_team", 1, np.nan)
    on_ice_df["h_check_three"] = np.where(on_ice_df['id_lag'].str.contains('p;'), 1, np.nan)

    # Conditions and values for ID'ing the first home or away skater for each PL-
    venue_conditions = [
        (on_ice_df["b_check_one"] == 1) & (on_ice_df["a_check_two"] == 1),
        (on_ice_df["b_check_one"] == 1) & (on_ice_df["h_check_two"] == 1) & (on_ice_df["h_check_three"] == 1)
    ]

    venue_choices = ['Away', 'Home']

    # apply to the df
    on_ice_df["venue_skater"] = np.select(venue_conditions, venue_choices, default=None)

    on_ice_df = on_ice_df[['initial_load', 'PL', 'venue_skater']]
    on_ice_df =\
        on_ice_df.query('initial_load != "n;next_team" & initial_load != PL')

    # Fill venue down
    on_ice_df["venue_skater"] = on_ice_df["venue_skater"].ffill()

    # Count by venue
    on_ice_df['player_count'] = on_ice_df.groupby(['PL', 'venue_skater']).cumcount()+1

    # Concatenate home or away ID on the counter
    on_ice_df["s_v_count"] = on_ice_df["venue_skater"] + on_ice_df["player_count"].astype(str)

    # Clean the DF
    on_ice_df = on_ice_df[['initial_load', 'PL', 's_v_count']]

    # Clean the columns
    on_ice_df['PL'] = on_ice_df['PL'].str.replace('e;', "")
    # Remove p; from the player name
    on_ice_df['initial_load'] = on_ice_df['initial_load'].str[2:]
    # Swap ; for spaces in the player name
    on_ice_df['initial_load'] = on_ice_df['initial_load'].str.replace(';', " ")

    # Transpose the skater venue count keeping the PL as columns and the initial load as rows
    on_ice_wide = on_ice_df.pivot(index=['PL'],columns="s_v_count", values="initial_load").sort_index(level=[1,0])
    on_ice_wide = on_ice_wide.rename(columns={on_ice_df.columns[0]: 'play_id'})

    # Merge to r_pbp
    r_pbp =\
        r_pbp\
        .merge(on_ice_wide,
               how='inner',
               left_on='play_id',
               right_on='PL')
    
    del on_ice_df
    del on_ice_wide

    # Id the home and away goalie if on ice during event. I don't want to do this col by col...
    mask = r_pbp.apply(lambda c: c.str.contains('Goalie '))

    r_pbp['AwayGoalie'] = r_pbp.where(mask).bfill(axis=1).iloc[:, 0]
    r_pbp['HomeGoalie'] = r_pbp.where(mask).bfill(axis=1).iloc[:, 14]

    # Remove goalies from the skater columns so it's easier to get count and strength
    skater_cols = ['Away1', 'Away2', 'Away3', 'Away4', 'Away5', 'Away6',
                   'Home1', 'Home2', 'Home3', 'Home4', 'Home5', 'Home6']
    away_cols = ['Away1', 'Away2', 'Away3', 'Away4', 'Away5', 'Away6']
    home_cols = ['Home1', 'Home2', 'Home3', 'Home4', 'Home5', 'Home6']
    r_pbp[skater_cols] = r_pbp[skater_cols].replace('Goalie .*', np.nan, regex=True)
    # r_pbp[skater_cols] = r_pbp[skater_cols].replace(np.nan, '', regex=True)

    # Count for each team
    # Need to remember axis = 1 is row wise operations
    r_pbp["away_skaters"] = 6-r_pbp[away_cols].isna().sum(axis=1)
    r_pbp["home_skaters"] = 6-r_pbp[home_cols].isna().sum(axis=1)

    # Begin regex cleaning for event types
    # s.str.extract(r'(?P<letter>[ab])(?P<digit>\d)') < regex into new columns

    # Eliminate shootouts from this logic
    r_pbp_no_shootout = r_pbp.copy()
    r_pbp_no_shootout = r_pbp_no_shootout[r_pbp_no_shootout['period'] != str(5)]

    # Shots
    # Example: BUF ONGOAL - #26 DAHLIN, Wrist , Off. Zone, 70 ft. 
    r_shots = r_pbp_no_shootout.copy()
    r_shots =\
        r_shots\
        .query("event_type == 'SHOT'")
    
    r_shots = r_shots[['play_id', 'event_description']]

    # Remove "Defensive Deflection, " from the string
    r_shots['event_description'] = r_shots['event_description'].str.replace(' Defensive Deflection,', '')

    # Make between legs one word
    r_shots['event_description'] = r_shots['event_description'].str.replace('Between Legs', 'BetweenLegs')
    r_shots['event_description'] = r_shots['event_description'].str.replace('Penalty Shot,', 'PenaltyShot')


    r_shots_expanded = r_shots.event_description.str.extract(r'(?P<ev_team>[A-Z]*) [A-Z]* - #(?P<ev_player_1>.*), (?P<shot_type>[A-z-]*)(?:[A-z ,]*) (?P<zone>[A-z]*).* (?P<distance>[0-9]+)', expand=True)

    # Concat as bind_cols?
    r_shots = \
        pd.concat([r_shots, r_shots_expanded], axis=1)

    # Factor columns
    r_shots["is_corsi"] = 1
    r_shots["is_fenwick"] = 1
    r_shots["is_shot"] = 1
    
    del r_shots_expanded

    # Blocks
    # Example: BUF #53 SKINNER OPPONENT-BLOCKED BY NYR #8 TROUBA, Wrist, Def. Zone 
    # Example: NYR #10 PANARIN BLOCKED BY TEAMMATE, Wrist, Off. Zone 
    r_blocks = r_pbp_no_shootout.copy()
    r_blocks =\
        r_blocks\
        .query("event_type == 'BLOCK'")
    
    r_blocks = r_blocks[['play_id', 'event_description']]

    # Make between legs one word
    r_blocks['event_description'] = r_blocks['event_description'].str.replace('Between Legs', 'BetweenLegs')

    # Split to opponent blocked and blocked by teammate and all others (Old(er) games don't feature this?)
    r_blocks_op = r_blocks[r_blocks['event_description'].str.contains('OPPONENT-BLOCKED')]
    r_blocks_tm = r_blocks[r_blocks['event_description'].str.contains('BLOCKED BY TEAMMATE')]
    r_blocks_other = r_blocks[~r_blocks['event_description'].str.contains('BLOCKED BY TEAMMATE|OPPONENT-BLOCKED')]

    # Input a delimiter on the blocked by teammate line items for regex ease
    r_blocks_tm['event_description'] = r_blocks_tm['event_description'].str.replace(' BLOCKED BY TEAMMATE', ', BLOCKED-BY-TEAMMATE')

    if len(r_blocks_op) > 0:
        r_blocks_op_expanded = r_blocks_op.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*) [A-Z]*-[A-Z ]*#(?P<ev_player_2>.*), (?P<shot_type>[A-z\\s-]*), (?P<zone>[A-z]*).', expand=True)
        r_blocks_op = \
            pd.concat([r_blocks_op, r_blocks_op_expanded], axis=1)

        del r_blocks_op_expanded
    
    else:
        pass

    if len(r_blocks_tm) > 0:
        r_blocks_tm_expanded = r_blocks_tm.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*),[A-Z ,-]*, (?P<shot_type>[A-z\\s-]*), (?P<zone>[A-z]*).')
        r_blocks_tm =\
            pd.concat([r_blocks_tm, r_blocks_tm_expanded], axis=1)
        
        del r_blocks_tm_expanded
    
    else:
        pass

    if len(r_blocks_other) > 0:
        r_blocks_other_expanded = r_blocks_other.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*) BLOCKED.*#(?P<ev_player_2>.*), (?P<shot_type>[A-z\\s-]*), (?P<zone>[A-z]*).')
        r_blocks_other =\
            pd.concat([r_blocks_other, r_blocks_other_expanded], axis=1)
        
        del r_blocks_other_expanded

    # Bind into one blocks df
    r_blocks = pd.concat([r_blocks_op, r_blocks_tm, r_blocks_other], ignore_index=True)

    r_blocks["is_corsi"] = 1



    # Testing behavior of merging dataframes with different columns
    #test_pbp_combined = pd.concat([r_shots, r_blocks], ignore_index=True)
    # Learned: behavior is NaN if a col exists in one but not the other
    #del test_pbp_combined

    # Faceoffs 
    # Example: NYR won Off. Zone - NYR #13 LAFRENIÈRE vs BUF #24 COZENS
    r_fo = r_pbp_no_shootout.copy()
    r_fo =\
        r_fo\
        .query("event_type == 'FAC'")

    r_fo = r_fo[['play_id', 'event_description']]

    r_fo_expanded = r_fo.event_description.str.extract(r'(?P<ev_team>[A-Z]*) won (?P<zone>[A-z]*). Zone - [A-Z]*? #(?P<ev_player_1>.*) vs .* #(?P<ev_player_2>.*)', expand=True)

    r_fo =\
        pd.concat([r_fo, r_fo_expanded], axis=1)

    del r_fo_expanded

    # Giveaways
    # Example: BUF, GIVEAWAY - #53 SKINNER, Off. Zone
    r_give = r_pbp_no_shootout.copy()

    r_give =\
        r_give\
        .query("event_type == 'GIVE'")

    r_give = r_give[['play_id', 'event_description']]

    r_give_expanded = r_give.event_description.str.extract(r'(?P<ev_team>[A-Z]*), GIVEAWAY - #(?P<ev_player_1>.*), (?P<zone>[A-z]*)..*', expand=True)

    r_give =\
        pd.concat([r_give, r_give_expanded], axis=1)

    r_give["is_give"] = 1

    del r_give_expanded

    # Goals
    # Example unassisted: NYR #10 PANARIN(1), Wrist , Off. Zone, 29 ft.
    # Example A1 (from different game): ANA #77 VATRANO(28), Wrist , Off. Zone, 18 ft.<br>Assist: #23 MCTAVISH(23) 
    # Example A2: NYR #13 LAFRENIÈRE(1), Wrist , Off. Zone, 10 ft.<br>Assists: #10 PANARIN(1); #72 CHYTIL(1) 

    # This is close but the optional isn't functioning the way I need it to
    # ([A-Z]*) #([0-9]*) (.*)\((?:[0-9)]*), ([A-z\\s-]*) , ([A-z]*). Zone, ([0-9]*) ft\.[<br>]?.*?(?:#(\d{1,2} .*))\((?:[0-9)]*).*(?:#(\d{1,2} .*))\((?:[0-9)]*)

    # Likely better to do this three times, when the goal event does not have 'Assist' when it has "Assists:" when it has "Assist:"

    # Can't figure out the optional capture for primary and secondary assists and have spent more time trying to than just typing out
    # the code for doing it three times so here we are

    r_goals = r_pbp_no_shootout.copy()

    r_goals =\
        r_goals\
        .query("event_type == 'GOAL'")
    
    r_goals = r_goals[['play_id', 'event_description']]

    # Kill 'defensive deflection'
    r_goals['event_description'] = r_goals['event_description'].str.replace(' Defensive Deflection,', '')

    # Make between legs one word
    r_goals['event_description'] = r_goals['event_description'].str.replace('Between Legs', 'BetweenLegs')

    # Remove the comma from Penalty Shots so the regex picks it up as shot type = Penalty Shot Wrist (for example)
    r_goals['event_description'] = r_goals['event_description'].str.replace('Penalty Shot,', 'Penalty Shot')

    # Trim any instance wehre there's a space before a comma
    r_goals['event_description'] = r_goals['event_description'].str.replace(' ,', ',')

    # Hold DFs?
    r_goals_unassisted = r_goals[~r_goals['event_description'].str.contains('Assist|Own Goal')]
    r_goals_own = r_goals[r_goals['event_description'].str.contains('Own Goal')]
    r_goals_primary = r_goals[r_goals['event_description'].str.contains('Assist:')]
    r_goals_secondary = r_goals[r_goals['event_description'].str.contains('Assists:')]

    # Check for unassisted goals and run:
    if len(r_goals_unassisted) > 0:
        r_goals_unassisted_expanded = r_goals_unassisted.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*)\((?:[0-9)]*), (?P<shot_type>[A-z -]*)[ ]?, (?P<zone>[A-z]*). Zone, (?P<distance>[0-9]*) ft\.')
        
        # 12/7/24 BUILD IN CONDITIONAL WHERE IF THE REGEX RETURNS NULLS TO ASSUME MISSING SHOT TYPE FROM DESCRIPTION AND RE-APPLY REGEX
        
        r_goals_unassisted =\
            pd.concat([r_goals_unassisted, r_goals_unassisted_expanded], axis=1)
        
        del r_goals_unassisted_expanded

        # Redundancy if regex fails, assume shot type was missing

        # Hold a DF of broken goals
        r_goals_missing_type = r_goals_unassisted[r_goals_unassisted.isna().any(axis=1)]
        if len(r_goals_missing_type) > 0:
            r_goals_missing_type_expanded = r_goals_missing_type.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*)\((?:[0-9)]*), (?P<zone>[A-z]*). Zone, (?P<distance>[0-9]*) ft\.')
            r_goals_missing_type = r_goals_missing_type.drop(columns=['ev_team', 'shot_type', 'ev_player_1', 'zone', 'distance'])
            r_goals_missing_type =\
                pd.concat([r_goals_missing_type, r_goals_missing_type_expanded], axis = 1)

            del r_goals_missing_type_expanded

            # Drop NAs from clean
            r_goals_unassisted = r_goals_unassisted.dropna(axis=0)

            # Reset indexes (I don't know why)
            r_goals_unassisted.reset_index(drop=True, inplace=True)
            r_goals_missing_type.reset_index(drop=True, inplace=True)

            # Concat in broken goals
            r_goals_unassisted =\
                pd.concat([r_goals_unassisted, r_goals_missing_type])

        else:
            pass   

    else:
        pass

    # Check for only primary assists and run:
    if len(r_goals_primary) > 0:
        r_goals_primary_expanded = r_goals_primary.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*)\((?:[0-9) ]*), (?P<shot_type>[A-z\\s-]*)[ ]?, (?P<zone>[A-z]*). Zone, (?P<distance>[0-9]*) ft\.<br>Assist: #(?P<ev_player_2>.*)\(')
        r_goals_primary =\
            pd.concat([r_goals_primary, r_goals_primary_expanded], axis=1)
        
        del r_goals_primary_expanded

        # Redundancy if regex fails, assume shot type was missing

        # Hold a DF of broken goals
        r_goals_missing_type = r_goals_primary[r_goals_primary.isna().any(axis=1)]
        if len(r_goals_missing_type) > 0:
            r_goals_missing_type_expanded = r_goals_missing_type.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*)\((?:[0-9) ]*), (?P<zone>[A-z]*). Zone, (?P<distance>[0-9]*) ft\.<br>Assist: #(?P<ev_player_2>.*)\(')
            r_goals_missing_type = r_goals_missing_type.drop(columns=['ev_team', 'shot_type', 'ev_player_1', 'zone', 'ev_player_2', 'distance'])
            r_goals_missing_type =\
                pd.concat([r_goals_missing_type, r_goals_missing_type_expanded], axis = 1)

            del r_goals_missing_type_expanded

            # Drop NAs from clean
            r_goals_primary = r_goals_primary.dropna(axis=0)

            # Reset indexes (I don't know why)
            r_goals_primary.reset_index(drop=True, inplace=True)
            r_goals_missing_type.reset_index(drop=True, inplace=True)

            # Concat in broken goals
            r_goals_primary =\
                pd.concat([r_goals_primary, r_goals_missing_type])

        else:
            pass    


    else:
        pass

    # Check for two assist goals and run:
        # Check for only primary assists and run:
    if len(r_goals_secondary) > 0:
        r_goals_secondary_expanded = r_goals_secondary.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*)\((?:[0-9) ]*), (?P<shot_type>[A-z\\s-]*)[ ]?, (?P<zone>[A-z]*). Zone, (?P<distance>[0-9]*) ft\.<br>Assists: #(?P<ev_player_2>.*)\([0-9\); ]* #(?P<ev_player_3>.*)\(')
        r_goals_secondary =\
            pd.concat([r_goals_secondary, r_goals_secondary_expanded], axis=1)
        
        del r_goals_secondary_expanded

        # Redundancy if regex fails, assume shot type was missing

        # Hold a DF of broken goals
        r_goals_missing_type = r_goals_secondary[r_goals_secondary.isna().any(axis=1)]
        if len(r_goals_missing_type) > 0:
            r_goals_missing_type_expanded = r_goals_missing_type.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*)\((?:[0-9) ]*), (?P<zone>[A-z]*). Zone, (?P<distance>[0-9]*) ft\.<br>Assists: #(?P<ev_player_2>.*)\([0-9\); ]* #(?P<ev_player_3>.*)\(')
            r_goals_missing_type = r_goals_missing_type.drop(columns=['ev_team', 'shot_type', 'ev_player_1', 'zone', 'ev_player_2', 'ev_player_3', 'distance'])
            r_goals_missing_type =\
                pd.concat([r_goals_missing_type, r_goals_missing_type_expanded], axis = 1)

            del r_goals_missing_type_expanded

            # Drop NAs from clean
            r_goals_secondary = r_goals_secondary.dropna(axis=0)

            # Reset indexes (I don't know why)
            r_goals_secondary.reset_index(drop=True, inplace=True)
            r_goals_missing_type.reset_index(drop=True, inplace=True)

            # Concat in broken goals
            r_goals_secondary =\
                pd.concat([r_goals_secondary, r_goals_missing_type])

        else:
            pass    


    else:
        pass

    # Check for own goals
    if len(r_goals_own) > 0:
        r_goals_own_expanded = r_goals_own.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*)\([0-9]*\), (?P<shot_type>[A-z\\s-]*)[ ]?, (?P<zone>[A-z]*). Zone, Own Goal, (?P<distance>[0-9]*) ft')
        r_goals_own =\
            pd.concat([r_goals_own, r_goals_own_expanded], axis=1)
        
        del r_goals_own_expanded

        # Redundancy if regex fails, assume shot type was missing

        # Hold a DF of broken goals
        r_goals_missing_type = r_goals_own[r_goals_own.isna().any(axis=1)]
        if len(r_goals_missing_type) > 0:
            r_goals_missing_type_expanded = r_goals_missing_type.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*)\([0-9]*\), (?P<zone>[A-z]*). Zone, Own Goal, (?P<distance>[0-9]*) ft')
            r_goals_missing_type = r_goals_missing_type.drop(columns=['ev_team', 'shot_type', 'ev_player_1', 'zone', 'distance'])
            r_goals_missing_type =\
                pd.concat([r_goals_missing_type, r_goals_missing_type_expanded], axis = 1)

            del r_goals_missing_type_expanded

            # Drop NAs from clean
            r_goals_own = r_goals_own.dropna(axis=0)

            # Reset indexes (I don't know why)
            r_goals_own.reset_index(drop=True, inplace=True)
            r_goals_missing_type.reset_index(drop=True, inplace=True)

            # Concat in broken goals
            r_goals_own =\
                pd.concat([r_goals_own, r_goals_missing_type])
        
        else:
            pass
    
    else:
        pass

    # Bind all goal dfs into one
    r_goals_combined = pd.concat([r_goals_unassisted, r_goals_primary, r_goals_secondary, r_goals_own], ignore_index=True)

    r_goals_combined["is_corsi"] = 1
    r_goals_combined["is_fenwick"] = 1
    r_goals_combined["is_shot"] = 1
    r_goals_combined["is_goal"] = 1

    del r_goals
    del r_goals_unassisted
    del r_goals_primary
    del r_goals_secondary

    # Hits
    # Example: BUF #6 JOHNSON HIT NYR #50 CUYLLE, Def. Zone
    r_hits = r_pbp_no_shootout.copy()
    r_hits =\
        r_hits\
        .query("event_type == 'HIT'")

    r_hits = r_hits[['play_id', 'event_description']]
    
    r_hits_expanded = r_hits.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*) HIT .*#(?P<ev_player_2>.*), (?P<zone>[A-z]*).', expand=True)

    r_hits = pd.concat([r_hits, r_hits_expanded], axis=1)

    del r_hits_expanded

    # Misses
    # Example: NYR #4 SCHNEIDER, Wrist, Wide Right, Off. Zone, 52 ft. 
    # Example: NSH #47 MCCARRON, Between Legs, Wide Right, Off. Zone, 9 ft. 

    r_miss = r_pbp_no_shootout.copy()
    r_miss =\
        r_miss\
        .query("event_type == 'MISS'")

    r_miss = r_miss[['play_id', 'event_description']]

    # Make between legs one word
    r_miss['event_description'] = r_miss['event_description'].str.replace('Between Legs', 'BetweenLegs')

    r_miss_expanded = r_miss.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*), (?P<shot_type>[A-z\\s-]*), (?P<miss_location>[A-z ]*), (?P<zone>[A-z]*)\. Zone, (?P<distance>[0-9]*) ', expand=True)

    r_miss = pd.concat([r_miss, r_miss_expanded], axis=1)
    r_miss["is_corsi"] = 1
    r_miss["is_fenwick"] = 1

    del r_miss_expanded

    # Penalties
    # Example drawn by player: BUF #12 GREENWAY, Cross-checking(2 min), Def. Zone Drawn By: NYR #20 KREIDER
    # Example delay of game minor: TOR #2 BENOIT, Delay Game - Puck over glass(2 min), Def. Zone
    # Example bench minor: BOS TEAM, Too many men/ice - bench(2 min) Served By: #11 FREDERIC, Neu. Zone
    # Example game misconduct: NYR #4 SCHNEIDER, Misconduct(10 min), Def. Zone

    r_pen = r_pbp_no_shootout.copy()
    r_pen =\
        r_pen\
        .query("event_type == 'PENL'")
    
    r_pen = r_pen[['play_id', 'event_description']]

    # Mimic goals and do some if checks so the loop doesn't error out
    r_pen_drawn = r_pen[r_pen['event_description'].str.contains('Drawn By:')]
    r_pen_delay = r_pen[r_pen['event_description'].str.contains('Delay Game')]
    r_pen_bench = r_pen[r_pen['event_description'].str.contains('bench')]
    r_pen_misconduct = r_pen[~r_pen['event_description'].str.contains('Drawn By:|Delay Game|bench')]


    # Check for drawn by penalties
    if len(r_pen_drawn) > 0:
        r_pen_drawn_expanded = r_pen_drawn.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*), (?P<penl_type>.*)\((?P<penl_length>[0-9]*) [A-z]*\).*, (?P<zone>[A-z]*).*#(?P<ev_player_2>.*)', expand=True)
        r_pen_drawn =\
            pd.concat([r_pen_drawn, r_pen_drawn_expanded], axis=1)
        
        del r_pen_drawn_expanded

    else:
        pass
    
    # Delay of games
    if len(r_pen_delay) > 0:
        r_pen_delay_expanded = r_pen_delay.event_description.str.extract(r'(?P<ev_team>[A-Z]*) [#]?(?P<ev_player_1>.*), (?P<penl_type>[A-z -]*)\((?P<penl_length>[0-9]*) [A-z]*\).*, (?P<zone>[A-z]*).', expand=True)
        r_pen_delay =\
            pd.concat([r_pen_delay, r_pen_delay_expanded], axis=1)
        
        del r_pen_delay_expanded
    
    else:
        pass

    # Bench minors
    if len(r_pen_bench) > 0:
        r_pen_bench_expanded = r_pen_bench.event_description.str.extract(r'(?P<ev_team>[A-Z]*) TEAM, (?P<penl_type>.*) - bench\((?P<penl_length>[0-9]*).*#(?P<ev_player_1>.*), (?P<zone>[A-z]*).', expand=True)
        r_pen_bench =\
            pd.concat([r_pen_bench, r_pen_bench_expanded], axis=1)
        
        del r_pen_bench_expanded
    
    else:
        pass

    # Misconducts
    if len(r_pen_misconduct) > 0:
        r_pen_misconduct_expanded = r_pen_misconduct.event_description.str.extract(r'(?P<ev_team>[A-Z]*) #(?P<ev_player_1>.*), (?P<penl_type>[A-z -]*)\((?P<penl_length>[0-9]*).*, (?P<zone>[A-z]*).', expand=True)
        r_pen_misconduct =\
            pd.concat([r_pen_misconduct, r_pen_misconduct_expanded], axis=1)

        del r_pen_misconduct_expanded
    
    else:
        pass

    # Bind all penalty dfs into one
    r_pen = pd.concat([r_pen_drawn, r_pen_delay, r_pen_bench, r_pen_misconduct], ignore_index=True)

    # Takeaways
    # Example: BUF, TAKEAWAY - #10 JOKIHARJU, Def. Zone

    r_take = r_pbp_no_shootout.copy()
    r_take =\
        r_take\
        .query("event_type == 'TAKE'")
    
    r_take = r_take[['play_id', 'event_description']]

    r_take_expanded = r_take.event_description.str.extract(r'(?P<ev_team>[A-Z]*).*#(?P<ev_player_1>.*), (?P<zone>[A-z]*).', expand=True)

    r_take = pd.concat([r_take, r_take_expanded], axis=1)

    del r_take_expanded

    # Events dataframe to re-merge back to the pbp
    events_merge = pd.concat([r_shots, r_blocks, r_fo, r_give, r_goals_combined, r_hits, r_miss, r_pen, r_take], ignore_index=True)
    del events_merge['event_description']

    # Merge to r_pbp on the play id
    r_pbp_merged =\
        r_pbp\
        .merge(events_merge,
               how='left',
               left_on='play_id',
               right_on='play_id')

    del [r_shots, r_blocks, r_fo, r_give, r_goals_combined, r_hits, r_miss, r_pen, r_take, events_merge, mask, r_pbp, r_pbp_no_shootout,
        r_pen_bench, r_pen_delay, r_pen_drawn, r_pen_misconduct]

    # Throw in home and away abbreviations for ev_team analysis
    # w_ = working

    w_pbp = r_pbp_merged.copy()
    w_pbp["away_team"] = away_team
    w_pbp["home_team"] = home_team

    # Time manipulation from mm:ss to total seconds (stolen from SO)
    def get_sec(time_str):
        m, s = time_str.split(':')
        return int(m) * 60 + int(s)

    w_pbp['seconds_elapsed'] = w_pbp.time_elapsed.apply(get_sec)
    w_pbp['seconds_remaining'] = w_pbp.time_remaining.apply(get_sec)

    # Time since last event
    w_pbp['time_since'] = w_pbp['seconds_elapsed'] - w_pbp['seconds_elapsed'].shift(1)

    # Previous event
    w_pbp['prev_event'] = w_pbp['event_type'].shift(1)

    # Skater strength based on event team
    w_pbp['skater_strength'] = np.where(
            w_pbp['ev_team'] == w_pbp['away_team'],
            w_pbp['away_skaters'].map(str) + 'v' + w_pbp['home_skaters'].map(str),
            w_pbp['home_skaters'].map(str) + 'v' + w_pbp['away_skaters'].map(str)
    )

    # Strength classifications
    # EV "5v5", "4v4", "3v3", "5v6", "6v5"
    # SH "4v5", "3v5", "4v6", "3v4", "3v6"
    # PP "5v4", "5v3", "4v3", "6v4", "6v3"

    # Update logic after this for empty net attempts

    strength_conditions = (w_pbp['skater_strength'] == "5v5",
                           w_pbp['skater_strength'] == "4v4",
                           w_pbp['skater_strength'] == "3v3",
                           w_pbp['skater_strength'] == "5v6",
                           w_pbp['skater_strength'] == "6v5",

                           w_pbp['skater_strength'] == "4v5",
                           w_pbp['skater_strength'] == "3v5",
                           w_pbp['skater_strength'] == "4v6",
                           w_pbp['skater_strength'] == "3v4",
                           w_pbp['skater_strength'] == "3v6",
                           
                           w_pbp['skater_strength'] == "5v4",
                           w_pbp['skater_strength'] == "5v3",
                           w_pbp['skater_strength'] == "4v3",
                           w_pbp['skater_strength'] == "6v4",
                           w_pbp['skater_strength'] == "6v3")

    strength_choices = ['EV', 'EV', 'EV', 'EV', 'EV',
                        'SH', 'SH', 'SH', 'SH', 'SH',
                        'PP', 'PP', 'PP', 'PP', 'PP']

    w_pbp['strength_cat'] = np.select(strength_conditions, strength_choices, default='junk')

    w_pbp["season"] = season
    w_pbp["game_id"] = gcode
    w_pbp["game_date"] = game_date

    print("finishing game " + season + " " + gcode + " pausing 2 seconds")
    time.sleep(2)

    return w_pbp

def scrape_game_summary(season, gcode):

    # Gets us: Goalie TOI, Team TOI, Power Plays

    # Inputs for testing prior to creating function
    #season = '20212022'
    #gcode = '20004'
    
    # Build pbp URL
    url = 'https://www.nhl.com/scores/htmlreports/' + season + '/' + 'GS0' + gcode + '.HTM'

    # Get request
    r_html = requests.get(url)

    # Build in redundancy for 403 errors
    while r_html.status_code == 403:
        print("403 error " + season + " " + gcode + " pausing 2 seconds and retrying")
        time.sleep(2)

        r_html = requests.get(url)

    # Parsing the HTML
    r_html_gs = r_html.text

    # Clean the nonbreaking spaces
    r_html_gs = re.sub("&nbsp;", ", ", r_html_gs)
    r_html_gs = re.sub("\\t", "", r_html_gs)
    r_html_gs = re.sub("\\r", "", r_html_gs)

    # Remove line breaks
    # r_html_pbp = re.sub("\r\n", "", r_html_pbp)
    
    # Game metadata holders    
    season = season
    gcode = gcode

    # Grab team headers
    away_team = {}
    pat_away = re.compile(r'visitorsectionheading">(.*)</td>')
    away_team = pat_away.findall(r_html_gs)
    away_team = away_team[0]

    home_team = {}
    pat_home = re.compile(r'homesectionheading">(.*)</td>')
    home_team = pat_home.findall(r_html_gs)
    home_team = home_team[0]

    del pat_away
    del pat_home

    # Power plays
    powerplays = {}
    pat_powerplays = re.compile(r'<td align="center">([0-9\/\: ,-]*)</td>\n<td align="center">([0-9\/\: ,-]*)</td>\n<td align="center">([0-9\/\: ,-]*)</td>\n<td align="center">([0-9\/\: ,-]*)</td>')
    powerplays = pat_powerplays.findall(r_html_gs)

    r_gs = pd.DataFrame(powerplays, columns = ["5v4", "5v3", "4v3", "delete"])

    del pat_powerplays

    # Apply the team to the power play df
    r_gs["team_name"] = ""
    r_gs.loc[0, "team_name"] = away_team
    r_gs.loc[1, "team_name"] = home_team

    # Conditions and choices for teams
    # Conditions and choices for teams
    conditions = [r_gs.team_name == "ANAHEIM DUCKS",
        r_gs.team_name == "ARIZONA COYOTES",
        r_gs.team_name == "BOSTON BRUINS",
        r_gs.team_name == "BUFFALO SABRES",
        r_gs.team_name == "CALGARY FLAMES",
        r_gs.team_name == "CAROLINA HURRICANES",
        r_gs.team_name == "CHICAGO BLACKHAWKS",
        r_gs.team_name == "COLORADO AVALANCHE",
        r_gs.team_name == "COLUMBUS BLUE JACKETS",
        r_gs.team_name == "DALLAS STARS",
        r_gs.team_name == "DETROIT RED WINGS",
        r_gs.team_name == "EDMONTON OILERS",
        r_gs.team_name == "FLORIDA PANTHERS",
        r_gs.team_name == "LOS ANGELES KINGS",
        r_gs.team_name == "MONTRÉAL CANADIENS",
        r_gs.team_name == "MINNESOTA WILD",
        r_gs.team_name == "NASHVILLE PREDATORS",
        r_gs.team_name == "NEW JERSEY DEVILS",
        r_gs.team_name == "NEW YORK ISLANDERS",
        r_gs.team_name == "NEW YORK RANGERS",
        r_gs.team_name == "OTTAWA SENATORS",
        r_gs.team_name == "PHILADELPHIA FLYERS",
        r_gs.team_name == "PITTSBURGH PENGUINS",
        r_gs.team_name == "SAN JOSE SHARKS",
        r_gs.team_name == "SEATTLE KRAKEN",
        r_gs.team_name == "ST. LOUIS BLUES",
        r_gs.team_name == "TAMPA BAY LIGHTNING",
        r_gs.team_name == "TORONTO MAPLE LEAFS",
        r_gs.team_name == "VANCOUVER CANUCKS",
        r_gs.team_name == "VEGAS GOLDEN KNIGHTS",
        r_gs.team_name == "WASHINGTON CAPITALS",
        r_gs.team_name == "WINNIPEG JETS",
        r_gs.team_name == "UTAH HOCKEY CLUB"]
    choices = ["ANA", "ARI", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET", "EDM", "FLA", "LAK", "MTL", "MIN", "NSH", "NJD", 
    "NYI", "NYR", "OTT", "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "VAN", "VGK", "WSH", "WPG", "UTA"]

    r_gs["Abbrev"] = np.select(conditions, choices, default = r_gs.team_name)

    # Team TOI totals by EV, PP, SH, TOT
    team_toi = {}
    pat_team_toi = re.compile(r'TEAM TOTALS, </td>\n<td align="center" class="bborder \+ rborder">([0-9\:]*)</td>\n<td align="center" class="bborder \+ rborder">([0-9\:]*)</td>\n<td align="center" class="bborder \+ rborder">([0-9\:]*)</td>\n<td align="center" class="bborder \+ rborder">([0-9\:]*)</td>')
    team_toi = pat_team_toi.findall(r_html_gs)
    team_toi = pd.DataFrame(team_toi, columns = ["EV", "PP", "SH", "TOT"])

    # Concat to r_gs
    r_gs = pd.concat([r_gs, team_toi], axis=1)

    # Change , to a /: so the splits work universally
    r_gs['5v4'] = r_gs['5v4'].replace(', ', '0-0/00:00')
    r_gs['5v3'] = r_gs['5v3'].replace(', ', '0-0/00:00')
    r_gs['4v3'] = r_gs['4v3'].replace(', ', '0-0/00:00')

    # Split the PPs
    r_gs[['5v4_perf', 'fivevfourtime']] = r_gs['5v4'].str.split('/', expand=True) 
    r_gs[['5v3_perf', 'fivevthreetime']] = r_gs['5v3'].str.split('/', expand=True)
    r_gs[['4v3_perf', 'fourvthreetime']] = r_gs['4v3'].str.split('/', expand=True)

    # Attempts and goals
    r_gs[['5v4_goals', '5v4_attempts']] = r_gs['5v4_perf'].str.split('-', expand=True)
    r_gs[['5v3_goals', '5v3_attempts']] = r_gs['5v3_perf'].str.split('-', expand=True)
    r_gs[['4v3_goals', '4v3_attempts']] = r_gs['4v3_perf'].str.split('-', expand=True)

    # Time by PP opportunity
    def get_sec(time_str):
        m, s = time_str.split(':')
        return int(m) * 60 + int(s)

    r_gs['ev_toi'] = r_gs.EV.apply(get_sec)
    r_gs['pp_toi'] = r_gs.PP.apply(get_sec)
    r_gs['sh_toi'] = r_gs.SH.apply(get_sec)
    r_gs['tot_toi'] = r_gs.TOT.apply(get_sec)

    r_gs['fivevfour_time'] = r_gs.fivevfourtime.apply(get_sec)
    r_gs['fivevthree_time'] = r_gs.fivevthreetime.apply(get_sec)
    r_gs['fourvthree_time'] = r_gs.fourvthreetime.apply(get_sec)

    # Finalize DF
    f_gs = r_gs[['team_name', 'Abbrev', 'ev_toi', 'pp_toi', 'sh_toi', 'tot_toi', 
                 'fivevfour_time', 'fivevthree_time', 'fourvthree_time',
                 '5v4_goals', '5v4_attempts', '5v3_goals', '5v3_attempts',
                 '4v3_goals', '4v3_attempts']]

    # Make some cols integers that we lost along the way
    f_gs =\
        f_gs\
        .astype({
            "5v4_goals": int,
            "5v4_attempts": int,
            "5v3_goals": int,
            "5v3_attempts": int,
            "4v3_goals": int,
            "4v3_attempts": int
        })
    
    f_gs['season'] = season
    f_gs['gcode'] = gcode


    # BEGIN GOALIE TOI FROM GAME SUMMARY
    # I'm gonna beautiful soup this part after learning it a bit on the ES function

    # Parse the HTML content using BeautifulSoup
    soup_goalies = soup(r_html.content, 'html.parser')

    # Find all tables in the HTML
    tables = soup_goalies.find_all('table')

    # Locate the goalie table
    goalie_table = None
    for i, table in enumerate(tables):
        # Extract table headers
        headers = [table.find_all('td')[0]]
        headers = str(headers)
        table_html = str(table)

        # Check for the visitor heading to signify the table
        if 'visitorsectionheading' in headers:
            player_table = table
            break
    
    if player_table is None:
        raise ValueError("Can't find the goalie table")

    # Find teams in game
    away = player_table.find_all('td', class_='lborder + rborder + bborder + visitorsectionheading')
    away = [away[0].get_text(strip=True)]
    away = away[0]

    home = player_table.find_all('td', class_='lborder + rborder + bborder + homesectionheading')
    home = [home[0].get_text(strip=True)]
    home = home[0]


    # Parse the table rows
    rows = []
    for row in player_table.find_all('tr')[0:]:  # Skip the header row
        cols = row.find_all('td')
        cols = [col.get_text(strip=True) for col in cols]
        if len(cols) > 1:  # Ensure row has data
            rows.append(cols)

    # Create a DataFrame
    df = pd.DataFrame(rows)

    # Jackhammer logic to split teams
    df["team_split"] = np.where(df.loc[:,0]=="TEAM TOTALS",1,np.nan)
    df["team_split"] = df["team_split"].ffill()

    # Apply full team name
    df["team"] = np.where(df['team_split'] == 1, home, away)

    # Build player name to match ev player 1 [# LAST]
    df[['last', 'first']] = df[2].str.split(', ', expand=True)

    # Remove winner and loser from name
    df['first'] = df['first'].str.replace(' (W)', '')
    df['first'] = df['first'].str.replace(' (L)', '')
    df['first'] = df['first'].str.replace(' (OT)', '')
    df['ev_player_1'] = df[0] + ' ' + df['last']
    df['full_name'] = df['first'] + ' ' + df['last'] + ' ' + df[0]

    # Keep goalie columns by forcing the number column to numeric
    df = df[pd.to_numeric(df[0], errors='coerce').notnull()]

    # Rename columns we like:
    col_dict = {3: 'ev', 4: 'pp', 5: 'sh', 6: 'tot'}
    df = df.rename(col_dict, axis=1)

    # Remove goalies with no TOI
    w_goalies = df.copy()
    w_goalies =\
        w_goalies\
        .query('tot != ""')

    # Convert mm:ss to seconds
    def get_sec(time_str):
        m, s = time_str.split(':')
        return int(m) * 60 + int(s)

    w_goalies['ev_toi'] = w_goalies.ev.apply(get_sec)
    w_goalies['pp_toi'] = w_goalies.pp.apply(get_sec)
    w_goalies['sh_toi'] = w_goalies.sh.apply(get_sec)
    w_goalies['tot_toi'] = w_goalies.tot.apply(get_sec)

    # Set df to final cols
    f_goalies = w_goalies.copy()
    f_goalies = f_goalies[['team', 'full_name', 'ev_player_1', 'ev_toi', 'pp_toi', 'sh_toi', 'tot_toi']]
    f_goalies['season'] = season
    f_goalies['gcode'] = gcode

    print("finishing game " + season + " " + gcode + " pausing 2 seconds")
    time.sleep(2)

    return f_goalies, f_gs


import requests
from bs4 import BeautifulSoup
import pandas as pd

# This was built by AI and edited by me, learn learn learn
def scrape_event_summary(season, gcode):

    # Define the URL
    url = url = 'https://www.nhl.com/scores/htmlreports/' + season + '/' + 'ES0' + gcode + '.HTM'

    # Send a request to fetch the HTML content
    response = requests.get(url)

    # Build in redundancy for 403 errors
    while response.status_code == 403:
        print("403 error " + season + " " + gcode + " pausing 2 seconds and retrying")
        time.sleep(2)

        response = requests.get(url)

    response.raise_for_status()  # Check for request errors

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all tables in the HTML
    tables = soup.find_all('table')

    # Locate the table by inspecting its content
    player_table = None
    for i, table in enumerate(tables):
        # Extract the table headers
        headers = [table.find_all('td')[0]]
        headers = str(headers)
        table_html = str(table)

        # Check if headers contain 'Player' and 'TOI'
        if 'visitorsectionheading' in headers:
            player_table = table
            break

    if player_table is None:
        raise ValueError('Player statistics table not found.')

    # Find teams in game
    away = player_table.find_all('td', class_='lborder + rborder + bborder + visitorsectionheading')
    away = [away[0].get_text(strip=True)]
    away = away[0]

    home = player_table.find_all('td', class_='lborder + rborder + bborder + homesectionheading')
    home = [home[0].get_text(strip=True)]
    home = home[0]


    # Parse the table rows
    rows = []
    for row in player_table.find_all('tr')[0:]:  # Skip the header row
        cols = row.find_all('td')
        cols = [col.get_text(strip=True) for col in cols]
        if len(cols) > 1:  # Ensure row has data
            rows.append(cols)

    # Create a DataFrame
    df = pd.DataFrame(rows)

    # Dataframe cleansing
    w_p_toi = df.loc[:, 0:14] # Remove many unneeded columns

    # Rename columns we like:
    col_dict = {2: 'player', 9: 'TOT', 10: 'SHF', 11: 'AVG', 12: 'PP', 13: 'SH', 14: 'EV'}
    w_p_toi = w_p_toi.rename(col_dict, axis=1)

    # Jackhammer logic to split teams
    w_p_toi["team_split"] = np.where(w_p_toi.loc[:,0]=="TEAM TOTALS",1,np.nan)
    w_p_toi["team_split"] = w_p_toi["team_split"].ffill()

    # Remove middle cols
    w_p_toi = w_p_toi.drop([3, 4, 5, 6, 7, 8], axis=1)

    # Build player name to match ev player 1 [# LAST]
    w_p_toi[['last', 'first']] = w_p_toi['player'].str.split(', ', expand=True)
    w_p_toi['ev_player_1'] = w_p_toi[0] + ' ' + w_p_toi['last']
    w_p_toi['full_name'] = w_p_toi['first'] + ' ' + w_p_toi['last'] + ' ' + w_p_toi[0]

    # Another df clean up
    w_p_toi = w_p_toi.drop([0, 1, 'player', 'AVG', 'last', 'first'], axis=1)

    # Apply full team name
    w_p_toi["team"] = np.where(w_p_toi['team_split'] == 1, home, away)

    # Remove non skaters (THIS IS VERY COOL)
    w_p_toi = w_p_toi[pd.to_numeric(w_p_toi['SHF'], errors='coerce').notnull()]

    # Calculate TOI in seconds
    def get_sec(time_str):
        m, s = time_str.split(':')
        return int(m) * 60 + int(s)

    w_p_toi['ev_time'] = w_p_toi.EV.apply(get_sec)
    w_p_toi['sh_time'] = w_p_toi.SH.apply(get_sec)
    w_p_toi['pp_time'] = w_p_toi.PP.apply(get_sec)
    w_p_toi['tot_time'] = w_p_toi.TOT.apply(get_sec)

    # Last col drop, finish DF
    f_p_toi = w_p_toi[['team', 'ev_player_1', 'full_name', 'ev_time', 'pp_time', 'sh_time', 'tot_time']]
    f_p_toi['season'] = season
    f_p_toi['gcode'] = gcode

    print("finishing game " + season + " " + gcode + " pausing 2 seconds")
    time.sleep(2)
    
    return f_p_toi

def scrape_api_players(season, gcode):

    # Inputs for testing prior to creating function
    #season = '20232024'
    #gcode = '20009'

    season_clean = season[:4]

    # Build API URL
    # Example: https://api-web.nhle.com/v1/gamecenter/2023020010/play-by-play
    url = "https://api-web.nhle.com/v1/gamecenter/" + season_clean + "0" + gcode + "/play-by-play"

    # Send a request to fetch the content
    response = requests.get(url)

    # Build in redundancy for errors
    while response.status_code != 200:
        print("Scrape error " + season + " " + gcode + " pausing 2 seconds and retrying")
        time.sleep(2)

        response = requests.get(url)

    response.raise_for_status()  # Check for request errors

    # Built in json parser?
    r_api_pull = response.json()

    # Grind through the rosters attributes to get num, first, last, player ID
    rosters = r_api_pull["rosterSpots"]
    player_df = pd.DataFrame(rosters)

    # Capture the player name values in "default" for first and last name
    player_df['firstName'] = player_df['firstName'].astype(str)
    player_df['lastName'] = player_df['lastName'].astype(str)

    # On the chance the entire column only features 'default' names
    # We're going to replace the } with a , so the split below doesn't fail
    player_df['firstName'] = player_df['firstName'].str.replace('}', ', NONSENSE')
    player_df['lastName'] = player_df['lastName'].str.replace('}', ', NONSENSE')

    # Splitting the string in first and last name so it's just the "default" value
    player_df[['default_first', 'extra_languages']] = player_df['firstName'].str.split(', ', n = 1, expand=True)
    player_df[['default_last', 'extra_languages']] = player_df['lastName'].str.split(', ', n = 1, expand=True)

    player_df['first_name'] = player_df['default_first'].str.extract(r'{\'default\':\s*[\'"](.*)[\'"]', expand=True)
    player_df['last_name'] = player_df['default_last'].str.extract(r'{\'default\':\s*[\'"](.*)[\'"]', expand=True)

    # Extract team abbrev from Headshot .*\/([A-Z]*)\/[0-9]*
    player_df['team_abbrev'] = player_df['headshot'].str.extract(r'.*\/([A-Z]*)\/[0-9]*', expand=True)

    # Keep relevant cols and apply metadata
    player_df = player_df[['team_abbrev', 'playerId', 'sweaterNumber', 'positionCode', 'first_name', 'last_name']]

    # Mimic ev_player_1
    player_df['ev_player_1'] = player_df['sweaterNumber'].astype(str) + ' ' + player_df['last_name'].str.upper()

    player_df['season'] = season
    player_df['game_id'] = gcode

    print("finishing game " + season + " " + gcode + " pausing 2 seconds")
    time.sleep(2)
    
    return player_df

def scrape_schedule(slate_day):

    # One time test
    #slate_day = "2024-10-16"

    # Example URL: https://api-web.nhle.com/v1/schedule/2024-10-14

    # Build URL
    s_url = "https://api-web.nhle.com/v1/schedule/" + slate_day

     # Send a request to fetch the content
    response = requests.get(s_url)

    # Build in redundancy for errors
    while response.status_code != 200:
        print("Scrape error " + slate_day + " pausing 2 seconds and retrying")
        time.sleep(2)

        response = requests.get(s_url)

    response.raise_for_status()  # Check for request errors

    # Built in json parser?
    r_api_schedule = response.json()

    w_schedule = r_api_schedule["gameWeek"]
    w_schedule = w_schedule[0] # What happens here if there are no games that day? Only an issue with a lazy long scrpe rather than daily?
    w_schedule = w_schedule["games"]
    w_schedule = pd.DataFrame(w_schedule)

    # Make sure the game is regular season
    w_schedule['id'] = w_schedule['id'].astype(str)
    w_schedule = w_schedule[w_schedule['id'].str.startswith('202402')]

    # Remove cancelled games
    w_schedule =\
        w_schedule \
        .query("gameScheduleState != 'CNCL'")

    # Parse home and away abbreviations
    w_schedule['awayTeam'] = w_schedule['awayTeam'].astype(str)
    w_schedule['homeTeam'] = w_schedule['homeTeam'].astype(str)

    w_schedule['away_abbrev'] = w_schedule['awayTeam'].str.extract(r'\'abbrev\':\s*[\'"](.*)[\'"], \'logo', expand=True)
    w_schedule['home_abbrev'] = w_schedule['homeTeam'].str.extract(r'\'abbrev\':\s*[\'"](.*)[\'"], \'logo', expand=True)

    # Pull relevant cols
    f_schedule = w_schedule.copy()
    f_schedule = f_schedule[['id', 'away_abbrev', 'home_abbrev']]

    # Parse gcode from id
    pattern = r'20240'
    f_schedule['game_id'] = f_schedule['id'].str.replace(pattern, '', regex=True)

    # Remove 'id' column and add date
    f_schedule = f_schedule.drop(['id'], axis=1)
    f_schedule['game_date'] = slate_day

    return f_schedule

def scrape_schedule_vegas(slate_day):

    # One time test
    #slate_day = "2024-12-22"

    # Example URL: https://api-web.nhle.com/v1/schedule/2024-10-14

    # Build URL
    s_url = "https://api-web.nhle.com/v1/schedule/" + slate_day

     # Send a request to fetch the content
    response = requests.get(s_url)

    # Build in redundancy for errors
    while response.status_code != 200:
        print("Scrape error " + slate_day + " pausing 2 seconds and retrying")
        time.sleep(2)

        response = requests.get(s_url)

    response.raise_for_status()  # Check for request errors

    # Built in json parser?
    r_api_schedule = response.json()

    w_schedule = r_api_schedule["gameWeek"]
    w_schedule = w_schedule[0] # What happens here if there are no games that day? Only an issue with a lazy long scrpe rather than daily?
    w_schedule = w_schedule["games"]
    w_schedule = pd.DataFrame(w_schedule)

    # Make sure the game is regular season
    w_schedule['id'] = w_schedule['id'].astype(str)
    w_schedule = w_schedule[w_schedule['id'].str.startswith('202402')]

    # Remove cancelled, finished, and live games
    w_schedule =\
        w_schedule \
        .query("gameScheduleState != 'CNCL' & gameState != 'LIVE' & gameState != 'OFF' and gameState != 'FINAL'")

    # Parse home and away abbreviations
    w_schedule['awayTeam'] = w_schedule['awayTeam'].astype(str)
    w_schedule['homeTeam'] = w_schedule['homeTeam'].astype(str)

    w_schedule['away_abbrev'] = w_schedule['awayTeam'].str.extract(r'\'abbrev\':\s*[\'"](.*)[\'"], \'logo', expand=True)
    w_schedule['home_abbrev'] = w_schedule['homeTeam'].str.extract(r'\'abbrev\':\s*[\'"](.*)[\'"], \'logo', expand=True)

    # Pull provider 9 (I think this is DK) odds from the home and away team cols
    w_schedule['away_ml'] = w_schedule['awayTeam'].str.extract(r"providerId': 9, 'value': '([+-]?\d+)", expand=True)
    w_schedule['home_ml'] = w_schedule['homeTeam'].str.extract(r"providerId': 9, 'value': '([+-]?\d+)", expand=True)

    # Shape to a team column and an odds column (lazy version)
    f_odds_h = w_schedule[['home_abbrev', 'home_ml']]
    f_odds_h.rename(columns={'home_abbrev':'Abbrev', 'home_ml':'ml'}, inplace=True)

    f_odds_a = w_schedule[['away_abbrev', 'away_ml']]
    f_odds_a.rename(columns={'away_abbrev':'Abbrev', 'away_ml':'ml'}, inplace=True)

    # Concat
    f_odds = pd.concat([f_odds_h, f_odds_a])

    # Strings to integers
    f_odds['ml'] = f_odds['ml'].astype(int)

    # ML to probability
    # "pays +X" (moneyline odds) means that the bet is fair if the probability is p = 100 / (X + 100). "pays −X" (moneyline odds) means that the bet is fair if the probability is p = X / (X + 100).

    f_odds['w_probability'] = np.where(f_odds['ml'] > 100, 100/(f_odds['ml']+100), abs(f_odds['ml']) / (abs(f_odds['ml'])+100))
    f_odds = f_odds[['Abbrev', 'w_probability']]

    return f_odds
