import time
from bs4 import BeautifulSoup
import pandas as pd
import requests
import pickle
import random
import time

# checks if the string can be converted into a float
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def convertNametoTID(name):
    N2ID = {'TOR': 28, 'BOS': 2, 'BKN': 3, 'NYK': 20, 'PHI': 23, 'IND': 12, 'CHI': 5, 'CLE': 6, 'DET': 9, 'MIL': 17,
            'MIA': 16, 'WAS': 30, 'CHA': 4, 'ATL': 1, 'ORL': 22, 'OKC': 21, 'POR': 25, 'MIN': 18, 'DEN': 8, 'UTA': 29,
            'LAC': 13, 'GSW': 10, 'PHO': 24, 'SAC': 26, 'LAL': 14, 'SAS': 27, 'HOU': 11, 'MEM': 15, 'DAL': 7, 'NOP': 19,
            'NOH': 19, 'NOK': 19, 'NJN': 3, 'CHO': 4}
    return N2ID[name]


# Converts a row of a table in HTML into a list
def rowToList(row):
    data_row = []
    data = row.find_all('td')
    for d in data:
        text = d.text
        if is_number(text):
            text = float(text)
        elif text == '':
            text = 0.0
        else:
            text = text.format('ascii')  #for pickling
        data_row.append(text)
    return data_row


def playerRowToList(row):
    data_row = []
    data = row.find_all('td')
    for d in data:
        link = d.find_all('a')
        if link:
            text = URLtoID(link[0].get('href'))
        else:
            text = d.text
        if is_number(text):
            text = float(text)
        elif text == '':
            text = 0.0
        else:
            text = text.format('ascii')  #for pickling
        data_row.append(text)
    return data_row


# convert the player URL into an ID
def URLtoID(url):
    return url[url.rfind('/') + 1:url.find('.html')]


def BoxScoreURLtoPBP(url):
    insert_ind = url.rfind('/')
    return url[:insert_ind] + '/pbp' + url[insert_ind:]


def BoxScoreURLtoShotChart(url):
    insert_ind = url.rfind('/')
    return url[:insert_ind] + '/shot-chart' + url[insert_ind:]


#Takes in a table in the form of HTML and returns a pandas dataframe
def detailToDataRow(table):
    pass


def timeToSeconds(time):
    minutes = float(time[:time.find(':')]) * 60
    seconds = float(time[time.find(':') + 1:time.find('.')])
    msec = float(time[time.rfind('.'):])
    return minutes + seconds + msec


def getPlayerBoxScore_fromTable(table):
    frame = pd.DataFrame()
    header = table.find_all('th', class_="tooltip")
    header_lst = []
    for h in header:
        header_lst.append(h.text)

    header_lst[0] = 'PlayerID'
    header_lst.insert(0, 'GameID')
    header_lst.append('H/A')
    rows = table.find_all('tr')

    for i, r in enumerate(rows):
        data_row = playerRowToList(r)
        if data_row:
            data_row.insert(0, None)
            data_row.append(None)
            frame = frame.append(pd.Series(data_row), ignore_index=True)
    frame.columns = header_lst
    return frame


def convertTextToScores(text):
    away = float(text[:text.find('-')])
    home = float(text[text.find('-') + 1:])
    return home, away


def getStarters(players, home, away):
    homeTeam = players[(players['TeamID'] == home)]
    awayTeam = players[(players['TeamID'] == away)]
    starters = list(homeTeam.head(5)['PlayerID'])
    starters = starters + list(awayTeam.head(5)['PlayerID'])
    return starters


def getTeamID(scores):
    home = scores['TeamID'][1]
    away = scores['TeamID'][0]
    return home, away


# ################################################################################################################
#################################################################################################################
#################################################################################################################
# #
#                                                                                                               #
#                                       Helper functions above                                                  #
#                                      Scraping functions below                                                 #
#                                                                                                               #
#                                                                                                               #
#################################################################################################################
#################################################################################################################
# ################################################################################################################


# scrapes the final score of the game and returns a pandas dataframe
# returns in the  form of [Game ID, Team ID, Q1, Q2, Q3, Q4, OT, Total, #OT, H/A (Home = true, away = false)]
def getFinalScores(soup):
    frame = pd.DataFrame()

    total_scores = soup.find_all('table', class_="nav_table stats_table")[0]
    header = total_scores.find_all('th', class_="align_right")
    header_lst = []
    num_OT = len(header) - 5
    for h in header:
        header_lst.append(h.text)
    header_lst_tmp = [header_lst[x] for x in [0, 1, 2, 3, -1]]
    header_lst = header_lst_tmp
    header_lst.insert(4, 'OT')
    header_lst.insert(6, '#OT')
    header_lst.insert(0, 'TeamID')
    header_lst.insert(0, 'GameID')  # gameID is added at the next level
    header_lst.append('H/A')

    rows = total_scores.find_all('tr')

    for i, r in enumerate(rows):
        data_row = rowToList(r)
        if data_row:
            if len(data_row) > 6:  # if there are multiple OTs, add up the points in OT need to add
                OT_Points = sum(data_row[5:5 + num_OT])
                while len(data_row) > 7:
                    data_row.pop(6)
                data_row[5] = OT_Points
            else:
                data_row[0] = convertNametoTID(data_row[0])
                data_row.insert(5, 0)
            data_row.insert(0, None)
            data_row.append(num_OT)
            if i == 2:
                data_row.append(0)
            elif i == 3:
                data_row.append(1)
            frame = frame.append(pd.Series(data_row), ignore_index=True)
    frame.columns = header_lst
    return frame


# scrapes the four factors from the box score and returns a pandas dataframe
#returns in the form of [GameID, Team ID, Pace, eFG%, TOv%, ORB%, FT/FGA, ORtg, H/A (home = true, away = false)]
def getFourFactors(soup):
    frame = pd.DataFrame()

    four_factors = soup.find_all('table', id="four_factors")[0]
    header = four_factors.find_all('th')
    header_lst = []
    for h in header:
        if h.has_attr('tip'):
            header_lst.append(h.text)
    header_lst[0] = 'TeamID'
    header_lst.insert(0, 'GameID')
    header_lst.append('H/A')

    rows = four_factors.find_all('tr')
    for i, r in enumerate(rows):
        data_row = rowToList(r)
        if data_row:
            data_row[0] = convertNametoTID(data_row[0])
            data_row.insert(0, None)
            if i == 2:
                data_row.append(0)
            elif i == 3:
                data_row.append(1)
            frame = frame.append(pd.Series(data_row), ignore_index=True)
    frame.columns = header_lst
    return frame


# scrapes the boxscore for individual player stats and Team Stats and returns 2 pandas dataframes
# returns players in the form of [GameID, TeamID, PlayerID, MP, FG, FGA, FG%, 3P, 3PA, 3P%, FT, FTA, FT%, ORB, DRB, TRB,
# AST,STL, BLK, TOV, PF, PTS, +/-, TS%, eFG%, 3PAr, FTr, ORB%, DRB%, TRB%, AST%, STL%, BLK%, TOV%, USG%, ORtg,
# DRtg, H/A (home = true, away = false)]
# returns teams in the form of [GameID, TeamID, MP, FG, FGA, FG%, 3P, 3PA, 3P%, FT, FTA, FT%, ORB, DRB, TRB, AST,
# STL, BLK, TOV, PF, PTS, +/-, TS%, eFG%, 3PAr, FTr, ORB%, DRB%, TRB%, AST%, STL%, BLK%, TOV%, USG%, ORtg,
# DRtg, H/A (home = true, away = false)]
def getBoxScoreStats(soup):
    tables = soup.find_all('table', class_="sortable  stats_table")
    Home = convertNametoTID(tables[2]['id'][:tables[2]['id'].find('_')])
    Home_basic = getPlayerBoxScore_fromTable(tables[2])
    Home_advanced = getPlayerBoxScore_fromTable(tables[3])
    Home_basic = Home_basic.drop('H/A', 1)
    Home_advanced = Home_advanced.drop(['GameID', 'MP'], 1)
    Home_bscore = Home_basic.merge(Home_advanced, on='PlayerID')
    Home_bscore.loc[:, 'H/A'] = 1

    Home_team_bscore = Home_bscore[Home_bscore.PlayerID == 'Team Totals']  # pulls out team totals
    Home_bscore = Home_bscore[Home_bscore.PlayerID != 'Team Totals']  # removes team totals
    Home_team_bscore = Home_team_bscore.rename(columns={'PlayerID': 'TeamID'})
    Home_team_bscore['TeamID'] = Home
    Home_bscore.insert(1, 'TeamID', Home)

    Away = convertNametoTID(tables[0]['id'][:tables[0]['id'].find('_')])
    Away_basic = getPlayerBoxScore_fromTable(tables[0])
    Away_advanced = getPlayerBoxScore_fromTable(tables[1])
    Away_basic = Away_basic.drop('H/A', 1)
    Away_advanced = Away_advanced.drop(['GameID', 'MP'], 1)
    Away_bscore = Away_basic.merge(Away_advanced, on='PlayerID')
    Away_bscore.loc[:, 'H/A'] = 0

    Away_team_bscore = Away_bscore[Away_bscore.PlayerID == 'Team Totals']  # pulls out team totals
    Away_bscore = Away_bscore[Away_bscore.PlayerID != 'Team Totals']  # removes team totals
    Away_team_bscore = Away_team_bscore.rename(columns={'PlayerID': 'TeamID'})
    Away_team_bscore['TeamID'] = Away
    Away_bscore.insert(1, 'TeamID', Away)

    Team_bscore = Home_team_bscore.append(Away_team_bscore, ignore_index=True)
    Player_bscore = Home_bscore.append(Away_bscore, ignore_index=True)

    return Player_bscore, Team_bscore


#scrapes the length of the game and returns a time object
def getGameLength(soup):
    frame = pd.DataFrame()
    table = soup.find_all('table', class_='margin_top small_text')[0]
    row = table.find_all('tr')[2]
    row_data = row.find_all('td')
    frame = frame.append(pd.Series([None, row_data[1].text]), ignore_index=True)
    frame.columns = ['GameID', 'GameLength']
    return frame


# scrapes the play by play data and returns a pandas dataframe
# input is beautifulsoup soup object, and an array of starters
# returns in the form of [GameID, playID (event#), Period (Q), Time Remaining, Time Elapsed, Play Length, Home TeamID,
# Away TeamID, HomeScore, AwayScore, Home1 PlayerID, Home2 PlayerID, Home3 PlayerID, Home4 PlayerID, Home5 PlayerID,
# Away1 PlayerID, Away2 PlayerID, Away3 PlayerID, Away4 PlayerID, Away5 PlayerID, PlayerTeamID, Event Type,
# PlayerID, OppPlayerID, Assist, Block, Steal, Pts, Result (miss/make), /home(jump, Away (jump), Possession (jump),
# In(sub), Out(sub), free throw, ft out of, reason, details]
# NOTE Time is stored in seconds, start of quarter = 720.0
# Event Types: ORb, Drb, Stl, Ast, Miss, Make, Blk, Jump, Foul, Ft, Turnover, Sub, Tech, Timeout, Kick
def getPlayByPlay(soup, starters, HomeID, AwayID):
    # table class_ = "no_highlight stats_table"
    # col 0 = time remaining in quarter
    # col 1 = away team action
    # col 2 = home team action
    # col 3 = home team action
    frame = pd.DataFrame()
    ind = None
    # initialize row
    gameID = None
    playID = 0
    period = 0
    timeRemaining = None
    timeElapsed = None
    playLength = None
    homeID = HomeID
    awayID = AwayID
    homeScore = 0
    awayScore = 0
    homeplayers = starters[0:5]
    awayplayers = starters[5:10]
    playTeamID = None
    eventType = None
    player = None
    opponent = None
    assist = None
    block = None
    steal = None
    pts = 0
    result = None
    homeJump = None
    awayJump = None
    possession = None
    subIn = None
    subOut = None
    ftNum = None
    ftTotal = None
    drawFoul = None
    foul = None
    reason = None
    details = ''

    homeplayersSeen = []
    awayplayersSeen = []

    periodLength = 720.0
    LastPlay = 720.0

    header = ['GameID', 'PlayID', 'Period', 'TimeRemaining', 'TimeElapsed', 'PlayLength', 'HomeTeamID', 'AwayTeamID',
              'HomeScore', 'AwayScore', 'H1', 'H2', 'H3', 'H4', 'H5', 'A1', 'A2', 'A3', 'A4', 'A5', 'PlayerTeamID',
              'EventType', 'PlayerID', 'OpponentID', 'Assist', 'Block', 'Steal', 'PTS', 'Result', 'HomeJump',
              'AwayJump', 'Possession', 'SubIn', 'SubOut', 'ftNum', 'ftTotal', 'draw foul', 'foul', 'reason', 'details']
    # start scraping
    table = soup.find_all('table', class_='no_highlight stats_table')[0]
    rows = table.find_all('tr')


    # check for Quarter:
    for r in rows:
        data = r.find_all('td')
        if data:
            if len(data) == 2:
                # Start of period
                if 'Start of' in data[1].text:
                    eventType = 'Start period'
                    if period > 1:
                        frameQ = frame[frame[2] == period]
                        homeReplace = list(set(homeplayersSeen) - set(homeplayers))
                        homeToReplace = list(set(homeplayers) - set(homeplayersSeen))
                        awayReplace = list(set(awayplayersSeen) - set(awayplayers))
                        awayToReplace = list(set(awayplayers) - set(awayplayersSeen))
                        for i, p in enumerate(homeToReplace):
                            pReplace = homeReplace[i]
                            awaycol = None
                            for ind in range(15, 20):
                                if p == frameQ.iloc[0, ind]:
                                    awaycol = ind
                                    break
                            frameQ.loc[:, ind] = pReplace
                            homeplayers[homeplayers.index(p)] = pReplace

                        for i, p in enumerate(awayToReplace):
                            pReplace = awayReplace[i]
                            homecol = None
                            for ind in range(10, 15):
                                if p == frameQ.iloc[0, ind]:
                                    homecol = ind
                                    break
                            frameQ.loc[:, ind] = pReplace
                            awayplayers[awayplayers.index(p)] = pReplace
                    period += 1
                    if period > 4:
                        periodLength = 300.0
                    else:
                        periodLength = 720.0
                    details = data[1].text

                    homeplayersSeen = []
                    awayplayersSeen = []
                # Jump Ball
                elif 'Jump' in data[1].text:
                    eventType = 'Jump'
                    links = data[1].find_all('a')
                    if len(links) == 3:
                        homeJump = URLtoID(links[0]['href'])
                        awayJump = URLtoID(links[1]['href'])
                        possession = URLtoID(links[2]['href'])
                    elif len(links) == 2:
                        homeJump = URLtoID(links[0]['href'])
                        awayJump = URLtoID(links[1]['href'])

                    # check for players seen for change of quarter substitutions
                    if homeJump not in homeplayersSeen:
                        homeplayersSeen.append(homeJump)
                    if awayJump not in awayplayersSeen:
                        awayplayersSeen.append(awayJump)


                    details = data[1].text
                elif 'End' in data[1].text:
                    eventType = 'End period'
                    details = data[1].text
            elif len(data) == 6:
                homeScore, awayScore = convertTextToScores(data[3].text)
                if len(data[1].text) > 1:
                    details = data[1].text
                    playTeamID = awayID
                    ind = 1
                else:
                    details = data[5].text
                    playTeamID = homeID
                    ind = 5
                # Event Types: ORb, Drb, Miss, Make, Jump, Foul, Ft, Turnover, Sub, Tech, Timeout, Kick
                if 'misses' in details:
                    links = data[ind].find_all('a')
                    player = URLtoID(links[0]['href'])
                    result = 'miss'
                    if len(links) == 2:
                        block = URLtoID(links[1]['href'])
                    if '3-pt' in details:
                        pts = 0
                        eventType = '3pt'
                    elif '2-pt' in details:
                        pts = 0
                        eventType = '2pt'
                    elif 'free throw' in details:
                        pts = 1
                        ftNumInfo = details[details.rfind('of') - 2:]
                        ftNum = ftNumInfo[0]
                        ftTotal = ftNumInfo[-1]
                        eventType = 'ft'

                    # check for players seen for change of quarter substitutions
                    if ind == 5:
                        if player not in homeplayersSeen:
                            homeplayersSeen.append(player)
                        if block:
                            if block not in awayplayersSeen:
                                awayplayersSeen.append(block)
                    if ind == 1:
                        if player not in awayplayersSeen:
                            awayplayersSeen.append(player)
                        if block:
                            if block not in homeplayersSeen:
                                homeplayersSeen.append(block)

                elif 'makes' in details:
                    links = data[ind].find_all('a')
                    player = URLtoID(links[0]['href'])
                    result = 'make'
                    if len(links) == 2:
                        assist = URLtoID(links[1]['href'])
                    if '3-pt' in details:
                        pts = 3
                        eventType = '3pt'
                    elif '2-pt' in details:
                        pts = 2
                        eventType = '2pt'
                    elif 'free throw' in details:
                        pts = 1
                        if 'technical' not in details:
                            ftNumInfo = details[details.rfind('of') - 2:]
                            ftNum = ftNumInfo[0]
                            ftTotal = ftNumInfo[-1]
                        else:
                            ftNum = 1
                            ftTotal = 1
                        eventType = 'ft'

                    # check for players seen for change of quarter substitutions
                    if ind == 5:
                        if player not in homeplayersSeen:
                            homeplayersSeen.append(player)
                        if assist:
                            if assist not in homeplayersSeen:
                                homeplayersSeen.append(assist)
                    if ind == 1:
                        if player not in awayplayersSeen:
                            awayplayersSeen.append(player)
                        if assist:
                            if assist not in awayplayersSeen:
                                awayplayersSeen.append(assist)

                elif 'Defensive rebound' in details:
                    if 'Team' in details:
                        player = playTeamID
                    else:
                        player = URLtoID(data[ind].find_all('a')[0]['href'])
                        # check for players seen for change of quarter substitutions
                        if ind == 5:
                            if player not in homeplayersSeen:
                                homeplayersSeen.append(player)
                        if ind == 1:
                            if player not in awayplayersSeen:
                                awayplayersSeen.append(player)

                    eventType = 'Defensive rebound'



                elif 'Offensive rebound' in details:
                    if 'Team' in details:
                        player = playTeamID
                    else:
                        player = URLtoID(data[ind].find_all('a')[0]['href'])

                        # check for players seen for change of quarter substitutions
                        if ind == 5:
                            if player not in homeplayersSeen:
                                homeplayersSeen.append(player)
                        if ind == 1:
                            if player not in awayplayersSeen:
                                awayplayersSeen.append(player)

                    eventType = 'Offensive rebound'



                elif 'Turnover by' in details:
                    if 'Team' in details:
                        player = playTeamID
                    else:
                        player = URLtoID(data[ind].find_all('a')[0]['href'])
                        # check for players seen for change of quarter substitutions
                        if ind == 5:
                            if player not in homeplayersSeen:
                                homeplayersSeen.append(player)
                        if ind == 1:
                            if player not in awayplayersSeen:
                                awayplayersSeen.append(player)

                    if 'steal' in details:
                        eventType = 'steal'
                        steal = URLtoID(data[ind].find_all('a')[1]['href'])
                        # check for players seen for change of quarter substitutions
                        if ind == 1:
                            if steal not in homeplayersSeen:
                                homeplayersSeen.append(steal)
                        if ind == 5:
                            if steal not in awayplayersSeen:
                                awayplayersSeen.append(steal)
                    else:
                        eventType = 'turnover'
                    reason = details[details.find('(')+1:-1]

                elif 'foul' in details:
                    eventType = 'foul'
                    if playTeamID == homeID:
                        playTeamID = awayID
                    else:
                        playTeamID = homeID

                    foul = URLtoID(data[ind].find_all('a')[0]['href'])
                    drawFoul = URLtoID(data[ind].find_all('a')[1]['href'])
                    player = foul

                    if 'Offensive' in details:
                        reason = 'Offensive'

                        if ind == 1:
                            if drawFoul not in homeplayersSeen:
                                homeplayersSeen.append(drawFoul)
                            if foul not in awayplayersSeen:
                                awayplayersSeen.append(foul)
                        if ind == 5:
                            if drawFoul not in awayplayersSeen:
                                awayplayersSeen.append(drawFoul)
                            if foul not in homeplayersSeen:
                                homeplayersSeen.append(foul)

                    elif 'Technical' in details:
                        reason = 'Technical'
                        if ind == 1:
                            if drawFoul not in homeplayersSeen:
                                homeplayersSeen.append(drawFoul)
                            if foul not in awayplayersSeen:
                                awayplayersSeen.append(foul)
                        if ind == 5:
                            if drawFoul not in awayplayersSeen:
                                awayplayersSeen.append(drawFoul)
                            if foul not in homeplayersSeen:
                                homeplayersSeen.append(foul)

                    else:
                        if 'Shooting' in details:
                            reason = 'Shooting'
                        elif 'Personal' in details:
                            reason = 'Personal'
                        elif 'Loose ball' in details:
                            reason = 'Loose ball'

                        if ind == 5:
                            if drawFoul not in homeplayersSeen:
                                homeplayersSeen.append(drawFoul)
                            if foul not in awayplayersSeen:
                                awayplayersSeen.append(foul)
                        if ind == 1:
                            if drawFoul not in awayplayersSeen:
                                awayplayersSeen.append(drawFoul)
                            if foul not in homeplayersSeen:
                                homeplayersSeen.append(foul)


                elif 'timeout' in details:
                    eventType = 'timeout'
                    if ind == 5:
                        player = homeID
                    elif ind == 1:
                        player = awayID

                elif 'Defensive three seconds' in details:
                    player = URLtoID(data[ind].find_all('a')[0]['href'])
                    eventType = 'turnover'

                #Gotta Fix substitutes during Quarters changes
                elif 'enters the game' in details:
                    links = data[ind].find_all('a')
                    player = URLtoID(links[0]['href'])
                    subIn = player
                    subOut = URLtoID(links[1]['href'])
                    eventType = 'substitution'
                    if ind == 1:
                        if subOut not in awayplayers:
                            if subOut not in awayplayersSeen:
                                awayplayersSeen.append(subOut)
                            if None in awayplayers:
                                replacePlayer = None
                            else:
                                removablePlayers = set(awayplayers) - set(awayplayersSeen)
                                replacePlayer = list(removablePlayers)[0]
                            frameQ = frame[frame[2] == period]
                            col = None
                            for ind in range(15, 20):
                                if replacePlayer == frameQ.iloc[0, ind]:
                                    col = ind
                                    break
                            frameQ.loc[:, ind] = subOut
                            awayplayers[ind - 15] = subOut
                        if subIn in awayplayers:
                            if subOut not in awayplayersSeen:
                                awayplayersSeen.append(subOut)
                            removablePlayers = set(awayplayersSeen) - set(awayplayers)
                            if removablePlayers:
                                replacePlayer = list(removablePlayers)[0]
                            else:
                                replacePlayer = None
                            frameQ = frame[frame[2] == period]
                            col = None
                            for ind in range(15, 20):
                                if subIn == frameQ.iloc[0, ind]:
                                    col = ind
                                    break
                            frameQ.loc[:, ind] = replacePlayer
                            awayplayers[ind - 15] = replacePlayer
                        if subOut not in awayplayersSeen:
                            awayplayersSeen.append(subOut)
                        awayplayers[awayplayers.index(subOut)] = subIn
                        awayplayersSeen[awayplayersSeen.index(subOut)] = subIn

                    elif ind == 5:
                        if subOut not in homeplayers:
                            if subOut not in homeplayersSeen:
                                homeplayersSeen.append(subOut)
                            if None in homeplayers:
                                replacePlayer = None
                            else:
                                removablePlayers = set(homeplayers) - set(homeplayersSeen)
                                replacePlayer = list(removablePlayers)[0]
                            frameQ = frame[frame[2] == period]
                            col = None
                            for ind in range(10, 15):
                                if replacePlayer == frameQ.iloc[0, ind]:
                                    col = ind
                                    break
                            frameQ.loc[:, ind] = subOut
                            homeplayers[ind - 10] = subOut
                        if subIn in homeplayers:
                            if subOut not in homeplayersSeen:
                                homeplayersSeen.append(subOut)
                            removablePlayers = set(homeplayersSeen) - set(homeplayers)
                            if removablePlayers:
                                replacePlayer = list(removablePlayers)[0]
                            else:
                                replacePlayer = None
                            frameQ = frame[frame[2] == period]
                            col = None
                            for ind in range(10, 15):
                                if subIn == frameQ.iloc[0, ind]:
                                    col = ind
                                    break
                            frameQ.loc[:, ind] = replacePlayer
                            homeplayers[ind - 10] = replacePlayer
                        if subOut not in homeplayersSeen:
                            homeplayersSeen.append(subOut)
                        homeplayers[homeplayers.index(subOut)] = subIn
                        homeplayersSeen[homeplayersSeen.index(subOut)] = subIn

                homeScore, awayScore = convertTextToScores(data[3].text)
            timeRemaining = timeToSeconds(data[0].text)
            timeElapsed = periodLength - timeRemaining
            playLength = LastPlay - timeRemaining

            LastPlay = timeRemaining
            framerow = [gameID, playID, period, timeRemaining, timeElapsed, playLength, homeID, awayID, homeScore,
                        awayScore] + homeplayers + awayplayers + [playTeamID, eventType, player, opponent,
                                                                  assist, block, steal, pts, result, homeJump, awayJump,
                                                                  possession, subIn, subOut, ftNum, ftTotal, drawFoul,
                                                                  foul, reason,
                                                                  details]
            frame = frame.append(pd.Series(framerow), ignore_index=True)



        # #############
        # reset vars #
        ##############
        playID += 1
        timeRemaining = None
        timeElapsed = None
        playLength = None
        playTeamID = None
        eventType = None
        player = None
        opponent = None
        assist = None
        block = None
        steal = None
        pts = 0
        result = None
        homeJump = None
        awayJump = None
        possession = None
        subIn = None
        subOut = None
        ftNum = None
        ftTotal = None
        drawFoul = None
        foul = None
        reason = None
        details = ''

        ##################
        # End reset vars #
        ##################
    frame.columns = header
    return frame


#scrapes the refs for the game and returns a pandas dataframe
#returns in the form of [GameID,refID, refID, refID]
def getRefs(soup):
    frame = pd.DataFrame()

    table = soup.find_all('table', class_='margin_top small_text')[0]
    row = table.find_all('tr')[0]
    row_data = row.find_all('a')
    for d in row_data:
        frame = frame.append(pd.Series([None, URLtoID(d['href']), d.text]), ignore_index=True)
    frame.columns = ['GameID', 'RefID', 'Name']
    return frame


# scrapes the shot chart for the game and returns a pandas dataframe
# returns in the form of [GameID, PlayerID, TeamID, Time, Xloc, Yloc, Shot Type (3/2), Result (make=1,miss=0)]
# May not be done from BBref due to the way the information is displayed possible from JSON on NBA.com
def getShotCharts(soup):
    pass


# takes in a link for the box score and stores all values in a SQL database
def scrapeBoxScore(link):
    # print('start scraping')
    r = requests.get(link)
    soupBS = BeautifulSoup(r.text)

    refs = getRefs(soupBS)
    refs.loc[:, 'GameID'] = URLtoID(link)
    # print('refs:')
    #print(refs)

    players, teams = getBoxScoreStats(soupBS)
    players.loc[:, 'GameID'] = URLtoID(link)
    teams.loc[:, 'GameID'] = URLtoID(link)
    # print('players and teams:')
    #print(players)
    #print(teams)


    ff = getFourFactors(soupBS)
    ff.loc[:, 'GameID'] = URLtoID(link)
    # print('4factors:')
    #print(ff)


    scores = getFinalScores(soupBS)
    scores.loc[:, 'GameID'] = URLtoID(link)
    # print('scores:')
    #print(scores)


    length = getGameLength(soupBS)
    length.loc[:, 'GameID'] = URLtoID(link)
    # print('length:')
    #print(length)


    pbp = BoxScoreURLtoPBP(link)

    r = requests.get(pbp)
    soupPBP = BeautifulSoup(r.text)

    home, away = getTeamID(scores)
    starters = getStarters(players, home, away)

    Play_by_Play = getPlayByPlay(soupPBP, starters, home, away)
    Play_by_Play.loc[:, 'GameID'] = URLtoID(link)
    # print('play by play:')
    #print(Play_by_Play)

    return refs, players, teams, ff, scores, length, Play_by_Play


refs = pd.DataFrame()
playerStats = pd.DataFrame()
teamStats = pd.DataFrame()
fourFactors = pd.DataFrame()
finalScores = pd.DataFrame()
gameLengths = pd.DataFrame()
pbp = pd.DataFrame()

failures = []
failcount = 1
bs = pickle.load(open("boxscores.p", "rb"))
for i, b in enumerate(bs):
    # print(i)
    #print(b)
    try:
        refBS, playerBS, teamsBS, ffBS, scoresBS, lengthBS, PBPBS = scrapeBoxScore(b)
        print('scrape complete')
        refs = refs.append(refBS, ignore_index=True)
        playerStats = playerStats.append(playerBS, ignore_index=True)
        teamStats = teamStats.append(teamsBS, ignore_index=True)
        fourFactors = fourFactors.append(ffBS, ignore_index=True)
        finalScores = finalScores.append(scoresBS, ignore_index=True)
        gameLengths = gameLengths.append(lengthBS, ignore_index=True)
        pbp = pbp.append(PBPBS, ignore_index=True)
        print('append complete')

        pickle.dump(refs, open("Scrape Results/refs.p", "wb"))
        pickle.dump(playerStats, open("Scrape Results/playerStats.p", "wb"))
        pickle.dump(teamStats, open("Scrape Results/teamStats.p", "wb"))
        pickle.dump(fourFactors, open("Scrape Results/fourFactors.p", "wb"))
        pickle.dump(finalScores, open("Scrape Results/finalScores.p", "wb"))
        pickle.dump(gameLengths, open("Scrape Results/gameLengths.p", "wb"))
        pickle.dump(pbp, open("Scrape Results/pbp.p", "wb"))

        print('dump complete')
        if i + 1 % 1200 == 0:
            R = random.randint(600, 900)
            print('wait: ', R)
            time.sleep(R)
        else:
            R = random.randint(5, 15)
            print('wait: ', R)
            time.sleep(R)

    except:
        print('Failed on Boxscore: ', b)
        print('{0} failures so so far'.format(failcount))
        failures.append(b)
        failcount += 1
        pickle.dump(failures, open("Scrape Results/fail.p", "wb"))