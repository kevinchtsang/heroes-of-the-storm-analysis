# Heroes of the Storm Analysis
Heroes of the Storm replay parsing and analysis, to take a deeper look at your games and make decisions backed by data. This pipeline is setup to process multiple games for data analysis. A data exploration tool (Shiny app) has been included to aid your analysis. 

Good luck; have fun

## Getting Started
You will need to put your replays in a folder. If you don't have any recent replays, (Heroes Lounge)[https://heroeslounge.gg/] hosts amature HotS matches and individual match replays can be downloaded.

### Parsing Replays
First install the [heroprotocol](https://github.com/Blizzard/heroprotocol).
```
python -m pip install --upgrade heroprotocol
```

Or clone the repository
```
git clone https://github.com/Blizzard/heroprotocol.git
python -m pip install -r ./heroprotocol/heroprotocol/requirements.txt
```

Then use the `HotS replays to dataframe.ipynb` notebook to parse your replays and combine them into a single dataframe `hero_died_all.csv`. This can be analysed in any method of your choice.

`HotS Analyse Multiple Games.ipynb` notebook is used to manually calibrate the coordinates of the parsed replays to the official Blizzard map overlay. It can also be a place to conduct data analysis using python.

`shiny_hero_deaths.R` is a Shiny app to explore the data interactively.


## Notes about protocol variables

protocol uses Dota/Warcraft terms (order/chaos team, creep)
Nothing useful in initdata

units = structures, players, minions

structures = TownHall, Moonwell, CannonTower



Tracker Events:

    *NNet.Replay.Tracker.SUnitBornEvent 
      = structures and units born and player summons (_eventid = 1)
      eg force wall, aba toxic nest
      m_controlPlayerId 0, 11 and 12 are AI, player index start at 1
    *NNet.Replay.Tracker.SUnitDiedEvent 
      = units, towers, and players summon die (_eventid = 2)
    *NNet.Replay.Tracker.SUnitOwnerChangeEvent 
      = sylvanas and towers of doom?? (_eventid = 3)
    *NNet.Replay.Tracker.SUnitTypeChangeEvent 
      = killing and reborn structures (_eventid = 4)
    NNet.Replay.Tracker.SUpgradeEvent 
      = set up player teams (_eventid = 5)
    NNet.Replay.Tracker.SUnitPositionsEvent
      = track position of some units every 240 gameloops (_eventid = 8)
      (Only units that have inflicted or taken damage are mentioned in unit position events, 
      and they occur periodically with a limit of 256 units mentioned per event.)
    NNet.Replay.Tracker.SPlayerSetupEvent 
      = players (_eventid = 9)
    NNet.Replay.Tracker.SStatGameEvent
      = update in damage numbers? (_eventid = 10)
      = {b'Altar Captured',
         b'EndOfGameTalentChoices',
         b'EndOfGameTimeSpentDead',
         b'EndOfGameUpVotesCollected',
         b'EndOfGameXPBreakdown',
         b'GameStart',
         b'GatesOpen',
         b'JungleCampCapture',
         b'JungleCampInit',
         b'LevelUp',
         b'LootSprayUsed',
         b'LootVoiceLineUsed',
         b'LootWheelUsed',
         b'PeriodicXPBreakdown',
         b'PlayerDeath',
         b'PlayerInit',
         b'PlayerSpawned',
         b'RegenGlobePickedUp',
         b'TalentChosen',
         b'Town Captured',
         b'TownStructureDeath',
         b'TownStructureInit'}
    NNet.Replay.Tracker.SScoreResultEvent
      = end of game stats (_eventid = 11)
    NNet.Replay.Tracker.SUnitRevivedEvent
      = revived units (_eventid = 12)
      has coordinates
      
      
    player identification:
        m_playerId (SPlayerSetupEvent) index start at 1
        m_slotId = basically playerId -1
        m_type
        m_userId = basically playerId -1
    
    Useful variables:
        _gameloop = game event time (correspond with header file) 
          (1 gameloop appox = 0.05 seconds = 862 seconds / 14127 gameloops)
        m_x = location x
        m_x = location y
        m_killerPlayerId
        m_time = time in seconds (found in SScoreResultEvent)

Game Events:
    
    NNet.Game.SUserFinishedLoadingSyncEvent
      = not useful (_eventid = 5)
    NNet.Game.SUserOptionsEvent
      = not useful, changing player options (_eventid = 7)
    NNet.Game.SCmdEvent
      = big file, clicks/actions? (_eventid = 27)
      has coordinates of target (x,y,z)
    NNet.Game.SSelectionDeltaEvent
      = unit info clicks? (_eventid = 28)
    NNet.Game.SControlGroupUpdateEvent
      = not useful, players changing control group / activatables? (_eventid = 29)
    NNet.Game.STriggerChatMessageEvent
      = hard to analyse, chat (_eventid = 32)
    NNet.Game.STriggerPingEvent
      = hard to analyse, pings (_eventid = 36)
    NNet.Game.SUnitClickEvent
      = space bar center? (_eventid = 39)
    NNet.Game.STriggerSoundOffsetEvent
      = when heroes make sounds? (_eventid = 46)
    NNet.Game.STriggerTransmissionOffsetEvent
      = change server/ channel? (_eventid = 47)
    NNet.Game.STriggerTransmissionCompleteEvent
      = change server/ channel? (_eventid = 48)
    NNet.Game.SCameraUpdateEvent
      = cammera move/scroll (_eventid = 49)
    NNet.Game.STriggerDialogControlEvent
      = voice lines? (_eventid = 55)
    NNet.Game.STriggerSoundLengthSyncEvent
      = not useful, sync announcer (probably) (_eventid = 56)
    NNet.Game.STriggerSoundtrackDoneEvent
      = trigger announcer (_eventid = 64)
    NNet.Game.STriggerKeyPressedEvent
      = start channel? (_eventid = 66)
    NNet.Game.STriggerCutsceneEndSceneFiredEvent
      = start / end of objective (_eventid = 98)
    NNet.Game.SGameUserLeaveEvent
      = not useful, players leave game (_eventid = 101)
    NNet.Game.SCommandManagerStateEvent
      = big file, ability / ults? (_eventid = 103)
    NNet.Game.SCmdUpdateTargetPointEvent
      = big file, player move commands? (_eventid = 104)
      has coordinates
    NNet.Game.SCmdUpdateTargetUnitEvent
      = point clicks? (_eventid = 105)
      has coordinates
    NNet.Game.SHeroTalentTreeSelectedEvent
      = pick talents (_eventid = 110)



Message events:
    
    _eventid = 0, event = NNet.Game.SChatMessage
    _eventid = 1, event = NNet.Game.SPingMessage
    _eventid = 2, event = NNet.Game.SLoadingProgressMessage
    _eventid = 5, event = NNet.Game.SPlayerAnnounceMessage

Header:
    
    m_elapsedGameLoops
    

Details:
    
    m_hero = hero name
    m_name = player name
    m_teamId = 0 (left team) or 1 (right team)
    m_result = 1 (win) or 2 (lose)
    m_title = map name

## Version
The code has been last updated with the [heroprotocol 2.55.0.86938 - 07 Dec 2021 replay parser](https://github.com/Blizzard/heroprotocol/releases/tag/v2.55.0.86938)