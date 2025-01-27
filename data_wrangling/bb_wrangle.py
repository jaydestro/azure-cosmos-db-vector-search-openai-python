"""
Usage:
  python bb_wrangle.py prune_people
  python bb_wrangle.py prune_player_positions
  python bb_wrangle.py prune_player_teams
  python bb_wrangle.py prune_batters
  python bb_wrangle.py prune_pitchers
  -
  python bb_wrangle.py calc_player_positions
  python bb_wrangle.py calc_player_teams
  python bb_wrangle.py calc_batters_stats
  python bb_wrangle.py calc_pitchers_stats
  -
  python bb_wrangle.py build_documents
  -
  python bb_wrangle.py add_embeddings_to_documents
  -
  python bb_wrangle.py scan_embeddings
  -
  python bb_wrangle.py csv_reports
Options:
  -h --help     Show this screen.
  --version     Show version.
"""

# Chris Joakim, Microsoft, 2023

import json
import os
import sys
import traceback

import pandas as pd

from docopt import docopt

from pysrc.aibundle import Bytes, CogSvcsClient, Counter, Env, FS, Mongo, OpenAIClient, Storage, System

EXPECTED_EMBEDDINGS_ARRAY_LENGTH = 1536
ALGORITHM_RAW_NUMBERS =  'raw-numbers'
ALGORITHM_BINNED_TEXT =  'binned-text'

def print_options(msg):
    print(msg)
    arguments = docopt(__doc__, version='1.0.0')
    print(arguments)

def prune_people():
    print('=== prune_people')
    df = people_df()
    include_cols = 'playerID,birthYear,birthCountry,deathYear,nameFirst,nameLast,weight,height,bats,throws,debut,finalGame'.split(',')
    df2 = include_only_cols(df, include_cols)
    df2.sort_values(by=['playerID'])
    write_df(df2, 'tmp/people.csv')
    rows = FS.read_csv_as_dicts('tmp/people.csv')
    FS.write_json(rows, 'tmp/people.json')

def prune_player_positions():
    print('=== prune_player_positions')
    df = appearances_df()
    include_cols = 'playerID,G_all,G_p,G_c,G_1b,G_2b,G_3b,G_ss,G_lf,G_cf,G_rf,G_dh'.split(',')
    df2 = include_only_cols(df, include_cols)
    df2.sort_values(by=['playerID'])
    write_df(df2, 'tmp/player_positions_pruned.csv')
    grouped = df2.groupby(['playerID'])
    grouped.sum().to_csv('tmp/player_positions.csv')
    rows = FS.read_csv_as_dicts('tmp/player_positions.csv')
    FS.write_json(rows, 'tmp/player_positions.json')

def prune_player_teams():
    print('=== prune_player_teams')
    df = appearances_df()
    include_cols = 'yearID,teamID,playerID,G_all'.split(',')
    df2 = include_only_cols(df, include_cols)
    df2.sort_values(by=['playerID'])
    write_df(df2, 'tmp/player_teams.csv')
    rows = FS.read_csv_as_dicts('tmp/player_teams.csv')
    FS.write_json(rows, 'tmp/player_teams.json')

def prune_batters():
    print('=== prune_batters')
    df = batters_df()
    include_cols = 'playerID,G,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,SO,IBB,HBP,SF'.split(',')
    df2 = include_only_cols(df, include_cols)
    df2.sort_values(by=['playerID'])
    write_df(df2, 'tmp/batters_pruned.csv')
    grouped = df2.groupby(['playerID'])
    grouped.sum().to_csv('tmp/batters.csv')
    rows = FS.read_csv_as_dicts('tmp/batters.csv')
    FS.write_json(rows, 'tmp/batters.json')

def prune_pitchers():
    print('=== prune_pitchers')
    df = pitchers_df()
    # playerID,yearID,stint,teamID,lgID,W,L,G,GS,CG,SHO,SV,IPouts,H,ER,HR,BB,SO,BAOpp,ERA,IBB,WP,HBP,BK,BFP,GF,R,SH,SF,GIDP
    include_cols = 'playerID,W,L,G,GS,CG,SHO,SV,IPouts,H,ER,HR,BB,SO,BAOpp,ERA,IBB,WP,HBP,BK'.split(',')
    df2 = include_only_cols(df, include_cols)
    df2.sort_values(by=['playerID'])
    write_df(df2, 'tmp/pitchers_pruned.csv')
    grouped = df2.groupby(['playerID'])
    grouped.sum().to_csv('tmp/pitchers.csv')
    rows = FS.read_csv_as_dicts('tmp/pitchers.csv')
    FS.write_json(rows, 'tmp/pitchers.json')

def calc_player_positions():
    print('=== calc_player_positions')
    infile = 'tmp/player_positions.csv'
    outfile = 'tmp/player_positions.json'
    rows = FS.read_csv_as_dicts(infile)
    player_dict = {}

    position_cols = 'G_p,G_c,G_1b,G_2b,G_3b,G_ss,G_lf,G_cf,G_rf,G_dh'.split(',')
    for row_idx, player in enumerate(rows):
        player['primary_position'] = '?'
        pid = player['playerID']
        games = float(player['G_all'])
        player_dict[pid] = player
        greatest = 0.0
        for position_col in position_cols:
            position = position_col.split('_')[1]
            position_percent_col = f"{position}_percent"
            n = float(player[position_col])
            player[position_percent_col] = n / games
            if n > greatest:
                greatest = n
                player['primary_position'] = position.upper()
        if verbose():
            print(json.dumps(player, sort_keys=False, indent=2))

    FS.write_json(player_dict, outfile)

def calc_player_teams():
    print('=== calc_player_teams')
    infile = 'tmp/player_teams.csv'
    outfile = 'tmp/player_teams_calc.json'
    rows = FS.read_csv_as_dicts(infile)
    player_dict = {}

    # First collect the playerDict
    for row_idx, player in enumerate(rows):
        # {'yearID': '2022', 'teamID': 'BAL', 'playerID': 'zimmebr02', 'G_all': '15'}
        pid = player['playerID']
        tid = player['teamID']
        game_count = int(float(player['G_all']))
        if pid in player_dict.keys():
            player_info = player_dict[pid]
            player_info['total_games'] = player_info['total_games'] + game_count
            if tid in player_info['teams'].keys():
                player_info['teams'][tid] = player_info['teams'][tid] + game_count
            else:
                player_info['teams'][tid] = game_count
        else:
            player_info = {}
            player_info['total_games'] = game_count
            player_info['teams'] = {}
            player_info['teams'][tid] = game_count
            player_dict[pid] = player_info
    # Identify the primary team for each player
    for pid in sorted(player_dict.keys()):
        player_info, highest = player_dict[pid], 0
        for tid in player_info['teams'].keys():
            games = player_info['teams'][tid]
            if games > highest:
                highest = games
                player_info['primary_team'] = tid

    FS.write_json(player_dict, outfile)

def calc_batters_stats():
    print('=== calc_batters_stats')
    infile  = 'tmp/batters.json'
    outfile = 'tmp/batters_calc.json'
    batters_list = FS.read_json(infile)
    output_dict = {}
    calculated_count = 0

    for batter in batters_list:
        try:
            pid = batter['playerID']
            calculated = {}
            batter['calculated'] = calculated
            output_dict[pid] = batter
            ab = float_value(batter, 'AB', 0.0)
            if ab > 0.0:
                # playerID,G,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,SO,IBB,HBP,SF
                calculated['runs_per_ab'] = float_value(batter, 'R', 0.0) / ab
                calculated['batting_avg'] = float_value(batter, 'H', 0.0) / ab
                calculated['2b_avg']  = float_value(batter, '2B', 0.0) / ab
                calculated['3b_avg']  = float_value(batter, '3B', 0.0) / ab
                calculated['hr_avg']  = float_value(batter, 'HR', 0.0) / ab
                calculated['rbi_avg'] = float_value(batter, 'RBI', 0.0) / ab
                calculated['bb_avg']  = float_value(batter, 'BB', 0.0) / ab
                calculated['so_avg']  = float_value(batter, 'SO', 0.0) / ab
                calculated['ibb_avg'] = float_value(batter, 'IBB', 0.0) / ab
                calculated['hbp_avg'] = float_value(batter, 'HBP', 0.0) / ab
                calculated_count += 1
        except Exception as e:
            print(f"Exception on batter: {batter}")
            print(traceback.format_exc())
        if verbose():
            print(json.dumps(batter, sort_keys=False, indent=2))

    print(f'batters count:    {len(batters_list)}')
    print(f'calculated count: {calculated_count}')
    FS.write_json(output_dict, outfile)

def calc_pitchers_stats():
    print('=== calc_pitchers_stats')
    infile  = 'tmp/pitchers.json'
    outfile = 'tmp/pitchers_calc.json'
    pitchers_list = FS.read_json(infile)
    calculated_count = 0
    output_dict = {}

    for pitcher in pitchers_list:
        try:
            pid = pitcher['playerID']
            calculated = {}
            pitcher['calculated'] = calculated
            output_dict[pid] = pitcher
            pid  = pitcher['playerID']
            w    = float_value(pitcher, 'W', 0.0)
            l    = float_value(pitcher, 'L', 0.0)
            er   = float_value(pitcher, 'ER', 0.0)
            gs   = float_value(pitcher, 'GS', 0.0)
            cg   = float_value(pitcher, 'CG', 0.0)
            sho  = float_value(pitcher, 'SHO', 0.0)
            hits = float_value(pitcher, 'H', 0.0)
            bb   = float_value(pitcher, 'BB', 0.0)
            so   = float_value(pitcher, 'SO', 0.0)
            ipo  = float_value(pitcher, 'IPouts', 0.0)
            hr   = float_value(pitcher, 'HR', 0.0)
            hbp  = float_value(pitcher, 'HBP', 0.0)
            if ipo > 0.0:
                fge = ipo / 27.0
                official_at_bats = ipo + hits
                all_at_bats = official_at_bats + bb + hbp

                calculated['full_games_pitched_equiv'] = fge
                calculated['era'] = er / fge
                calculated['opp_batting_avg'] = hits / official_at_bats
                calculated['bb_pct']  = bb / all_at_bats
                calculated['so_pct']  = so / all_at_bats
                calculated['hbp_pct'] = hbp / all_at_bats
                calculated['hr_pct']  = hr / all_at_bats

                if (w + l) > 0.0:
                    calculated['win_pct'] = w / (w + l)
                    calculated['sho_pct'] = sho / (w + l)
                else:
                    calculated['win_pct'] = 0.0
                    calculated['sho_pct'] = 0.0
                if gs > 0.0:
                    calculated['cg_pct'] = cg / gs
                else:
                    calculated['cg_pct'] = 0.0
                calculated_count += 1
        except Exception as e:
            print(f"Exception on pitcher: {pitcher}")
            print(traceback.format_exc())

    print(f'pitcher count:    {len(pitchers_list)}')
    print(f'calculated count: {calculated_count}')
    FS.write_json(output_dict, outfile)

def build_documents():
    print('=== build_documents')
    players_list  = FS.read_json('tmp/people.json')
    batters_dict  = FS.read_json('tmp/batters_calc.json')
    pitchers_dict = FS.read_json('tmp/pitchers_calc.json')
    player_teams_dict = FS.read_json('tmp/player_teams_calc.json')
    player_positions_dict = FS.read_json('tmp/player_positions.json')
    print(f'players count:      {len(players_list)}')
    print(f'batters count:      {len(batters_dict.keys())}')
    print(f'pitchers count:     {len(pitchers_dict.keys())}')
    print(f'player teams count: {len(player_teams_dict.keys())}')
    documents = {}
    outfile = '../data/wrangled/documents.json'
    pruned_player_attrs  = 'x'.split(',')
    pruned_pitcher_attrs = 'playerID,dog'.split(',')
    pruned_batter_attrs  = 'playerID,cat'.split(',')

    for player in players_list:
        pid = player['playerID']
        if pid in player_teams_dict.keys():
            documents[pid] = player
            player['teams'] = player_teams_dict[pid]
            pitching_ipo, batting_hits = 0, 0

            if pid in pitchers_dict.keys():
                player['pitching'] = pitchers_dict[pid]
                pitching_ipo = int(float(player['pitching']['IPouts']))
                player['category'] = 'pitcher'
                for attr in pruned_pitcher_attrs:
                     if attr in player['pitching'].keys():
                        del player['pitching'][attr]

            if pid in player_positions_dict.keys():
                pp = player_positions_dict[pid]
                player['primary_position'] = pp['primary_position']
            else:
                player['primary_position'] = '?'

            if pid in batters_dict.keys():
                player['batting'] = batters_dict[pid]
                batting_hits = int(float(player['batting']['H']))
                player['category'] = 'fielder'
                for attr in pruned_batter_attrs:
                    if attr in player['batting'].keys():
                        del player['batting'][attr]

            if 'pitching' in player.keys():
                if 'batting' in player.keys():
                    # compare the primary metric for each category if the player
                    # is BOTH a pitcher and a batter/fielder.  see aardsda01.
                    if pitching_ipo > batting_hits:  
                        player['category'] = 'pitcher'
                    else:
                        player['category'] = 'fielder'
            for attr in pruned_player_attrs:
                if attr in player.keys():
                    del player[attr]

            refine_values(player)
            calculate_embeddings_string_value(player, ALGORITHM_BINNED_TEXT)

    print(f'documents count: {len(documents.keys())}')
    FS.write_json(documents, outfile)

def refine_values(player):
    try:
        player['debut_year'] = 0
        player['final_year'] = 0
        player['birthYear']  = int(float(player['birthYear']))
        player['weight']     = int(float(player['weight']))
        player['height']     = int(float(player['height']))
        player['debut_year'] = int(player['debut'][0:4])
        player['final_year'] = int(player['finalGame'][0:4])
    except:
        pass

def calculate_embeddings_string_value(player, algorithm):
    if algorithm == ALGORITHM_BINNED_TEXT:
        calculate_embeddings_string_value_with_binned_text(player)
    else:
        calculate_embeddings_string_value_with_raw_numbers(player)

def calculate_embeddings_string_value_with_binned_text(player):
    try:
        values = []
        category = player['category']
        player['embeddings_str'] = ''
        values.append(category)
        values.append(labeled_text_value('primary_position', player['primary_position']))
        values.append(labeled_text_value('total_games', player['teams']['total_games']))
        values.append(labeled_text_value('bats', player['bats']))
        values.append(labeled_text_value('throws', player['throws']))

        if category == 'pitcher':
            values.append(labeled_text_value('wins', player['pitching']['W']))
            values.append(labeled_text_value('losses', player['pitching']['L']))
            calculated = player['pitching']['calculated']
            values.append(labeled_floating_text_value('full_games_pitched_equiv', calculated['full_games_pitched_equiv'], 1)) 
            values.append(labeled_floating_text_value('era', calculated['era'], 1000)) 
            values.append(labeled_binned_pct_text_value(calculated, 'opp_batting_avg', 1000))
            values.append(labeled_binned_pct_text_value(calculated, 'so_pct', 1000)) 
            values.append(labeled_binned_pct_text_value(calculated, 'bb_pct', 1000)) 
            values.append(labeled_binned_pct_text_value(calculated, 'hbp_pct', 1000)) 
            values.append(labeled_binned_pct_text_value(calculated, 'hr_pct', 1000))
            values.append(labeled_binned_pct_text_value(calculated, 'win_pct', 100)) 
            values.append(labeled_binned_pct_text_value(calculated, 'sho_pct', 100)) 
            values.append(labeled_binned_pct_text_value(calculated, 'cg_pct', 100)) 
        else:
            values.append(labeled_text_value('hits', player['batting']['H']))
            values.append(labeled_text_value('hr', player['batting']['HR']))
            calculated = player['batting']['calculated']
            values.append(labeled_binned_pct_text_value(calculated, 'batting_avg', 1000))
            values.append(labeled_binned_pct_text_value(calculated, 'runs_per_ab', 1000)) 
            values.append(labeled_binned_pct_text_value(calculated, '2b_avg', 1000))
            values.append(labeled_binned_pct_text_value(calculated, '3b_avg', 1000)) 
            values.append(labeled_binned_pct_text_value(calculated, 'hr_avg', 1000)) 
            values.append(labeled_binned_pct_text_value(calculated, 'rbi_avg', 1000)) 
            values.append(labeled_binned_pct_text_value(calculated, 'bb_avg', 1000))
            values.append(labeled_binned_pct_text_value(calculated, 'so_avg', 1000)) 
            values.append(labeled_binned_pct_text_value(calculated, 'ibb_avg', 1000)) 
            values.append(labeled_binned_pct_text_value(calculated, 'hbp_avg', 1000)) 

        player['embeddings_str'] = ' '.join(values)
    except Exception as e:
        print(f"Exception on player: {player}")
        print(traceback.format_exc())
        return None

def labeled_text_value(stat, value):
    try:
        s = str(stat).strip()
        v = str(value).strip()
        return f'{s}_{v}'.lower()
    except Exception as e:
        print(f"Exception in labeled_text_value: {stat} {value}")
        print(traceback.format_exc())
        return ''

def labeled_floating_text_value(stat, value, multiplier):
    """ 
    for a given set of args 'era', '4.27299703264095', and multiplier 1000
    return 'era_4273'
    """
    try:
        s = str(stat).strip()
        int_value = int(round(float(value) * float(multiplier)))  
        return f'{s}_{int_value}'.strip().lower()
    except Exception as e:
        print(f"Exception in labeled_floating_text_value: {stat} {value} {multiplier}")
        print(traceback.format_exc())
        return ''

def labeled_binned_pct_text_value(values_dict, stat, bin_factor):
    """
    for a values dict with stat/key "so_pct" with value 0.22576361221779548 and bin factor 100
    return the string 'so_pct_23' by binning the rounded percent value.
    bin_factor value is expected to be 10, 100, 1000, etc.
    """
    s = str(stat).strip()
    bin_range = range(bin_factor - 1)
    try:
        if stat not in values_dict.keys():
            return ''
        int_value = int(round(float(values_dict[stat]) * float(bin_factor)))
        tier_name = '?'
        for tier in bin_range:
            if int_value >= tier:
                tier_name = str(tier)
        return f'{s}_{tier_name}'.strip().lower()
    except Exception as e:
        print(f"Exception in labeled_binned_pct_text_value: {values_dict} {stat}")
        print(traceback.format_exc())
        return f'{s}_??'.lower()

def calculate_embeddings_string_value_with_raw_numbers(player):
    try:
        values = []
        category = player['category']
        player['embeddings_str'] = ''
        values.append(category)
        if category == 'pitcher':
            values.append('0')
        else:
            values.append('1')
        values.append(str(player['primary_position'])) 
        values.append(str(player['teams']['total_games']))
        values.append(player['bats'].lower())
        values.append(player['throws'].lower())

        if category == 'pitcher':
            # values.append(str(player['pitching']['G']))
            values.append(str(player['pitching']['W']))
            values.append(str(player['pitching']['L']))
            calculated = player['pitching']['calculated']
            values.append(str(calculated['full_games_pitched_equiv']))
            values.append(str(calculated['era']))
            values.append(str(calculated['opp_batting_avg']))
            values.append(str(calculated['so_pct']))
            values.append(str(calculated['bb_pct']))
            values.append(str(calculated['hbp_pct']))
            values.append(str(calculated['hr_pct']))
            values.append(str(calculated['win_pct']))
            values.append(str(calculated['sho_pct']))
            values.append(str(calculated['cg_pct']))
        else:
            values.append(str(player['batting']['H']))
            values.append(str(player['batting']['HR']))
            calculated = player['batting']['calculated']
            values.append(str(calculated['batting_avg']))
            values.append(str(calculated['runs_per_ab']))
            values.append(str(calculated['2b_avg']))
            values.append(str(calculated['3b_avg']))
            values.append(str(calculated['hr_avg']))
            values.append(str(calculated['rbi_avg']))
            values.append(str(calculated['bb_avg']))
            values.append(str(calculated['so_avg']))
            values.append(str(calculated['ibb_avg']))
            values.append(str(calculated['hbp_avg']))
        player['embeddings_str'] = ' '.join(values)
    except Exception as e:
        print(f"Exception on player: {player}")
        print(traceback.format_exc())
        return None

def add_embeddings():
    print(f'=== add_embeddings')
    infile  = '../data/wrangled/documents.json'
    outfile = '../data/wrangled/documents_with_embeddings.json'
    oaic = create_azure_oai_client()
    print(json.dumps(oaic.get_config(), sort_keys=False, indent=2))

    documents = FS.read_json(infile)
    for idx, pid in enumerate(sorted(documents.keys())):
        if idx < 100_000:
            print(f'adding embedding for: {pid}')
            doc = documents[pid]
            try:
                doc['embeddings'] = []
                doc = documents[pid]
                estr = doc['embeddings_str']
                if len(estr) > 0:
                    embed = oaic.get_embedding(estr)
                    if embed is not None:
                        doc['embeddings'] = embed
            except Exception as e:
                print(f"Exception on doc: {doc}")
                print(traceback.format_exc())

    FS.write_json(documents, outfile)

def create_azure_oai_client():
    config = {}
    config['type'] = 'azure'
    config['url']  = os.environ['AZURE_OPENAI_URL']
    config['key']  = os.environ['AZURE_OPENAI_KEY1']
    config['api_version'] = '2023-05-15'  # <-- subject to change
    print('create_azure_oai_client, config: {}'.format(json.dumps(config)))
    return OpenAIClient(config)

def scan_embeddings():
    print(f'=== scan_embeddings')
    infile = '../data/wrangled/documents_with_embeddings.json'
    documents = FS.read_json(infile)
    count = len(documents.keys())
    with_count, without_count = 0, 0
    for pid in sorted(documents.keys()):
        doc = documents[pid]
        embeddings = doc['embeddings']
        if len(embeddings) == EXPECTED_EMBEDDINGS_ARRAY_LENGTH:
            with_count += 1
            print(f'{pid}: present {len(embeddings)}')
        else:
            without_count += 1
            print(f'{pid}: absent {len(embeddings)}')
    print(f'documents count: {count}')
    print(f'with_count: {with_count}')
    print(f'without_count: {without_count}')

def csv_reports():
    print(f'=== csv_reports')
    infile = '../data/wrangled/documents_with_embeddings.json'
    documents = FS.read_json(infile)
    pitcher_rows = []
    fielder_rows = []

    # construct and add the csv header rows for the two output files.
    common_cols  = 'category,category_code,primary_position,total_games,bats,throws'
    pitcher_cols = 'W,L,full_games_pitched_equiv,era,opp_batting_avg,so_pct,bb_pct,hbp_pct,hr_pct,win_pct,sho_pct,cg_pct'
    fielder_cols = 'H,HR,batting_avg,runs_per_ab,2b_avg,3b_avg,hr_avg,rbi_avg,bb_avg,so_avg,ibb_avg,hbp_avg'
    pitcher_rows.append(f'{common_cols},{pitcher_cols}')
    fielder_rows.append(f'{common_cols},{fielder_cols}')

    for pid in sorted(documents.keys()):
        player = documents[pid]
        cat = player['category']
        if cat == 'pitcher':
            pitcher_rows.append(player['embeddings_str'])
        else:
            fielder_rows.append(player['embeddings_str'])

    FS.write_lines(pitcher_rows, '../data/wrangled/pitchers.csv')
    FS.write_lines(fielder_rows, '../data/wrangled/fielders.csv')

def float_value(dictionary: dict, key: str, default_value: float) -> float:
    try:
        return float(dictionary[key])
    except:
        return float(default_value)

def appearances_df():
    infile = '../data/seanhahman-baseballdatabank-2023.1/core/Appearances.csv'
    df = pd.read_csv(infile)
    df = df.dropna()
    if verbose():
        cols = list(df.columns.values)
        cols_str = ",".join(cols)
        print(f"appearances_df shape:   {df.shape}")
        print(f"appearances_df columns: {cols_str}")
    return df

def people_df():
    infile = '../data/seanhahman-baseballdatabank-2023.1/core/People.csv'
    df = pd.read_csv(infile)
    if verbose():
        cols = list(df.columns.values)
        cols_str = ",".join(cols)
        print(f"people_df shape:   {df.shape}")
        print(f"people_df columns: {cols_str}")
    return df

def batters_df():
    infile = '../data/seanhahman-baseballdatabank-2023.1/core/Batting.csv'
    df = pd.read_csv(infile)
    if verbose():
        cols = list(df.columns.values)
        cols_str = ",".join(cols)
        print(f"batters_df shape:   {df.shape}")
        print(f"batters_df columns: {cols_str}")
    return df

def pitchers_df():
    infile = '../data/seanhahman-baseballdatabank-2023.1/core/Pitching.csv'
    df = pd.read_csv(infile)
    if verbose():
        cols = list(df.columns.values)
        cols_str = ",".join(cols)
        print(f"pitchers_df shape:   {df.shape}")
        print(f"pitchers_df columns: {cols_str}")
    return df

def include_only_cols(df, cols_to_keep):
    col_names = list(df.columns.values)
    cols_to_delete = []
    for col in col_names:
        if col not in cols_to_keep:
            cols_to_delete.append(col)
    return df.drop(cols_to_delete, axis=1)

def write_df(df, outfile):
    df.to_csv(outfile, index=False)
    print(f"file written: {outfile}")
    if verbose():
        cols = list(df.columns.values)
        cols_str = ",".join(cols)
        print(f"df shape: {df.shape}, cols: {cols_str}")

def verbose():
    for arg in sys.argv:
        if arg == '--verbose':
            return True
    return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            func = sys.argv[1].lower()
            if func == 'prune_people':
                prune_people()
            elif func == 'prune_player_positions':
                prune_player_positions()
            elif func == 'prune_player_teams':
                prune_player_teams()
            elif func == 'prune_batters':
                prune_batters()
            elif func == 'prune_pitchers':
                prune_pitchers()
            elif func == 'calc_player_positions':
                calc_player_positions()
            elif func == 'calc_player_teams':
                calc_player_teams()
            elif func == 'calc_batters_stats':
                calc_batters_stats()
            elif func == 'calc_pitchers_stats':
                calc_pitchers_stats()
            elif func == 'build_documents':
                build_documents()
            elif func == 'add_embeddings_to_documents':
                add_embeddings()
            elif func == 'scan_embeddings':
                scan_embeddings()
            elif func == 'csv_reports':
                csv_reports()
            else:
                print_options('Error: invalid function: {}'.format(func))
        except Exception as e:
            print(str(e))
            print(traceback.format_exc())
    else:
        print_options('Error: no command-line function specified')
