# nhl_python

Python NHL PBP and Daily Fantasy Scripts

#dfs_cleaning_functions 

- builds the function clean_skater_model which returns clean dataframes of skaters and goalies for daily fantasy sports projection purposes

#nhl_scraper_functions

contains 6 functions, all of which can be used alone or in conjunction with the DFS cleaning functions

- scrape_single_game(season, gcode): returns a clean dataframe manipulating the public NHL play-by-play data. Mostly ripped and converted from the public nhlscrapr package that's now running the Carolina Hurricanes
- scrape_game_summary(season, gcode): returns two dataframes, a goalie summary and a game event summary, scraped from the public NHL Game Summary sheets
- scrape_event_summary(season, gcode): returns a single data frame featuring player time on ice by strength from the public NHL Event Summary sheets
- scrape_api_players(season, gcode): returns a player dimension table from the public NHL API, important for player metadata
- scrape_schedule(slate_day): returns a df of the inputted days NHL games
- scrape_schedule_vegas(slate_day): returns a dataframe that scrapes the moneyline odds that are shown on the NHL scoreboard page before a game starts

#eval_dots_goal

- very manual since this data is not yet scrapable (not a word?) publicly.
- allows the user to download the json formatted data that shows up when you inspect the EDGE dots replay of a goal on the NHL scoreboard
- user also needs to manually input the goal scorer, and the goal scoring team
- the code will return a dataframe of the opposing team skaters who were on the ice and the distance to the shooter at the time of the shot that turned into the goal
- I think this is very cool
