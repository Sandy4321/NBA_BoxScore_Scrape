from bs4 import BeautifulSoup
import pandas as pd
import requests
import pickle
import random
import time
from sqlalchemy import *
import sys
from orderedset import *
# checks if the string can be converted into a float


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def convert_name_to_team_id(name):
    name_to_id = {'TOR': 28, 'BOS': 2, 'BKN': 3, 'NYK': 20, 'PHI': 23, 'IND': 12, 'CHI': 5, 'CLE': 6, 'DET': 9,
                  'MIL': 17, 'MIA': 16, 'WAS': 30, 'CHA': 4, 'ATL': 1, 'ORL': 22, 'OKC': 21, 'POR': 25, 'MIN': 18,
                  'DEN': 8, 'UTA': 29, 'LAC': 13, 'GSW': 10, 'PHO': 24, 'SAC': 26, 'LAL': 14, 'SAS': 27, 'HOU': 11,
                  'MEM': 15, 'DAL': 7, 'NOP': 19, 'NOH': 19, 'NOK': 19, 'NJN': 3, 'CHO': 4}
    return name_to_id[name]


# Converts a row of a html_table in HTML into a list
def row_to_list(row):
    data_row = []
    data = row.find_all('td')
    for d in data:
        txt = d.text
        if is_number(txt):
            txt = float(txt)
        elif txt == '':
            txt = 0.0
        else:
            txt = txt.format('ascii')  # for pickling
        data_row.append(txt)
    return data_row


def player_row_to_list(row):
    data_row = []
    data = row.find_all('td')
    for d in data:
        link = d.find_all('a')
        if link:
            txt = url_to_id(link[0].get('href'))
        else:
            txt = d.text
        if is_number(txt):
            txt = float(txt)
        elif txt == '':
            txt = 0.0
        else:
            txt = txt.format('ascii')  # for pickling
        data_row.append(txt)
    return data_row


# convert the player URL into an id
def url_to_id(url):
    return url[url.rfind('/') + 1:url.find('.html')]


def boxscore_url_to_play_by_play(url):
    insert_ind = url.rfind('/')
    return url[:insert_ind] + '/pbp' + url[insert_ind:]


def boxscore_url_to_shotchart(url):
    insert_ind = url.rfind('/')
    return url[:insert_ind] + '/shot-chart' + url[insert_ind:]


# Takes in a html_table in the form of HTML and returns a pandas dataframe

def time_to_seconds(t):
    minutes = float(t[:t.find(':')]) * 60
    seconds = float(t[t.find(':') + 1:t.find('.')])
    msec = float(t[t.rfind('.'):])
    return minutes + seconds + msec


def get_player_boxscore_from_html_table(html_table):
    frame = pd.DataFrame()
    header = html_table.find_all('th', class_="tooltip")
    header_lst = []
    for h in header:
        header_lst.append(h.text)

    header_lst[0] = 'player_id'
    header_lst.insert(0, 'game_id')
    header_lst.append('H/A')
    rows = html_table.find_all('tr')

    for r in rows:
        data_row = player_row_to_list(r)
        if data_row:
            data_row.insert(0, None)
            data_row.append(None)
            frame = frame.append(pd.Series(data_row), ignore_index=True)
    frame.columns = header_lst
    return frame


def convert_text_to_scores(txt):
    away = float(txt[:txt.find('-')])
    home = float(txt[txt.find('-') + 1:])
    return home, away


def get_starters(players, home, away):
    home_team = players[(players['team_id'] == home)]
    away_team = players[(players['team_id'] == away)]
    starters = list(home_team.head(5)['player_id'])
    starters = starters + list(away_team.head(5)['player_id'])
    return starters


def get_team_id(scores):
    home = scores['team_id'][1]
    away = scores['team_id'][0]
    return home, away


# ################################################################################################################
#################################################################################################################
#################################################################################################################
# #
# #
#                                       Helper functions above                                                  #
#                                      Scraping functions below                                                 #
#                                                                                                               #
#                                                                                                               #
#################################################################################################################
#################################################################################################################
# ################################################################################################################


# scrapes the final score of the game and returns a pandas dataframe
# returns in the  form of [Game id, Team id, Q1, Q2, Q3, Q4, OT, Total, #OT, H/A (home = true, away = false)]
def get_final_scores(soup):
    frame = pd.DataFrame()

    total_scores = soup.find_all('table', class_="nav_table stats_table")[0]
    header = total_scores.find_all('th', class_="align_right")
    header_lst = []
    num_ot = len(header) - 5
    for h in header:
        header_lst.append(h.text)
    header_lst_tmp = [header_lst[x] for x in [0, 1, 2, 3, -1]]
    header_lst = header_lst_tmp
    header_lst.insert(4, 'OT')
    header_lst.insert(6, '#OT')
    header_lst.insert(0, 'team_id')
    header_lst.insert(0, 'game_id')  # game_id is added at the next level
    header_lst.append('H/A')

    rows = total_scores.find_all('tr')

    for ii, r in enumerate(rows):
        data_row = row_to_list(r)
        if data_row:
            if len(data_row) > 6:  # if there are multiple OTs, add up the points in OT need to add
                ot_points = sum(data_row[5:5 + num_ot])
                while len(data_row) > 7:
                    data_row.pop(6)
                data_row[5] = ot_points
                data_row[0] = convert_name_to_team_id(data_row[0])
            else:
                data_row[0] = convert_name_to_team_id(data_row[0])
                data_row.insert(5, 0)
            data_row.insert(0, None)
            data_row.append(num_ot)
            if ii == 2:
                data_row.append(0)
            elif ii == 3:
                data_row.append(1)

            frame = frame.append(pd.Series(data_row), ignore_index=True)
    frame.columns = header_lst
    return frame


# scrapes the four factors from the box score and returns a pandas dataframe
# returns in the form of [game_id, Team id, Pace, efg%, TOv%, ORB%, FT/fga, ORtg, H/A (home = true, away = false)]
def get_four_factors(soup):
    frame = pd.DataFrame()

    four_factors = soup.find_all('table', id="four_factors")[0]
    header = four_factors.find_all('th')
    header_lst = []
    for h in header:
        if h.has_attr('tip'):
            header_lst.append(h.text)
    header_lst[0] = 'team_id'
    header_lst.insert(0, 'game_id')
    header_lst.append('H/A')

    rows = four_factors.find_all('tr')
    for ii, r in enumerate(rows):
        data_row = row_to_list(r)
        if data_row:
            data_row[0] = convert_name_to_team_id(data_row[0])
            data_row.insert(0, None)
            if ii == 2:
                data_row.append(0)
            elif ii == 3:
                data_row.append(1)
            frame = frame.append(pd.Series(data_row), ignore_index=True)
    frame.columns = header_lst
    return frame


# scrapes the boxscore for individual player stats and Team Stats and returns 2 pandas dataframes
# returns players in the form of [game_id, team_id, player_id, MP, fg, fga, fg%, 3P, 3PA, 3P%, FT, FTA, FT%, ORB, DRB, 
# TRB,AST,STL, BLK, TOV, PF, PTS, +/-, TS%, efg%, 3PAr, FTr, ORB%, DRB%, TRB%, AST%, STL%, BLK%, TOV%, USG%, ORtg,
# DRtg, H/A (home = true, away = false)]
# returns teams in the form of [game_id, team_id, MP, fg, fga, fg%, 3P, 3PA, 3P%, FT, FTA, FT%, ORB, DRB, TRB, AST,
# STL, BLK, TOV, PF, PTS, +/-, TS%, efg%, 3PAr, FTr, ORB%, DRB%, TRB%, AST%, STL%, BLK%, TOV%, USG%, ORtg,
# DRtg, H/A (home = true, away = false)]


def get_boxscore_stats(soup):
    html_tables = soup.find_all('table', class_="sortable stats_table")
    home = convert_name_to_team_id(html_tables[2]['id'][:html_tables[2]['id'].find('_')])
    home_basic = get_player_boxscore_from_html_table(html_tables[2])
    home_advanced = get_player_boxscore_from_html_table(html_tables[3])
    home_basic = home_basic.drop('H/A', 1)
    home_advanced = home_advanced.drop(['game_id', 'MP'], 1)
    home_boxscore = home_basic.merge(home_advanced, on='player_id')
    home_boxscore.loc[:, 'H/A'] = 1

    home_team_boxscore = home_boxscore[home_boxscore.player_id == 'Team Totals']  # pulls out team totals
    home_boxscore = home_boxscore[home_boxscore.player_id != 'Team Totals']  # removes team totals
    home_team_boxscore = home_team_boxscore.rename(columns={'player_id': 'team_id'})
    home_team_boxscore['team_id'] = home
    home_boxscore.insert(1, 'team_id', home)

    away = convert_name_to_team_id(html_tables[0]['id'][:html_tables[0]['id'].find('_')])
    away_basic = get_player_boxscore_from_html_table(html_tables[0])
    away_advanced = get_player_boxscore_from_html_table(html_tables[1])
    away_basic = away_basic.drop('H/A', 1)
    away_advanced = away_advanced.drop(['game_id', 'MP'], 1)
    away_boxscore = away_basic.merge(away_advanced, on='player_id')
    away_boxscore.loc[:, 'H/A'] = 0

    away_team_boxscore = away_boxscore[away_boxscore.player_id == 'Team Totals']  # pulls out team totals
    away_boxscore = away_boxscore[away_boxscore.player_id != 'Team Totals']  # removes team totals
    away_team_boxscore = away_team_boxscore.rename(columns={'player_id': 'team_id'})
    away_team_boxscore['team_id'] = away
    away_boxscore.insert(1, 'team_id', away)

    team_boxscore = home_team_boxscore.append(away_team_boxscore, ignore_index=True)
    player_boxscore = home_boxscore.append(away_boxscore, ignore_index=True)

    return player_boxscore, team_boxscore


# scrapes the length of the game and returns a time object
def get_game_length(soup):
    frame = pd.DataFrame()
    try:
        html_table = soup.find_all('table', class_='margin_top small_text')[0]
        row = html_table.find_all('tr')[2]
        row_data = row.find_all('td')
        length = row_data[1].text
    except:
        length = 0
    frame = frame.append(pd.Series([None, length]), ignore_index=True)
    frame.columns = ['game_id', 'GameLength']
    return frame


# scrapes the play by play data and returns a pandas dataframe
# input is beautifulsoup soup object, and an array of starters
# returns in the form of [game_id, play_id (event#), Period (Q), Time Remaining, Time Elapsed, Play Length, 
# home team_id, away team_id, home_score, away_score, home1 player_id, home2 player_id, 
# home3 player_id, home4_player_id, home5 player_id,
# away1 player_id, away2 player_id, away3 player_id, away4 player_id, away5 player_id, player_team_id, Event Type,
# player_id, op_player_id, Assist, Block, Steal, Pts, Result (miss/make), /home(jump, away (jump), Possession (jump),
# In(sub), Out(sub), free throw, ft out of, reason, details]
# NOTE Time is stored in seconds, start of quarter = 720.0
# Event Types: ORb, Drb, Stl, Ast, Miss, Make, Blk, Jump, Foul, Ft, Turnover, Sub, Tech, Timeout, Kick

def get_play_by_play(soup, starters, home_id, away_id):
    # html_table class_ = "no_highlight stats_html_table"
    # col 0 = time remaining in quarter
    # col 1 = away team action
    # col 2 = home team action
    # col 3 = home team action
    frame = pd.DataFrame()
    ind = None
    # initialize row
    game_id = None
    play_id = 0
    period = 0
    time_remaining = None
    time_elapsed = None
    play_length = None
    home_id = home_id
    away_id = away_id
    home_score = 0
    away_score = 0
    home_players = starters[0:5]
    away_players = starters[5:10]
    play_team_id = None
    event_type = None
    player = None
    opponent = None
    assist = None
    block = None
    steal = None
    pts = 0
    result = None
    home_jump = None
    away_jump = None
    possession = None
    sub_in = None
    sub_out = None
    ft_num = None
    ft_total = None
    draw_foul = None
    foul = None
    reason = None
    details = ''

    home_players_seen = []
    away_players_seen = []

    next_home_players = home_players
    next_away_players = away_players


    away_sub_out = []
    home_sub_out = []

    period_length = 720.0
    last_play = 720.0

    header = ['game_id', 'play_id', 'Period', 'time_remaining', 'time_elapsed', 'play_length', 'home_team_id',
              'away_team_id', 'home_score', 'away_score', 'H1', 'H2', 'H3', 'H4', 'H5', 'A1', 'A2', 'A3', 'A4', 'A5',
              'player_team_id', 'event_type', 'player_id', 'Opponent_id', 'Assist', 'Block', 'Steal', 'PTS', 'Result',
              'home_jump', 'away_jump', 'Possession', 'sub_in', 'sub_out', 'ft_num', 'ft_total', 'draw foul', 'foul',
              'reason', 'details']
    # start scraping
    html_table = soup.find_all('table', class_='no_highlight stats_table')[0]
    rows = html_table.find_all('tr')
    # check for Quarter:
    for r in rows:
        data = r.find_all('td')
        if data:
            time_remaining = time_to_seconds(data[0].text)
            if len(data) == 2:
                # Start of period
                if 'Start of' in data[1].text:
                    event_type = 'Start period'
                    period += 1
                    if period > 4:
                        period_length = 300.0
                        last_play = 300.0
                    else:
                        period_length = 720.0
                        last_play = 720.0
                    details = data[1].text

                    home_players_seen = []
                    away_players_seen = []


                # Jump Ball
                elif 'End of' in data[1].text:

                    if period > 0:
                        frame_period = frame[frame[2] == period]
                        home_insert_tmp = list(OrderedSet(home_players_seen) - OrderedSet(home_players))
                        home_to_replace = list(OrderedSet(home_players) - OrderedSet(home_players_seen))
                        away_insert_tmp = list(OrderedSet(away_players_seen) - OrderedSet(away_players))
                        away_to_replace = list(OrderedSet(away_players) - OrderedSet(away_players_seen))

                        home_insert = [x for x in home_insert_tmp if x is not None]
                        away_insert = [x for x in away_insert_tmp if x is not None]

                        if home_to_replace and home_insert:
                            for i, p in enumerate(home_insert):
                                player_to_replace = home_to_replace[i]
                                for ind in range(10, 15):
                                    if player_to_replace == frame_period.iloc[0, ind]:
                                        print('ind: ', ind)
                                        break
                                ind2 = list(frame_period.index)
                                frame.loc[ind2, ind] = p
                                home_players[home_players.index(player_to_replace)] = p
                        if away_to_replace and away_insert:
                            for i, p in enumerate(away_insert):
                                player_to_replace = away_to_replace[i]
                                for ind in range(15, 20):
                                    if player_to_replace == frame_period.iloc[0, ind]:
                                        break
                                ind2 = list(frame_period.index)
                                frame.loc[ind2, ind] = p
                                away_players[away_players.index(player_to_replace)] = p
                        home_players_seen = []
                        away_players_seen = []

                elif 'Jump' in data[1].text:
                    event_type = 'Jump'
                    links = data[1].find_all('a')
                    if len(links) == 3:
                        home_jump = url_to_id(links[0]['href'])
                        away_jump = url_to_id(links[1]['href'])
                        possession = url_to_id(links[2]['href'])
                    elif len(links) == 2:
                        home_jump = url_to_id(links[0]['href'])
                        away_jump = url_to_id(links[1]['href'])

                    # check for players seen for change of quarter substitutions
                    if home_jump not in home_players_seen:
                        home_players_seen.append(home_jump)
                    if away_jump not in away_players_seen:
                        away_players_seen.append(away_jump)

                    details = data[1].text
                elif 'End' in data[1].text:
                    event_type = 'End period'
                    details = data[1].text
            elif len(data) == 6:
                if len(data[1].text) > 1:
                    details = data[1].text
                    play_team_id = away_id
                    ind = 1
                else:
                    details = data[5].text
                    play_team_id = home_id
                    ind = 5
                # Event Types: ORb, Drb, Miss, Make, Jump, Foul, Ft, Turnover, Sub, Tech, Timeout, Kick
                if 'misses' in details:
                    links = data[ind].find_all('a')
                    player = url_to_id(links[0]['href'])
                    result = 'miss'
                    if len(links) == 2:
                        block = url_to_id(links[1]['href'])
                    if '3-pt' in details:
                        pts = 0
                        event_type = '3pt'
                    elif '2-pt' in details:
                        pts = 0
                        event_type = '2pt'
                    elif 'free throw' in details:
                        pts = 0
                        ft_num_info = details[details.rfind('of') - 2:]
                        ft_num = ft_num_info[0]
                        ft_total = ft_num_info[-1]
                        event_type = 'ft'

                    # check for players seen for change of quarter substitutions
                    if ind == 5:
                        if player not in home_players_seen:
                            home_players_seen.append(player)
                        if block:
                            if block not in away_players_seen:
                                away_players_seen.append(block)
                    if ind == 1:
                        if player not in away_players_seen:
                            away_players_seen.append(player)
                        if block:
                            if block not in home_players_seen:
                                home_players_seen.append(block)

                elif 'makes' in details:
                    links = data[ind].find_all('a')
                    player = url_to_id(links[0]['href'])
                    result = 'make'
                    if len(links) == 2:
                        assist = url_to_id(links[1]['href'])
                    if '3-pt' in details:
                        pts = 3
                        event_type = '3pt'
                    elif '2-pt' in details:
                        pts = 2
                        event_type = '2pt'
                    elif 'free throw' in details:
                        pts = 1
                        if 'technical' not in details:
                            ft_num_info = details[details.rfind('of') - 2:]
                            ft_num = ft_num_info[0]
                            ft_total = ft_num_info[-1]
                        else:
                            ft_num = 1
                            ft_total = 1
                        event_type = 'ft'

                    # check for players seen for change of quarter substitutions
                    if ind == 5:
                        if player not in home_players_seen:
                            home_players_seen.append(player)
                        if assist:
                            if assist not in home_players_seen:
                                home_players_seen.append(assist)
                    if ind == 1:
                        if player not in away_players_seen:
                            away_players_seen.append(player)
                        if assist:
                            if assist not in away_players_seen:
                                away_players_seen.append(assist)

                elif 'Defensive rebound' in details:
                    if 'Team' in details:
                        player = play_team_id
                    else:
                        player = url_to_id(data[ind].find_all('a')[0]['href'])
                        # check for players seen for change of quarter substitutions
                        if ind == 5:
                            if player not in home_players_seen:
                                home_players_seen.append(player)
                        if ind == 1:
                            if player not in away_players_seen:
                                away_players_seen.append(player)

                    event_type = 'Defensive rebound'

                elif 'Offensive rebound' in details:
                    if 'Team' in details:
                        player = play_team_id
                    else:
                        player = url_to_id(data[ind].find_all('a')[0]['href'])

                        # check for players seen for change of quarter substitutions
                        if ind == 5:
                            if player not in home_players_seen:
                                home_players_seen.append(player)
                        if ind == 1:
                            if player not in away_players_seen:
                                away_players_seen.append(player)

                    event_type = 'Offensive rebound'

                elif 'Turnover by' in details:
                    if 'Team' in details:
                        player = play_team_id
                    else:
                        player = url_to_id(data[ind].find_all('a')[0]['href'])
                        # check for players seen for change of quarter substitutions
                        if ind == 5:
                            if player not in home_players_seen:
                                home_players_seen.append(player)
                        if ind == 1:
                            if player not in away_players_seen:
                                away_players_seen.append(player)

                    if 'steal' in details:
                        event_type = 'turnover'
                        steal = url_to_id(data[ind].find_all('a')[1]['href'])
                        # check for players seen for change of quarter substitutions
                        if ind == 1:
                            if steal not in home_players_seen:
                                home_players_seen.append(steal)
                        if ind == 5:
                            if steal not in away_players_seen:
                                away_players_seen.append(steal)
                    else:
                        event_type = 'turnover'
                    reason = details[details.find('(') + 1:-1]

                elif 'Delay tech' in details:
                    event_type = 'turnover'
                    player = play_team_id

                elif "Double technical foul" in details:
                    event_type = "foul"
                    reason = 'Technical'
                    if len(data[ind].find_all('a')) > 0:
                        foul = url_to_id(data[ind].find_all('a')[0]['href'])
                    else:
                        foul = None
                    if len(data[ind].find_all('a')) > 1:
                        draw_foul = url_to_id(data[ind].find_all('a')[1]['href'])
                    else:
                        draw_foul = None
                    player = foul

                elif 'foul' in details:
                    event_type = 'foul'
                    if 'Technical foul by Team' in details:
                        player = play_team_id
                    else:
                        if play_team_id == home_id:
                            play_team_id = away_id
                        else:
                            play_team_id = home_id

                        if len(data[ind].find_all('a')) > 0:
                            foul = url_to_id(data[ind].find_all('a')[0]['href'])
                        else:
                            foul = None
                        if len(data[ind].find_all('a')) > 1:
                            draw_foul = url_to_id(data[ind].find_all('a')[1]['href'])
                        else:
                            draw_foul = None

                        player = foul

                    if 'Offensive' in details:
                        reason = 'Offensive'

                        if ind == 1:
                            if draw_foul and (draw_foul not in home_players_seen):
                                home_players_seen.append(draw_foul)
                            if foul and (foul not in away_players_seen):
                                away_players_seen.append(foul)
                        if ind == 5:
                            if draw_foul and (draw_foul not in away_players_seen):
                                away_players_seen.append(draw_foul)
                            if foul and (foul not in home_players_seen):
                                home_players_seen.append(foul)

                    elif 'Technical' in details:
                        reason = 'Technical'

                    elif 'Double' in details:
                        reason = 'Double foul'

                        if ind == 1:
                            if draw_foul and (draw_foul not in home_players_seen):
                                home_players_seen.append(draw_foul)
                            if foul and (foul not in away_players_seen):
                                away_players_seen.append(foul)
                        if ind == 5:
                            if draw_foul and (draw_foul not in away_players_seen):
                                away_players_seen.append(draw_foul)
                            if foul and (foul not in home_players_seen):
                                home_players_seen.append(foul)
                    else:
                        if 'Shooting' in details:
                            reason = 'Shooting'
                        elif 'Personal' in details:
                            reason = 'Personal'
                        elif 'Loose ball' in details:
                            reason = 'Loose ball'

                        if ind == 5:
                            if draw_foul and (draw_foul not in home_players_seen):
                                home_players_seen.append(draw_foul)
                            if foul and (foul not in away_players_seen):
                                away_players_seen.append(foul)
                        if ind == 1:
                            if draw_foul and (draw_foul not in away_players_seen):
                                away_players_seen.append(draw_foul)
                            if foul and (foul not in home_players_seen):
                                home_players_seen.append(foul)

                elif 'timeout' in details:
                    event_type = 'timeout'
                    if ind == 5:
                        player = home_id
                    elif ind == 1:
                        player = away_id

                elif 'Defensive three seconds' in details:
                    player = url_to_id(data[ind].find_all('a')[0]['href'])
                    event_type = '3 seconds'

                    if ind == 5:
                        if player not in away_players_seen:
                            away_players_seen.append(player)
                    if ind == 1:
                        if player not in home_players_seen:
                            home_players_seen.append(player)

                elif 'enters the game' in details:
                    links = data[ind].find_all('a')
                    player = url_to_id(links[0]['href'])
                    sub_in = player
                    sub_out = url_to_id(links[1]['href'])
                    event_type = 'substitution'
                    if ind == 1:
                        if sub_out not in away_players_seen:
                            away_players_seen.append(sub_out)
                        if sub_out not in away_players:
                            if None in away_players:
                                player_insert = None
                            else:
                                removable_players = OrderedSet(away_players) - OrderedSet(away_players_seen)
                                player_insert = list(removable_players)[0]
                            frame_period = frame[frame[2] == period]
                            for ind in range(15, 20):
                                if player_insert == frame_period.iloc[0, ind]:
                                    break
                            ind2 = list(frame_period.index)
                            frame.loc[ind2, ind] = sub_out
                            away_players[ind - 15] = sub_out
                        if sub_in in away_players:
                            removable_players = OrderedSet(away_players_seen) - OrderedSet(away_players)
                            if removable_players:
                                player_insert = list(removable_players)[0]
                            else:
                                player_insert = None
                            frame_period = frame[frame[2] == period]
                            for ind in range(15, 20):
                                if sub_in == frame_period.iloc[0, ind]:
                                    break
                            ind2 = list(frame_period.index)
                            frame.loc[ind2, ind] = player_insert
                            away_players[ind - 15] = player_insert
                        away_sub_out.append(sub_out)
                        away_players[away_players.index(sub_out)] = sub_in
                        away_players_seen[away_players_seen.index(sub_out)] = sub_in

                    elif ind == 5:
                        print("\n\n")
                        print(period)
                        print(home_players)
                        print(home_players_seen)
                        print(sub_out)
                        print(sub_in)
                        if sub_out not in home_players_seen:
                            home_players_seen.append(sub_out)
                        if sub_out not in home_players:
                            if None in home_players:
                                player_insert = None
                            else:
                                removable_players = OrderedSet(home_players) - OrderedSet(home_players_seen)
                                player_insert = list(removable_players)[0]
                            frame_period = frame[frame[2] == period]
                            for ind in range(10, 15):
                                if player_insert == frame_period.iloc[0, ind]:
                                    break
                            ind2 = list(frame_period.index)
                            frame.loc[ind2, ind] = sub_out
                            home_players[ind - 10] = sub_out
                        if sub_in in home_players:
                            removable_players = OrderedSet(home_players_seen) - OrderedSet(home_players)
                            if removable_players:
                                player_insert = list(removable_players)[0]
                            else:
                                player_insert = None
                            frame_period = frame[frame[2] == period]
                            for ind in range(10, 15):
                                if sub_in == frame_period.iloc[0, ind]:
                                    break
                            ind2 = list(frame_period.index)
                            frame.loc[ind2, ind] = player_insert
                            home_players[ind - 10] = player_insert
                        home_sub_out.append(sub_out)
                        home_players[home_players.index(sub_out)] = sub_in
                        home_players_seen[home_players_seen.index(sub_out)] = sub_in
                home_score, away_score = convert_text_to_scores(data[3].text)
            time_elapsed = period_length - time_remaining
            play_length = last_play - time_remaining
            if play_length > 0:
                next_home_players = home_players
                next_away_players = away_players
                if away_sub_out:
                    for a in away_sub_out:
                        if a in away_players_seen:
                            away_players_seen.remove(a)
                if home_sub_out:
                    for h in home_sub_out:
                        if h in home_players_seen:
                            home_players_seen.remove(h)
                away_sub_out = []
                home_sub_out = []
            last_play = time_remaining
            frame_row = [game_id, play_id, period, time_remaining, time_elapsed, play_length, home_id, away_id,
                         home_score, away_score] + next_home_players + next_away_players + [play_team_id, event_type, player,
                                                                                  opponent, assist, block, steal, pts,
                                                                                  result, home_jump, away_jump,
                                                                                  possession, sub_in, sub_out, ft_num,
                                                                                  ft_total, draw_foul, foul, reason,
                                                                                  details]
            frame = frame.append(pd.Series(frame_row), ignore_index=True)

        ##############
        # reOrderedSet vars #
        ##############
        play_id += 1
        time_remaining = None
        time_elapsed = None
        play_length = None
        play_team_id = None
        event_type = None
        player = None
        opponent = None
        assist = None
        block = None
        steal = None
        pts = 0
        result = None
        home_jump = None
        away_jump = None
        possession = None
        sub_in = None
        sub_out = None
        ft_num = None
        ft_total = None
        draw_foul = None
        foul = None
        reason = None
        details = ''

        ##################
        # End reOrderedSet vars #
        ##################
    frame.columns = header
    return frame


# scrapes the refs for the game and returns a pandas dataframe
# returns in the form of [game_id,refid, refid, refid]


def get_refs(soup):
    frame = pd.DataFrame()
    html_table = soup.find_all('table', class_='margin_top small_text')[0]
    row = html_table.find_all('tr')[0]
    row_data = row.find_all('a')
    for d in row_data:
        frame = frame.append(pd.Series([None, url_to_id(d['href']), d.text]), ignore_index=True)
    frame.columns = ['game_id', 'Refid', 'Name']
    return frame


def generate_bs_from_pbp(pbp):
    header = ['player_id', 'MP', 'FG', 'FGA', '3P', '3PA', 'FT', 'FTA', 'ORB', 'DRB', 'TRB', 'AST', 'STL', 'BLK', 'TOV',
              'PF', 'PTS']
    frame = pd.DataFrame()
    h1 = list(pbp['H1'])
    h2 = list(pbp['H2'])
    h3 = list(pbp['H3'])
    h4 = list(pbp['H4'])
    h5 = list(pbp['H5'])
    home_players = OrderedSet(h1 + h2 + h3 + h4 + h5)

    a1 = list(pbp['A1'])
    a2 = list(pbp['A2'])
    a3 = list(pbp['A3'])
    a4 = list(pbp['A4'])
    a5 = list(pbp['A5'])
    away_players = OrderedSet(a1 + a2 + a3 + a4 + a5)

    for h in home_players:
        player_pbp = pbp[(pbp['H1'] == h) | (pbp['H2'] == h) | (pbp['H3'] == h) | (pbp['H4'] == h) | (pbp['H5'] == h)]
        mp = sum(player_pbp['play_length'])
        m, s = divmod(mp, 60)
        mp = str(int(m)) + ':' + str(int(s)).zfill(2)

        player_assists = player_pbp[(player_pbp['Assist'] == h)]
        assist = len(player_assists.index)

        blk = len(player_pbp[(player_pbp['Block'] == h)].index)

        stl = len(player_pbp[(player_pbp['Steal'] == h)].index)

        player_shots = player_pbp[
            (player_pbp['player_id'] == h) & ((player_pbp['Result'] == 'make') | (player_pbp['Result'] == 'miss'))]
        fga = len(player_shots[(player_shots['event_type'] != 'ft')])
        fg = len(player_shots[(player_shots['Result'] == 'make') & (player_shots['event_type'] != 'ft')])
        threes_attempted = len(player_shots[player_shots['event_type'] == '3pt'])
        threes_made = len(player_shots[(player_shots['event_type'] == '3pt') & (player_shots['Result'] == 'make')])
        fta = len(player_shots[(player_shots['event_type'] == 'ft')])
        ft = len(player_shots[(player_shots['event_type'] == 'ft') & (player_shots['Result'] == 'make')])
        pts = sum(player_shots['PTS'])

        pf = len(player_pbp[(((player_pbp['foul'] == h) & (player_pbp['reason'] != 'Technical')) |
                             ((player_pbp['draw foul'] == h) & (player_pbp['reason'] == 'Double foul')))])

        tov = len(player_pbp[(player_pbp['event_type'] == 'turnover') & (player_pbp['player_id'] == h)])

        orb = len(player_pbp[(player_pbp['event_type'] == 'Offensive rebound') & (player_pbp['player_id'] == h)])

        drb = len(player_pbp[(player_pbp['event_type'] == 'Defensive rebound') & (player_pbp['player_id'] == h)])

        trb = orb + drb

        frame = frame.append(
            pd.Series([h, mp, fg, fga, threes_made, threes_attempted, ft, fta, orb, drb, trb, assist, stl, blk, tov, pf,
                       pts]), ignore_index=True)

    for a in away_players:
        player_pbp = pbp[(pbp['A1'] == a) | (pbp['A2'] == a) | (pbp['A3'] == a) | (pbp['A4'] == a) | (pbp['A5'] == a)]
        mp = sum(player_pbp['play_length'])
        m, s = divmod(mp, 60)
        mp = str(int(m)) + ':' + str(int(s)).zfill(2)
        player_assists = player_pbp[(player_pbp['Assist'] == a)]
        assist = len(player_assists.index)

        block = len(player_pbp[(player_pbp['Block'] == a)].index)

        steal = len(player_pbp[(player_pbp['Steal'] == a)].index)

        player_shots = player_pbp[
            (player_pbp['player_id'] == a) & ((player_pbp['Result'] == 'make') | (player_pbp['Result'] == 'miss'))]
        fga = len(player_shots[(player_shots['event_type'] != 'ft')])
        fg = len(player_shots[(player_shots['Result'] == 'make') & (player_shots['event_type'] != 'ft')])
        threes_attempted = len(player_shots[player_shots['event_type'] == '3pt'])
        threes_made = len(player_shots[(player_shots['event_type'] == '3pt') & (player_shots['Result'] == 'make')])
        fta = len(player_shots[(player_shots['event_type'] == 'ft')])
        ft = len(player_shots[(player_shots['event_type'] == 'ft') & (player_shots['Result'] == 'make')])
        points = sum(player_shots['PTS'])

        fouls = len(player_pbp[(((player_pbp['foul'] == a) & (player_pbp['reason'] != 'Technical')) |
                                ((player_pbp['draw foul'] == a) & (player_pbp['reason'] == 'Double foul')))])

        turnovers = len(player_pbp[(player_pbp['event_type'] == 'turnover') & (player_pbp['player_id'] == a)])

        orb = len(player_pbp[(player_pbp['event_type'] == 'Offensive rebound') & (player_pbp['player_id'] == a)])

        drb = len(player_pbp[(player_pbp['event_type'] == 'Defensive rebound') & (player_pbp['player_id'] == a)])

        total_rebounds = orb + drb

        frame = frame.append(
            pd.Series(
                [a, mp, fg, fga, threes_made, threes_attempted, ft, fta, orb, drb, total_rebounds, assist, steal, block,
                 turnovers, fouls, points]),
            ignore_index=True)

    frame.columns = header
    return frame


def compare_boxscores(bs, pbpbs):
    cols = pbpbs.columns
    players = bs['player_id']
    failures = pd.DataFrame()
    for p in players:
        try:
            row1 = bs[bs['player_id'] == p]
            row2 = pbpbs[pbpbs['player_id'] == p]
            for c in cols:
                val1 = row1.loc[:, c].values[0]
                val2 = row2.loc[:, c].values[0]
                if type('') == type(val1) and ':' in val1:
                    time_low = int(val1[:val1.find(':')]) - 1
                    time_high = int(val1[:val1.find(':')]) + 1
                    test_time = int(val2[:val2.find(':')])
                    if time_low > test_time or test_time > time_high:
                        failures = failures.append(pd.Series([p, c, val1, val2]), ignore_index=True)
                elif val1 != val2:
                    failures = failures.append(pd.Series([p, c, val1, val2]), ignore_index=True)
        except:
            failures = failures.append(pd.Series([p, 0, 0, 0]), ignore_index=True)
    if not failures.empty:
        failures.columns = ['player_id', 'Category', 'BS', 'PBP']
    return failures


# takes in a link for the box score and stores all values in a SQL database
def scrape_boxscore(link):
    print('start scraping')
    r = requests.get(link)
    soup_bs = BeautifulSoup(r.text, 'html5lib')
    refs = get_refs(soup_bs)
    refs.loc[:, 'game_id'] = url_to_id(link)
    print('refs complete')
    # print(refs)

    players, teams = get_boxscore_stats(soup_bs)
    players.loc[:, 'game_id'] = url_to_id(link)
    teams.loc[:, 'game_id'] = url_to_id(link)
    print('players and teams complete')
    # print(players)
    # print(teams)

    four_factors = get_four_factors(soup_bs)
    four_factors.loc[:, 'game_id'] = url_to_id(link)
    print('4factors complete')
    # print(ff)

    scores = get_final_scores(soup_bs)
    scores.loc[:, 'game_id'] = url_to_id(link)
    print('scores complete')
    # print(scores)

    length = get_game_length(soup_bs)
    length.loc[:, 'game_id'] = url_to_id(link)
    print('length complete')

    # print(length)

    r_int = random.randint(1, 5)
    print('wait: ', r_int)
    time.sleep(r_int)

    play_by_play_link = boxscore_url_to_play_by_play(link)

    r = requests.get(play_by_play_link)
    soup_pbp = BeautifulSoup(r.text, 'html5lib')

    home, away = get_team_id(scores)
    starters = get_starters(players, home, away)
    """
    play_by_play = get_play_by_play(soup_pbp, starters, home, away)
    play_by_play.loc[:, 'game_id'] = url_to_id(link)
    print('play by play complete')
    # print(Play_by_Play)
    return refs, players, teams, four_factors, scores, length, play_by_play
    """
    return refs, players, teams, four_factors, scores, length



refs = pd.DataFrame()
playerStats = pd.DataFrame()
teamStats = pd.DataFrame()
fourFactors = pd.DataFrame()
finalScores = pd.DataFrame()
gameLengths = pd.DataFrame()

boxscores = pickle.load(open("boxscores.p", "rb"))
for i, b in enumerate(boxscores):
    refBS, playerBS, teamsBS, ffBS, scoresBS, lengthBS = scrape_boxscore(b)
    refs = refs.append(refBS, ignore_index=True)
    playerStats = playerStats.append(playerBS, ignore_index=True)
    teamStats = teamStats.append(teamsBS, ignore_index=True)
    fourFactors = fourFactors.append(ffBS, ignore_index=True)
    finalScores = finalScores.append(scoresBS, ignore_index=True)
    gameLengths = gameLengths.append(lengthBS, ignore_index=True)

    if (i % 1200) == 0:
        refs.to_csv("Scrape Results/refs.csv")
        playerStats.to_csv("Scrape Results/playerStats.csv")
        teamStats.to_csv("Scrape Results/teamStats.csv")
        fourFactors.to_csv("Scrape Results/fourFactors.csv")
        finalScores.to_csv("Scrape Results/finalScores.csv")
        gameLengths.to_csv("Scrape Results/gameLengths.csv")

    if (i + 1) % 1200 == 0:
        R = random.randint(600, 900)
        print('wait: ', R)
        time.sleep(R)
    else:
        R = random.randint(2, 6)
        print('wait: ', R)
        time.sleep(R)


"""
with open('Scrape Results/fail.p', 'rb') as handle:
        bs = pickle.load(handle)
for i, test in enumerate(bs):
    test = bs[2]
    print(i)
    print(test)
    refs, players, teams, ff, scores, length, Play_by_Play = scrape_boxscore(test)
    R = random.randint(5, 15)
    print('wait: ', R)
    time.sleep(R)
"""

"""
boxscores = pickle.load(open("boxscores.p", "rb"))
issues = pickle.load(open("Scrape Results/fail.p", "rb"))
finished = pickle.load(open("Scrape Results/finishedBS.p", "rb"))
pbpError = []
for f in issues:
    pbpError.append(f[0])

errors = list(OrderedSet(boxscores) - OrderedSet(finished) - OrderedSet(pbpError))
print(len(errors))
i = 0
#for b in errors:
b = errors[19]
print(b)
print(i)
# try:
refBS, playerBS, teamsBS, ffBS, scoresBS, lengthBS, play_by_play_frame = scrape_boxscore(b)
play_by_play_frame.to_csv('test.csv')
pbp_bs = generate_bs_from_pbp(play_by_play_frame)

fail = compare_boxscores(playerBS, pbp_bs)
print('scrape complete')
print(fail)
i += 1
"""
"""
refs = pd.DataFrame()
playerStats = pd.DataFrame()
teamStats = pd.DataFrame()
fourFactors = pd.DataFrame()
finalScores = pd.DataFrame()
gameLengths = pd.DataFrame()
playByPlay = pd.DataFrame()


playByPlay_to_fix = pd.DataFrame()


compare_failures = []
compare_fail_count = 1

error_failures = []
error_fail_count = 1

finished = []

bs = pickle.load(open("boxscores.p", "rb"))
for i, b in enumerate(bs):
    print(i)
    print(b)
    try:
        refBS, playerBS, teamsBS, ffBS, scoresBS, lengthBS, PBP = scrape_boxscore(b)
        pbpbs = generate_bs_from_pbp(PBP)
        fail = compare_boxscores(playerBS, pbpbs)

        refs = refs.append(refBS, ignore_index=True)
        playerStats = playerStats.append(playerBS, ignore_index=True)
        teamStats = teamStats.append(teamsBS, ignore_index=True)
        fourFactors = fourFactors.append(ffBS, ignore_index=True)
        finalScores = finalScores.append(scoresBS, ignore_index=True)
        gameLengths = gameLengths.append(lengthBS, ignore_index=True)

        if (i) % 1200 == 0:
            refs.to_csv("Scrape Results/refs.csv")
            playerStats.to_csv("Scrape Results/playerStats.csv")
            teamStats.to_csv("Scrape Results/teamStats.csv")
            fourFactors.to_csv("Scrape Results/fourFactors.csv")
            finalScores.to_csv("Scrape Results/finalScores.csv")
            gameLengths.to_csv("Scrape Results/gameLengths.csv")

        if fail.empty:
            print('No Failure')
            playByPlay = playByPlay.append(PBP, ignore_index=True)
            playByPlay.to_csv("Scrape Results/pbp.csv")
        else:
            print('Failure number {0}, appending failures to failure list'.format(compare_fail_count))
            print(fail)
            playByPlay_to_fix = playByPlay_to_fix.append(PBP, ignore_index=True)
            compare_fail_count +=1
            compare_failures.append((b, fail))
            pickle.dump(compare_failures, open("Scrape Results/fail.p", "wb"))
            playByPlay_to_fix.to_csv("Scrape Results/pbpToFix.csv")
        finished.append(b)
        if i % 200 == 0:
            with open("Scrape Results/finishedBS.p", "wb") as file2:
                pickle.dump(finished, file2)
            file2.close()

    except:
        error_failures.append(b)
        print('Error in scraping, Error number: ', error_fail_count)
        error_fail_count += 1
        e = sys.exc_info()
        with open('Scrape Results/exceptions.txt', 'a') as file:
            file.write("Error number {0}: {1}\n" .format(error_fail_count, e))
        file.close()

    print('dump complete')
    if (i + 1) % 1200 == 0:
        R = random.randint(600, 900)
        print('wait: ', R)
        time.sleep(R)
    else:
        R = random.randint(2, 6)
        print('wait: ', R)
        time.sleep(R)


"""

"""
    except:
        print('Failed on Boxscore: ', b)
        print('{0} failures so so far'.format(failcount))
        failures.append(b)
        failcount += 1
        pickle.dump(failures, open("Scrape Results/fail.p", "wb"))
"""
"""
with open('boxscores.p', 'rb') as handle:
        bs = pickle.load(handle)

b = bs[0]
print(b)
refBS, playerBS, teamsBS, ffBS, scoresBS, lengthBS, PBP = scrape_boxscore(b)
PBPBS = generate_bs_from_pbp(PBP)
failures = compare_boxscores(playerBS, PBPBS)
print(failures)
"""