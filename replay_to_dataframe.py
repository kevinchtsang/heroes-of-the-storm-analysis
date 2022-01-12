# import
import ast
import re
import subprocess
import numpy as np
import math
import datetime
import pandas as pd

def closest_gameloop(gameloop, gameloop_list):
    # will find the largest element of gameloop_list less than gameloop
    if len(gameloop_list) == 1:
        gameloop_list = int(gameloop_list)
        if gameloop == gameloop_list:
            return gameloop
        elif gameloop < gameloop_list:
            return -1
        elif gameloop > gameloop_list:
            return int(gameloop_list)

    else:
        if gameloop in gameloop_list:
            return gameloop
        elif gameloop < min(gameloop_list):
            return -1
        else:
            closest_gameloop = -1
            for gl in gameloop_list:
                if gl < gameloop:
                    closest_gameloop = gl
                else:
                    break
            return closest_gameloop

class ReplayData:
    
    def __init__(self, file_names = ['gameevents', 'messageevents', 'trackerevents', 'attributeevents',
                                     'header', 'details', 'initdata'],
                near_distance = np.sqrt(20**2 * 2)):
        self.file_names = file_names
        self.near_distance = near_distance
        
        # look up
        self.hero_alt_names = {}
        self.hero_alt_names_inv = {}
        
        # dataframes
        self.data = {}
        self.game_events = {}
        self.tracker_events = {}
        self.player_info = {}
        self.unit_info = {}
        self.unit_info_short = {}
        self.hero_info_short = {}
        self.player_id_ls = {}
        self.unit_died = {}
        self.position_hero = {}
        self.hero_distances = {}
        self.building_position = {}
        
        # replay info
        self.map = ""
        self.stats_time_sec = None
        self.stats_gameloop = None
        self.timeUTC = ""
        
        # intialisation functions
        self.make_hero_alt_names()
        self.parse_files()
        self.make_player_info()
        self.make_unit_info()
        self.make_position_hero()
        self.make_exp_event()
        self.make_hero_distances()
        self.make_heroes_died_position()
        self.make_building_position()
    
    def make_hero_alt_names(self):
        # diablo heroes name lookup
        self.hero_alt_names = {
            "Sonya": "Barbarian",
            "Johnana": "Johnana",
            "Valla": "DemonHunter",
            "Kharazim": "Monk",
            "Xul": "Necromancer",
            "Nazeebo": "WitchDoctor",
            "Li-Ming": "Wizard",
            "LostViking": "LongboatRaidBoat"
        }

        self.hero_alt_names_inv = {v: k for k, v in self.hero_alt_names.items()}
        return None
    
    def parse(self, list_dict_str):
        # input: listDictStr, the string from read() on output.txt file from 
        #   command line using heroprotocol
        # output: listDict, list of dictionaries

        # remove \n in string
        list_dict_str = list_dict_str.replace('\n','')

        list_dict = []

        dict_start_idx = [m.start() for m in re.finditer("{'_bits'", list_dict_str)]
        list_dict_str_len = list_dict_str.count("{'_bits'")

        for i in range(list_dict_str_len):
            if i != list_dict_str_len - 1:
                temp_dict = ast.literal_eval(list_dict_str[dict_start_idx[i]: dict_start_idx[i+1]])
            else:
                temp_dict = ast.literal_eval(list_dict_str[dict_start_idx[i]:])

            list_dict.append(temp_dict)

        return list_dict
    
    def parse_files(self):
        # parse all txt files
        data = {}
        for file_name in self.file_names:

            f = open(file_name + '.txt', 'r')
            content = f.read()
#             print("loaded "+file_name)

            if file_name in ["gameevents", "trackerevents","messageevents"]:
                data[file_name] = self.parse(content)
            elif file_name == "initdata":
                data[file_name] = content
            else:
                data[file_name] = ast.literal_eval(content)
        
        if len(data["gameevents"]) == 0:
            raise ValueError("data missing")
        
        # update match data
        self.data = data
        self.game_events = data["gameevents"]
        self.tracker_events = data["trackerevents"]
        self.map = data["details"]["m_title"].decode("utf-8") 
        self.timeUTC = data["details"]["m_timeUTC"]
        
        for event in self.tracker_events:
            if event["_eventid"] == 11:
                # stats_m_time is in replay time
                self.stats_time_sec = event['m_instanceList'][0]['m_values'][0][0]['m_time']
                self.stats_gameloop = event['_gameloop']
                break
        
        return data
    
    def make_player_info(self):
        # define player info df
        player_info_df = pd.DataFrame(columns = ["player_id", "m_hero", "m_name", "m_teamId", "m_result"])

        i = 1
        for player in self.data["details"]["m_playerList"]:
            player_info_df.loc[len(player_info_df)] = [
                i, player['m_hero'], player['m_name'], player['m_teamId'], player['m_result']]
            i += 1

        player_info_df.loc[:,'m_hero'] = player_info_df['m_hero'].str.decode("utf-8") 
        player_info_df.loc[:,'m_name'] = player_info_df['m_name'].str.decode("utf-8") 
        
        # update player info
        self.player_info = player_info_df
        
        return None
    
#     def closest_gameloop(self, gameloop, gameloop_list):
#         # will find the largest element of gameloop_list less than gameloop
#         if len(gameloop_list) == 1:
#             gameloop_list = int(gameloop_list)
#             if gameloop == gameloop_list:
#                 return gameloop
#             elif gameloop < gameloop_list:
#                 return -1
#             elif gameloop > gameloop_list:
#                 return int(gameloop_list)

#         else:
#             if gameloop in gameloop_list:
#                 return gameloop
#             elif gameloop < min(gameloop_list):
#                 return -1
#             else:
#                 closest_gameloop = -1
#                 for gl in gameloop_list:
#                     if gl < gameloop:
#                         closest_gameloop = gl
#                     else:
#                         break
#                 return closest_gameloop
    
    def make_unit_info(self):
        # unit life cycle
        # unit_born = (unitIndex, recyle tag, gameloop): (unit name, x coord, y coord, playerId (team))
        # unit_died = (unitIndex, recyle tag, gameloop): (x coord, y coord, killer playerId (team), killer unitTagIndex, killer recyle tag)

        unit_born = {}
        unit_revived = {}
        unit_died = {}
        player_id = {}

        for event in self.tracker_events:
            if event['_event'] == 'NNet.Replay.Tracker.SUnitBornEvent':
                unit_born[( event['m_unitTagIndex'], event['m_unitTagRecycle'], event['_gameloop'] )] = (
                        event['m_unitTypeName'], event['m_x'], event['m_y'], event['m_upkeepPlayerId'])

            elif event['_event'] == 'NNet.Replay.Tracker.SUnitRevivedEvent':
                unit_revived[( event['m_unitTagIndex'], event['m_unitTagRecycle'], event['_gameloop'] )] = (
                        event['m_x'], event['m_y'])

            elif event['_event'] == 'NNet.Replay.Tracker.SUnitDiedEvent':
                unit_died[( event['m_unitTagIndex'], event['m_unitTagRecycle'], event['_gameloop'] )] = (
                        event['m_x'], event['m_y'], event['m_killerPlayerId'],
                        event['m_killerUnitTagIndex'], event['m_killerUnitTagRecycle'])

            elif event['_event'] == 'NNet.Replay.Tracker.SPlayerSetupEvent':
                player_id[event['m_userId']] = event['m_playerId']
        
        
        # form pandas dataframe

        # unit born df
        unit_born_df = pd.Series(unit_born).reset_index()
        unit_born_df = unit_born_df.rename(columns={'level_0': "m_unitTagIndex", 'level_1': "m_unitTagRecycle", 'level_2': "born_gameloop", 0: "info"})
        unit_born_df[["m_unitTypeName", "born_m_x", "born_m_y", "m_upkeepPlayerId"]] = pd.DataFrame(unit_born_df['info'].tolist(), index=unit_born_df.index)
        unit_born_df = unit_born_df.drop(columns=['info'])
        unit_born_df["revived"] = 0

        # unit revived df
        unit_revived_df = pd.Series(unit_revived).reset_index()
        unit_revived_df = unit_revived_df.rename(columns={'level_0': "m_unitTagIndex", 'level_1': "m_unitTagRecycle", 'level_2': "born_gameloop", 0: "info"})
        unit_revived_df[["born_m_x", "born_m_y"]] = pd.DataFrame(unit_revived_df['info'].tolist(), index=unit_revived_df.index)
        unit_revived_df = unit_revived_df.drop(columns=['info'])
        unit_revived_df["revived"] = 1
        # fill info from born_df
        unit_revived_df["m_unitTypeName"] = unit_revived_df.apply (
                lambda row: unit_born_df[unit_born_df.m_unitTagIndex.eq(int(row['m_unitTagIndex'])) &
                                         unit_born_df.m_unitTagRecycle.eq(int(row['m_unitTagRecycle']))].m_unitTypeName.iloc[0], axis=1)
        unit_revived_df["m_upkeepPlayerId"] = unit_revived_df.apply (
                lambda row: unit_born_df[unit_born_df.m_unitTagIndex.eq(int(row['m_unitTagIndex'])) &
                                         unit_born_df.m_unitTagRecycle.eq(int(row['m_unitTagRecycle']))].m_upkeepPlayerId.iloc[0], axis=1)

        # unit died df
        unit_died_df = pd.Series(unit_died).reset_index()
        unit_died_df = unit_died_df.rename(columns={'level_0': "m_unitTagIndex", 'level_1': "m_unitTagRecycle", 'level_2': "died_gameloop", 0: "info"})
        unit_died_df[['died_m_x','died_m_y', 'm_killerPlayerId', 'm_killerUnitTagIndex', 'm_killerUnitTagRecycle']] = pd.DataFrame(unit_died_df['info'].tolist(), index=unit_died_df.index)
        unit_died_df = unit_died_df.drop(columns=['info'])

        # merge unit info dataframes
        # unit_born_df longer than unit_died_df
        # first merge born_df with revived_df
        # second merge with died_df, define joining index using closest_gameloop

        unit_born_df = pd.concat([unit_born_df, unit_revived_df], ignore_index=True, sort=True)
        unit_born_df = unit_born_df.sort_values(by=['born_gameloop', 'm_unitTagIndex','m_unitTagRecycle'])

        unit_born_df.loc[:,'m_unitTypeName'] = unit_born_df['m_unitTypeName'].str.decode("utf-8") 

        def born_died_index(row):
            m_unitTagIndex = row['m_unitTagIndex']
            m_unitTagRecycle = row['m_unitTagRecycle']
            born_gameloop = unit_born_df[
                unit_born_df.m_unitTagIndex.eq(int(m_unitTagIndex)) &
                unit_born_df.m_unitTagRecycle.eq(int(m_unitTagRecycle))].born_gameloop
#             idx_gameloop = self.closest_gameloop(int(row['died_gameloop']), born_gameloop)
            idx_gameloop = closest_gameloop(int(row['died_gameloop']), born_gameloop)

            return (m_unitTagIndex, m_unitTagRecycle, idx_gameloop)

        unit_died_df["born_died_index"] = unit_died_df.apply (lambda row: born_died_index(row), axis=1)
        unit_born_df["born_died_index"] = unit_born_df.apply (lambda row: (row["m_unitTagIndex"], row['m_unitTagRecycle'], row["born_gameloop"]), axis=1)


        unit_info_df = unit_born_df.merge(
            unit_died_df.drop(columns = ['m_unitTagIndex', 'm_unitTagRecycle']),
            how = 'outer', 
            on = 'born_died_index')
        unit_info_df = unit_info_df.drop(columns = ['born_died_index'])

        # replace no died gameloop to infinity
        unit_info_df.died_gameloop = unit_info_df.died_gameloop.fillna(float('inf'))

        # sort by born gameloop
        unit_info_df = unit_info_df.sort_values(by = ['born_gameloop','m_unitTagIndex', 'm_unitTagRecycle'])
        
        # add data about lives lived:
        # first born = 0 lives lived
        # first death = 0 lives lived
        # first revive = 1 lives lived

        unit_info_df['lives'] = unit_info_df.groupby(['m_unitTagIndex','m_unitTagRecycle']).cumsum()['revived']
        
        # unit_info_short
        unit_info_df_short = unit_info_df[['m_upkeepPlayerId','m_unitTagIndex','m_unitTagRecycle','m_unitTypeName']]
        unit_info_df_short = unit_info_df_short.drop_duplicates()
                
        # define shorter df for look up
        hero_info_df_short = unit_info_df_short[unit_info_df_short['m_unitTypeName'].str.contains("Hero")]
        
        # update unit_info
        self.unit_info = unit_info_df
        self.unit_info_short = unit_info_df_short
        self.hero_info_short = hero_info_df_short
        self.unit_died = unit_died_df
        self.player_id_ls = player_id
        
        return None
    
    
    def hero_unit_index (self, player_id=None, hero_name=None):
        if player_id is not None:
            unit = self.unit_info_short[self.unit_info_short.m_upkeepPlayerId.eq(int(player_id))]
        if (hero_name is not None) or (player_id is None and len(unit) > 1 ):
            hero_name_adapted = hero_name.replace('The','')
            hero_name_adapted = hero_name_adapted.replace(' ','')
            unit = self.unit_info_short[self.unit_info_short['m_unitTypeName'].str.contains(hero_name_adapted)]
            if unit.empty and (hero_name_adapted in self.hero_alt_names.keys()):
                unit = self.unit_info_short[self.unit_info_short[
                    'm_unitTypeName'].str.contains(self.hero_alt_names[hero_name_adapted])]

    #     unit['m_unitTypeName'] = unit['m_unitTypeName'].str.decode("utf-8") 
        unit = unit[unit['m_unitTypeName'].str.contains("Hero")]
        unit = unit[['m_unitTagIndex','m_unitTagRecycle','m_unitTypeName']]
        unit = unit.drop_duplicates()

        if len(unit) == 0:
            raise ValueError("no such hero")
        elif len(unit) == 1:
            unit_one = unit.iloc[0]
            return (unit_one['m_unitTagIndex'], unit_one['m_unitTagRecycle'])
        else:
            raise ValueError("multiple unitTagIdex found, please try with unit name")
        return unit
    
    def unit_info_lookup(self, unitIndex, gameloop, unitRecycle=None):
        # look up function
        # unitIndex with either unitRecyle or gameloop should uniquely identify
        # return 1 line of data

        unit = {}
        # all units reuse 0 to 259 unit index (maybe)
        if unitIndex >= 1000:
            raise ValueError("UnitIndex must be less than 1000, you tried "+str(unitIndex))

        if unitRecycle is not None:
            sub_df = self.unit_info[self.unit_info.m_unitTagIndex.eq(int(unitIndex)) &
                                    (self.unit_info.born_gameloop <= gameloop) & 
                                    (self.unit_info.died_gameloop >= gameloop) &
                                    self.unit_info.m_unitTagRecycle.eq(int(unitRecycle))].copy()

        else:
            sub_df = self.unit_info[self.unit_info.m_unitTagIndex.eq(int(unitIndex)) &
                                    (self.unit_info.born_gameloop <= gameloop) & 
                                    (self.unit_info.died_gameloop >= gameloop)].copy()

        return sub_df
    
    def make_position_hero(self):
        ## =============================
        ## make unit_position_df
        # unit_position = (unitIndex, gameloop): (x, y)
        # unit_position x and y range is 0:1000 compared to 0:200 in born_df

        unit_position = {}

        for event in self.tracker_events:

            # Interpret the NNet.Replay.Tracker.SUnitPositionsEvent events like this:
            if event["_event"] == 'NNet.Replay.Tracker.SUnitPositionsEvent':
                unitIndex = event['m_firstUnitIndex']
                j = 0
                for i in range(0, len(event['m_items']), 3):
                    unitIndex += event['m_items'][i + 0]
                    x = event['m_items'][i + 1] * 4
                    y = event['m_items'][i + 2] * 4
                    j+=1
                    # unit identified by unitIndex at the current event['_gameloop'] time
                    # is at approximate position (x, y)

                    unit_position[(unitIndex, event['_gameloop'] )] = (x, y)

        unit_position_df = pd.Series(unit_position).reset_index()
        unit_position_df = unit_position_df.rename(columns={'level_0': "m_unitTagIndex", 'level_1': "gameloop", 0: "info"})
        unit_position_df[["m_x", "m_y"]] = pd.DataFrame(unit_position_df['info'].tolist(), index=unit_position_df.index)
        unit_position_df = unit_position_df.drop(columns=['info'])
        
        # add names to unit_position_df
#         print(unit_position_df.head())
#         print(max(unit_position_df.m_unitTagIndex))
#         print(min(unit_position_df.m_unitTagIndex))
        unit_position_df["m_unitTypeName"] = unit_position_df.apply (
                lambda row: self.unit_info_lookup(
                    unitIndex = int(row['m_unitTagIndex']),
                    gameloop = int(row['gameloop'])).m_unitTypeName.iloc[0], axis=1)

        unit_position_df["m_upkeepPlayerId"] = unit_position_df.apply (
                lambda row: self.unit_info_lookup(
                    int(row['m_unitTagIndex']),
                    int(row['gameloop'])).m_upkeepPlayerId.iloc[0], axis=1)
        
        ## =============================
        ## make player_position_cmd_df
        # add positions of heroes based on CCmdUpdateTargetUnitEvent, CCmdEvent, CCmdUpdateTargetPointEvent
        # NNet.Game.SCmdEvent (id = 27)
        # NNet.Game.SCmdUpdateTargetPointEvent (id = 104)
        # NNet.Game.SCmdUpdateTargetUnitEvent (id = 105)

        # event values are scaled by 4096

        # NNet.Game.SCommandManagerStateEvent ?

        # cmd_event = (user, gameloop): (x,y,z)

        cmd_event = {}
        cmd_target_point = {}
        cmd_target_unit = {}

        for event in self.game_events:
            if event['_event'] == 'NNet.Game.SCmdEvent':
                if event['m_data'] != {'None': None}:  
                    if list(event['m_data'].keys()) == ['TargetUnit']:
                        cmd_event[( event['m_data']['TargetUnit']['m_snapshotControlPlayerId'], 
                                         event['_gameloop'] )] = (
                            event['m_data']['TargetUnit']['m_snapshotPoint']['x'], 
                            event['m_data']['TargetUnit']['m_snapshotPoint']['y'], 
                            event['m_data']['TargetUnit']['m_snapshotPoint']['z'])
                    elif list(event['m_data'].keys()) == ['TargetPoint']:
                        cmd_event[( event['_userid']['m_userId'], event['_gameloop'] )] = (
                            event['m_data']['TargetPoint']['x'], 
                            event['m_data']['TargetPoint']['y'], 
                            event['m_data']['TargetPoint']['z'])
            elif event['_event'] == 'NNet.Game.SCmdUpdateTargetPointEvent':
                # position of target of ability
                cmd_target_point[( event['_userid']['m_userId'], event['_gameloop'] )] = (
                    event['m_target']['x'], 
                    event['m_target']['y'],
                    event['m_target']['z'])

            elif event['_event'] == 'NNet.Game.SCmdUpdateTargetUnitEvent':
                cmd_target_unit[( event['m_target']['m_snapshotControlPlayerId'], event['_gameloop'] )] = (
                        event['m_target']['m_snapshotPoint']['x'], 
                        event['m_target']['m_snapshotPoint']['y'], 
                        event['m_target']['m_snapshotPoint']['z'])
        
        # form pandas dataframe

        # cmd_event_df
        cmd_event_df = pd.Series(cmd_event).reset_index()
        cmd_event_df = cmd_event_df.rename(columns={'level_0': "user", 'level_1': "gameloop", 0: "info"})
        cmd_event_df[["x", "y", "z"]] = pd.DataFrame(cmd_event_df['info'].tolist(), index=cmd_event_df.index)
        cmd_event_df = cmd_event_df.drop(columns=['info'])

        # cmd_target_point_df
        cmd_target_point_df = pd.Series(cmd_target_point).reset_index()
        cmd_target_point_df = cmd_target_point_df.rename(columns={'level_0': "user", 'level_1': "gameloop", 0: "info"})
        cmd_target_point_df[["x", "y", "z"]] = pd.DataFrame(cmd_target_point_df['info'].tolist(), index=cmd_target_point_df.index)
        cmd_target_point_df = cmd_target_point_df.drop(columns=['info'])

        # cmd_target_unit_df
        cmd_target_unit_df = pd.Series(cmd_target_unit).reset_index()
        cmd_target_unit_df = cmd_target_unit_df.rename(columns={'level_0': "user", 'level_1': "gameloop", 0: "info"})
        cmd_target_unit_df[["x", "y", "z"]] = pd.DataFrame(cmd_target_unit_df['info'].tolist(), index=cmd_target_unit_df.index)
        cmd_target_unit_df = cmd_target_unit_df.drop(columns=['info'])


        # merge
        player_position_cmd_df = pd.concat([cmd_event_df, cmd_target_point_df, cmd_target_unit_df], 
                                           ignore_index=True, sort=True)
        player_position_cmd_df = player_position_cmd_df.sort_values(by=['gameloop', 'user'])
        player_position_cmd_df.x = player_position_cmd_df.x / 4096
        player_position_cmd_df.y = player_position_cmd_df.y / 4096
        player_position_cmd_df.z = player_position_cmd_df.z / 4096

        # add hero names based on m_upkeepPlayerId and user
        player_position_cmd_df['player_id'] = player_position_cmd_df.user.map(self.player_id_ls)
        player_position_cmd_df = player_position_cmd_df.merge(
            self.player_info[['player_id','m_hero']], 
            how = 'left', 
            on = 'player_id')
        
        ## =============================
        ## Combine born and died df, player_position_cmd_df, and unit_position_df
        
        # columns: gameloop, x, y, player_id, hero, unitTag, alive

        # player position cmd
        temp_df1 = player_position_cmd_df.drop(columns=['user', 'z'])
        temp_df1 = temp_df1.rename(columns={"m_hero": "hero"})
        temp_df1 = temp_df1[temp_df1['hero'].notnull()]

        temp_df1.loc[:,'hero'] = temp_df1.hero.str.replace("Hero",'',case=True)
        temp_df1 = pd.merge(left = temp_df1, 
                            right = self.hero_info_short[['m_upkeepPlayerId', 'm_unitTagIndex']], 
                            how = 'left',
                            left_on = 'player_id', 
                            right_on = 'm_upkeepPlayerId')
        temp_df1 = temp_df1.rename(columns={"m_unitTagIndex": "unitTagIndex"})

        # fill nan using function
        if (len(temp_df1[temp_df1['unitTagIndex'].isna()]) != 0):
            temp_df1[temp_df1['unitTagIndex'].isna()]['unitTagIndex'] = temp_df1[
                temp_df1['unitTagIndex'].isna()].apply (
                    lambda row: hero_unit_index(row['player_id'], row['hero'])[0], axis=1)

        # unit position 
        temp_df2 = unit_position_df
        temp_df2 = temp_df2.rename(columns={"m_x": "x", "m_y": "y",
                                            "m_unitTypeName": "hero",
                                            "m_upkeepPlayerId": "player_id",
                                            "m_unitTagIndex": "unitTagIndex"})
        temp_df2.x = temp_df2.x / 4
        temp_df2.y = temp_df2.y / 4

        # unit born
        temp_df3 = self.unit_info[['born_gameloop','born_m_x','born_m_y','m_upkeepPlayerId',
                                   'm_unitTypeName', 'm_unitTagIndex', 'lives']].copy()
        temp_df3 = temp_df3.rename(columns={"born_gameloop": "gameloop",
                                            "born_m_x": "x", "born_m_y": "y",
                                            "m_unitTypeName": "hero",
                                            "m_upkeepPlayerId": "player_id",
                                            "m_unitTagIndex": "unitTagIndex"})


        # unit died
        temp_df4 = self.unit_info[['died_gameloop','died_m_x','died_m_y','m_upkeepPlayerId',
                                   'm_unitTypeName', 'm_unitTagIndex', 'lives']].copy()
        temp_df4 = temp_df4.rename(columns={"died_gameloop": "gameloop",
                                            "died_m_x": "x", "died_m_y": "y",
                                            "m_unitTypeName": "hero",
                                            "m_upkeepPlayerId": "player_id",
                                            "m_unitTagIndex": "unitTagIndex"})

        temp_df4 = temp_df4[temp_df4['hero'].str.contains("Hero")]
        temp_df4 = temp_df4[temp_df4['x'].notnull()]


        # only keep heros
        temp_df2 = temp_df2[temp_df2['hero'].str.contains("Hero")]
        temp_df3 = temp_df3[temp_df3['hero'].str.contains("Hero")]
        
        # add empty lives column to temp df 1 2
        temp_df1['lives'] = None
        temp_df2['lives'] = None

        # add column about alive,
        # temp_df2 could be the moment they are killed
        temp_df1['alive'] = True
        temp_df2['alive'] = None
        temp_df3['alive'] = True
        temp_df4['alive'] = False

        # concat
        temp_df1 = temp_df1[['gameloop','x','y','player_id', 'hero', 'unitTagIndex', 'lives', 'alive']].copy()
        temp_df2 = temp_df2[['gameloop','x','y','player_id', 'hero', 'unitTagIndex', 'lives', 'alive']].copy()
        temp_df3 = temp_df3[['gameloop','x','y','player_id', 'hero', 'unitTagIndex', 'lives', 'alive']].copy()
        temp_df4 = temp_df4[['gameloop','x','y','player_id', 'hero', 'unitTagIndex', 'lives', 'alive']].copy()

        position_hero_df = pd.concat([temp_df1, temp_df2, temp_df3, temp_df4], ignore_index=True, sort=True)
        position_hero_df = position_hero_df.sort_values(by=['gameloop','player_id','unitTagIndex'])
#         print(len(position_hero_df))

        position_hero_df['hero'] = position_hero_df.hero.str.replace("Hero",'',case=True)

        # add team
        position_hero_df['team'] = position_hero_df['player_id'] <=5

        position_hero_df['gameloop'] = position_hero_df['gameloop'].astype('int')

        # rename altnames:
        for index, unit in position_hero_df.iterrows():
            if unit.hero in self.hero_alt_names.values():
                position_hero_df.at['hero',index] = self.hero_alt_names_inv[unit.hero]

        ## =============================
        ## Fill remaining gameloop positions with linear interpolation
        fill_df = position_hero_df.copy()
#         print(set(position_hero_df.hero))
        def fill_position (position_df):
            filled_df = pd.DataFrame(columns = position_df.columns)

            for hero_name in set(position_df.hero):
                if isinstance(hero_name, str):
                    hero_df = position_df[(position_df['hero'] == hero_name)]

                    # make gameloops to fill
                    temp_df = pd.DataFrame(columns = position_df.columns)
                    temp_df['gameloop'] = np.arange(min(position_df.gameloop), max(position_df.gameloop), dtype=int)
                    temp_df.at[:,'hero'] = hero_name
                    if len(set(hero_df.player_id)) == 1: 
                        temp_df.at[:,'player_id'] = list(set(hero_df.player_id))[0]
                    elif len(set(hero_df.player_id)) == 0:
                        print("No player id found for hero: " + str(hero_name))
                        raise ValueError("No player id found for hero: " + str(hero_name))
                    else:
                        print(set(hero_df.player_id))
                        raise ValueError("Multiple player id found for a hero")
                    if len(set(hero_df.unitTagIndex)) == 1:
                        temp_df.at[:,'unitTagIndex'] = list(set(hero_df.unitTagIndex))[0]
                    else:
                        unitTagIndex_options = set(hero_df.unitTagIndex).intersection(
                            set(self.unit_info[(hero_name in self.unit_info.m_unitTypeName) & 
                                             (self.unit_info.m_unitTagRecycle == 1)].m_unitTagIndex)
                        )
                    temp_df.at[:,'team'] = list(set(hero_df.team))[0]

                    # join temp df
                    hero_df = pd.concat([hero_df, temp_df], ignore_index=False)
                    hero_df = hero_df.sort_values(by=['gameloop', 'alive'])
                    hero_df = hero_df.drop_duplicates(subset=['gameloop'], keep="first")

                    # reset index
                    hero_df = hero_df.reset_index(drop=True)

                    cols = ['alive','lives']
                    hero_df.loc[:, cols] = hero_df.loc[:, cols].ffill()

                    # backward fill for lives
                    hero_df.loc[:, 'lives'] = hero_df.loc[:, 'lives'].bfill()

                    hero_df['alive'] = hero_df['alive'].astype('bool')

                    hero_df['x'] = hero_df['x'].astype('float')
                    hero_df['y'] = hero_df['y'].astype('float')

                    # if not alive, fill x and y
                    rows = hero_df.alive==False
                    cols = ['x','y']
                    hero_df.loc[rows, cols] = hero_df.loc[rows, cols].ffill()

                    # filling alive position will use died position as well
                    cols = ['x','y']
                    hero_df.loc[:, cols] = hero_df.loc[:, cols].interpolate()

                    filled_df = pd.concat([filled_df, hero_df])
            return filled_df

        position_filled_df = fill_position(fill_df)
        
        ## =============================
        # update position_hero
        self.position_hero = position_filled_df#position_hero_df
        
        return None
    
    def make_exp_event(self):
        # SStatGameEvent
        # reg_globe_event = {}
        exp_event = {}

        for event in self.tracker_events:
            if event['_event'] == 'NNet.Replay.Tracker.SStatGameEvent':
                if event['m_eventName'] == b'PeriodicXPBreakdown':
                    exp_event[(event['_gameloop'], 
                               event['m_intData'][0]['m_value'] # team
                              )] = (
                        event['m_fixedData'][0]['m_value'], # gametime
                        event['m_fixedData'][1]['m_value'], # previous game time
                        event['m_fixedData'][2]['m_value'], # Minion XP
                        event['m_fixedData'][3]['m_value'], # CreepXP
                        event['m_fixedData'][4]['m_value'], # StructureXP
                        event['m_fixedData'][5]['m_value'], # HeroXP
                        event['m_fixedData'][6]['m_value'], # TrickleXP
                        event['m_intData'][1]['m_value'] # team level
                    )
        # form pandas dataframe

        # exp_event_df
        exp_event_df = pd.Series(exp_event).reset_index()
        exp_event_df = exp_event_df.rename(columns={'level_0': "gameloop", 'level_1': "team", 0: "info"})
        exp_event_df[["game_time", 
                      "previous_game_time", 
                      "minionXP",
                      "creepXP",
                      "structureXP",
                      "heroXP",
                      "trickleXP",
                      "level"]] = pd.DataFrame(exp_event_df['info'].tolist(), index=exp_event_df.index)
        exp_event_df = exp_event_df.drop(columns=['info'])
        
        # update exp_event
        self.exp_event = exp_event_df
        
        return None
    
    def make_hero_distances(self, gameloop_steps = 100):
        # define distance measure between players

        # use data['xy'] = data['x'] + data['y'] * 1j to make complex

        # use the below to split into 2 columns
        # data['x'] = data['xy'].apply(np.real)
        # data['y'] = data['xy'].apply(np.imag)
        # data.drop('xy', axis=1, inplace=True)

        # distance = (data['xy'] - ref_xy).abs()

        # define pairwise relations
        hero_unitTagIndex = set(self.position_hero.unitTagIndex)
        hero_unitTagIndex_pairs = []
        for i in hero_unitTagIndex:
            for j in hero_unitTagIndex:
                if i != j:
#                     hero_unitTagIndex_pairs = pd.concat((hero_unitTagIndex_pairs, (i,j)), axis=0)
                    hero_unitTagIndex_pairs.append((i,j))

        # form df from list
        list1, list2 = zip(*hero_unitTagIndex_pairs)

        hero_unitTagIndex_pairs_df = pd.DataFrame({'unit1': list1,
                                                   'unit2': list2})
        
        # join x and y as complex number
        hero_position_complex = self.position_hero[['gameloop','unitTagIndex','x','y']].copy()
        hero_position_complex['xy'] = hero_position_complex['x'] + hero_position_complex['y'] * 1j
        hero_position_complex = hero_position_complex.drop_duplicates(subset=['gameloop','unitTagIndex'])
        
        # define distance
        hero_distances = pd.DataFrame(columns = ["gameloop", "unit1", "unit2", "distance"])
        for gl in set(hero_position_complex.gameloop):
            if np.mod(gl, gameloop_steps) == 0:
                temp_df = pd.DataFrame(columns = hero_distances.columns)
                temp_df["unit1"] = hero_unitTagIndex_pairs_df["unit1"]
                temp_df["unit2"] = hero_unitTagIndex_pairs_df["unit2"]
                temp_df["gameloop"] = gl

                hero_distances = pd.concat([hero_distances,temp_df])

        # hero_distances.reset_index(drop=True)
        hero_distances["unit1_position"] = list(pd.merge(hero_distances[['gameloop','unit1']],
                                  hero_position_complex[['gameloop','unitTagIndex','xy']],
                                  how = 'left', 
                                  left_on = ['unit1','gameloop'], 
                                  right_on = ['unitTagIndex','gameloop'])['xy'])

        hero_distances["unit2_position"] = list(pd.merge(hero_distances[['gameloop','unit2']],
                                  hero_position_complex[['gameloop','unitTagIndex','xy']],
                                  how = 'left', 
                                  left_on = ['gameloop','unit2'], 
                                  right_on = ['gameloop','unitTagIndex'])['xy'])

        hero_distances["distance"] = (hero_distances["unit1_position"] - hero_distances["unit2_position"]).abs()
        
        # add whether distances are friendly or opponent
        unit_teams = self.position_hero[['unitTagIndex',"team"]].copy().drop_duplicates().sort_values(by="unitTagIndex")

        hero_distances["team1"] = pd.merge(hero_distances, unit_teams,
                                           how = "left",
                                           left_on = ["unit1"],
                                           right_on = ["unitTagIndex"])['team']
        hero_distances["team2"] = pd.merge(hero_distances, unit_teams,
                                           how = "left",
                                           left_on = ["unit2"],
                                           right_on = ["unitTagIndex"])['team']

        hero_distances["friendly"] = (hero_distances["team1"] == hero_distances["team2"])
        
        # update hero_distances
        self.hero_distances = hero_distances
        
        return None
    
    def is_team_fight (self, gameloop, hero_distances, 
                       friendly_team_fight_dist = None,
                       opponent_team_fight_dist = None,
                       min_heroes = 3):
        if friendly_team_fight_dist is None:
            friendly_team_fight_dist = self.near_distance
        if opponent_team_fight_dist is None:
            opponent_team_fight_dist = self.near_distance
        
        # define team fight
        sub_df = self.hero_distances[self.hero_distances.gameloop == gameloop].copy()
        
        friend_dist = sub_df[sub_df.friendly == True]
        opp_dist = sub_df[sub_df.friendly == False]

        # min_heroes * 2 because duplicate distance
        return ((sum(friend_dist.distance <= friendly_team_fight_dist) > min_heroes*2) &
                (sum(opp_dist.distance <= opponent_team_fight_dist) > min_heroes*2))

    def nearby_heroes(self, gameloop, hero_distances, unitTagIndex,
                      near_distance = None):
        if near_distance is None:
            near_distance = self.near_distance
        # define nearby friendly and enemy
        close_gameloop = closest_gameloop(gameloop, self.hero_distances.gameloop)
#         close_gameloop = self.closest_gameloop(gameloop, self.hero_distances.gameloop)

        sub_df = self.hero_distances[(self.hero_distances.gameloop == close_gameloop) &
                                    (self.hero_distances.unit1 == unitTagIndex)].copy()

        friendly_heroes = sub_df[(sub_df.friendly == True) &
                                 (sub_df.distance <= near_distance)].unit2
        enemy_heroes = sub_df[(sub_df.friendly == False) &
                                 (sub_df.distance <= near_distance)].unit2

        return(friendly_heroes, enemy_heroes)
    
    def make_heroes_died_position(self):
        # see where heroes are killed

        # heroes m_unitTagIndex
        heroes_unitTagIndex = list(set(self.hero_info_short[self.hero_info_short.m_unitTypeName.str.contains('Hero')].m_unitTagIndex))

        # where heroes died
        heroes_died_df = self.unit_died[self.unit_died['m_unitTagIndex'].isin(heroes_unitTagIndex)].copy()

        # how many heroes were near
        heroes_died_position_df = heroes_died_df[['m_unitTagIndex','died_gameloop',
                                                  'died_m_x','died_m_y','m_killerUnitTagIndex']].copy()
        heroes_died_position_df.at[:,'near_friend'] = 0
        heroes_died_position_df.at[:,'near_enemy'] = 0
        heroes_died_position_df.at[:, 'near_friend_ls_hero'] = ""
        heroes_died_position_df.at[:, 'near_enemy_ls_hero'] = ""
        heroes_died_position_df.at[:, 'near_friend_ls_player'] = ""
        heroes_died_position_df.at[:, 'near_enemy_ls_player'] = ""
        
        for row_i in heroes_died_position_df.index:
            died_sub_info = heroes_died_position_df.loc[row_i]
            near_friend_ls, near_enemy_ls = self.nearby_heroes(died_sub_info.died_gameloop,
                                                               self.hero_distances,
                                                               died_sub_info.m_unitTagIndex)
            heroes_died_position_df.at[row_i, 'near_friend'] = len(near_friend_ls)
            heroes_died_position_df.at[row_i, 'near_enemy'] = len(near_enemy_ls)
            
            near_friend_hero_info = self.hero_info_short.loc[
                self.hero_info_short.m_unitTagIndex.isin(near_friend_ls)].copy()
#             near_enemy_hero_info = self.hero_info_short.loc[list(map(int, near_enemy_ls))].copy()
            near_enemy_hero_info = self.hero_info_short.loc[
                self.hero_info_short.m_unitTagIndex.isin(near_enemy_ls)].copy()
    
            heroes_died_position_df.at[row_i, 'near_friend_ls_hero'] = list(near_friend_hero_info.m_unitTypeName)
            heroes_died_position_df.at[row_i, 'near_enemy_ls_hero'] = list(near_enemy_hero_info.m_unitTypeName)
            heroes_died_position_df.at[row_i, 'near_friend_ls_player'] = list(self.player_info.loc[near_friend_hero_info.m_upkeepPlayerId - 1, "m_name"])
            heroes_died_position_df.at[row_i, 'near_enemy_ls_player'] = list(self.player_info.loc[near_enemy_hero_info.m_upkeepPlayerId - 1, "m_name"])
            

        # add hero name, winning team, which direction, user
        heroes_died_position_df = heroes_died_position_df.merge(
            self.hero_info_short[['m_unitTagIndex','m_unitTypeName','m_upkeepPlayerId']],
            on = ['m_unitTagIndex'], 
            how = 'left')
        
        heroes_died_position_df = heroes_died_position_df.merge(
            self.hero_info_short[['m_unitTagIndex','m_unitTypeName']].copy().rename(columns={"m_unitTagIndex":"m_killerUnitTagIndex", "m_unitTypeName": "m_killerUnitTypeName"}),
            on = ['m_killerUnitTagIndex'],
#             right_on = ['m_unitTagIndex'],
            how = 'left')
        
        heroes_died_position_df = heroes_died_position_df.merge(
            self.player_info,
            left_on = 'm_upkeepPlayerId', 
            right_on = 'player_id',
            how = 'left')
        
        # update heroes_died_position
        self.heroes_died_position = heroes_died_position_df
        
        return None
    
    def make_building_position(self):
        building_names = ['HallOfStormsLocationUnit', 'TownTownHallL2', 'KingsCore']
        building_position = pd.DataFrame(columns = ["m_unitTypeName", "m_upkeepPlayerId", "x", "y"])

        for index, unit in self.unit_info.iterrows():
            if unit.m_unitTypeName in building_names:                                
                building_position.loc[len(building_position)] = [
                    unit.m_unitTypeName, int(unit.m_upkeepPlayerId),
                    unit.born_m_x, unit.born_m_y]
        
        # update building position
        self.building_position = building_position
        
        return None
        
    def export_to_csv(self, attr, path = ""):
        path = attr + '.csv'
        # export to csv
        getattr(self,attr).to_csv(path)