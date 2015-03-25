import time
from bs4 import BeautifulSoup
import pandas as pd
import requests
import pickle

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


#Converts a row of a table in HTML into a list
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


#################################################################################################################
#Helper functions above
#Scraping functions below
#################################################################################################################

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
            data_row[1] = convertNametoTID(data_row[1])
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
    h1 = starters[0]
    h2 = starters[1]
    h3 = starters[2]
    h4 = starters[3]
    h5 = starters[4]
    a1 = starters[5]
    a2 = starters[6]
    a3 = starters[7]
    a4 = starters[8]
    a5 = starters[9]
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
    reason = None
    details = ''

    periodLength = 720.0
    LastPlay = 720.0

    header = ['GameID', 'PlayID', 'Period', 'TimeRemaining', 'TimeElapsed', 'PlayLength', 'HomeTeamID', 'AwayTeamID',
              'HomeScore', 'AwayScore', 'H1', 'H2', 'H3', 'H4', 'H5', 'A1', 'A2', 'A3', 'A4', 'A5', 'PlayerTeamID',
              'EventType', 'PlayerID', 'OpponentID', 'Assist', 'Block', 'Steal', 'PTS', 'Result', 'HomeJump',
              'AwayJump',
              'Possession', 'SubIn', 'SubOut', 'ftNum', 'ftTotal', 'reason', 'details']
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
                    period += 1
                    if period > 4:
                        periodLength = 300.0
                    else:
                        periodLength = 720.0
                # Jump Ball
                elif 'Jump' in data[1].text:
                    links = data[1].find_all('a')
                    if len(links) == 3:
                        homeJump = URLtoID(links[0]['href'])
                        awayJump = URLtoID(links[1]['href'])
                        possession = URLtoID(links[2]['href'])
                    elif len(links) == 2:
                        homeJump = URLtoID(links[0]['href'])
                        awayJump = URLtoID(links[1]['href'])
                    details = data[1].text

            elif len(data) == 6:
                pass
            timeRemaining = timeToSeconds(data[0].text)
            timeElapsed = periodLength - timeRemaining
            playLength = LastPlay - timeRemaining

            LastPlay = timeRemaining
            framerow = [gameID, playID, period, timeRemaining, timeElapsed, playLength, homeID, awayID, homeScore,
                        awayScore, h1, h2, h3, h4, h5, a1, a2, a3, a4, a5, playTeamID, eventType, player, opponent,
                        assist, block, steal, pts, result, homeJump, awayJump, possession, subIn, subOut,
                        ftNum, ftTotal, reason, details]
            frame = frame.append(pd.Series(framerow), ignore_index=True)


        # #############
        # reset vars #
        ##############

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
        reason = None
        details = ''

        ##################
        # End reset vars #
        ##################


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
    pass


boxscores = pickle.load(open("boxscores.p", "rb"))
bs = 'http://www.basketball-reference.com/boxscores/200904010BOS.html'
pbp = BoxScoreURLtoPBP(bs)
SC = BoxScoreURLtoShotChart(bs)


# print(bs)
r = requests.get(pbp)
soup = BeautifulSoup(r.text)
Play_by_Play = getPlayByPlay(soup, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 1, 2)

# refs = getRefs(soup)
#refs.loc[:, 'GameID'] = URLtoID(bs)
#print(refs)

#players, teams = getBoxScoreStats(soup)
#players.loc[:, 'GameID'] = URLtoID(bs)
#teams.loc[:, 'GameID'] = URLtoID(bs)
#print(teams)
#print(players)

#ff = getFourFactors(soup)
#ff.loc[:, 'GameID'] = URLtoID(bs)
#print(ff)

#scores = getFinalScores(soup)
#scores.loc[:, 'GameID'] = URLtoID(bs)
#print(scores)

# length = getGameLength(soup)
#length.loc[:, 'GameID'] = URLtoID(bs)
#print(length)

