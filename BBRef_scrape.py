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
            text = URLtoPID(link[0].get('href'))
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


#convert the player URL into a playerID
def URLtoPID(url):
    return url[url.rfind('/') + 1:url.find('.html')]


#convert the boxscore URL into a gameID
def URLtoGID(url):
    return url[url.rfind('/') + 1:url.find('.html')]


#Takes in a table in the form of HTML and returns a pandas dataframe
def tableToDF(table):
    pass


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
    header_lst.insert(0, 'GameID')  #gameID is added at the next level
    header_lst.append('H/A')

    rows = total_scores.find_all('tr')

    for i, r in enumerate(rows):
        data_row = rowToList(r)
        if data_row:
            if len(data_row) > 6:  #if there are multiple OTs, add up the points in OT need to add
                print(data_row)
            else:
                data_row[0] = convertNametoTID(data_row[0])
                data_row.insert(0, None)
                data_row.insert(6, 0)
                data_row.append(0)
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
#returns players in the form of [GameID, TeamID, PlayerID, MP, FG, FGA, FG%, 3P, 3PA, 3P%, FT, FTA, FT%, ORB, DRB, TRB, AST,
# STL, BLK, TOV, PF, PTS, +/-, TS%, eFG%, 3PAr, FTr, ORB%, DRB%, TRB%, AST%, STL%, BLK%, TOV%, USG%, ORtg,
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

#scrapes the time of the start of the game returns a time object
def getGameTime(soup):
    pass


#scrapes the length of the game and returns a time object
def getGameLength(soup):
    pass


#scrapes the play by play data and returns a pandas dataframe
#STILL NEEED TO FIGURE OUT WHAT FORM I WANT THIS IN
def getPlayByPlay(soup):
    pass


#scrapes the refs for the game and returns a pandas dataframe
#returns in the form of [GameID,refID, refID, refID]
def getRefs(soup):
    table = soup.find_all('table', class_='margin_top small_text')[0]
    row = table.find_all('tr')[0]
    row_data = r.find_all('td')
    for d in row_data:
        pass  # FINISH NEXT

# scrapes the shot chart for the game and returns a pandas dataframe
#returns in the form of [GameID, PlayerID, TeamID, Time, Xloc, Yloc, Shot Type (3/2), Result (make=1,miss=0)]
def getShotCharts(soup):
    pass


# takes in a link for the box score and stores all values in a SQL database
def scrapeBoxScore(link):
    pass


boxscores = pickle.load(open("boxscores.p", "rb"))
bs = boxscores[0]
print(bs)
r = requests.get(bs)
soup = BeautifulSoup(r.text)

refs = getRefs(soup)
# f = getBoxScoreStats(soup)
#f.loc[:, 'GameID'] = URLtoGID(bs)
#print(f)
