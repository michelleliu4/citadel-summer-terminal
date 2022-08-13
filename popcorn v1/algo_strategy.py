from os import remove
import gamelib
import random
import math
import warnings
from sys import maxsize
import json
import copy
from gamelib import game_state
import time

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))
        self.midgame = 0



    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0
        # This is a good place to do initial setup
        self.scored_on_side = set()
        self.scored_times = set()
        self.self_destruct_times = set()
        self.interceptor_locations = [[3, 10], [24, 10], [6, 7], [21, 7]]
        self.initial_turret_locations = [[1, 12], [26, 12], [4, 11], [23, 11]]
        self.initial_wall_upgrades = [[4,12], [23, 12]]
        self.key_wall_upgrades = [[0,13], [5, 11], [27,13], [23, 12], [22, 11], [5, 11]]
        self.initial_wall_locations = [[0, 13], [27, 13], [2, 12], [4, 12], [23, 12], [25, 12], [5, 11], [22, 11], [6, 10], [21, 10], [6, 9], [21, 9], [7, 8], [20, 8], [8, 7], [9, 7], [10, 7], [11, 7], [12, 7], [13, 7], [14, 7], [15, 7], [16, 7], [17, 7], [18, 7], [19, 7]]
        self.additional_walls = [[5, 12], [22, 12], [21, 11], [6, 11]]
        self.additional_wall_upgrades = [[5,12],[22,12], [21, 11], [6, 11]]
        self.additional_turrets = [[5, 10],[22, 10]]
        self.support_locations = [[10, 5], [11, 5], [12, 5], [13, 5], [14, 5], [15, 5], [16, 5], [17, 5]]
        self.self_destruct_walls_left = [[3, 11]]
        self.self_destruct_walls_right = [[24, 11]]
        self.is_far_away = False
        #positive means left neg means right 0 is no info
        self.enemy_spawn_side = 0


    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.

        self.starter_strategy(game_state)
        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """

        # First, place basic defenses
        if game_state.turn_number == 0:
            self.build_initial_defences(game_state)
        else:
            self.build_all(game_state)
        
        
            
    def build_all(self, game_state):
        self.build_initial_defences(game_state)
        if game_state.get_resource(1, 1) > 12:
            self.self_destruct(is_left)
        game_state.attempt_spawn(WALL, self.additional_walls)
        game_state.attempt_upgrade(self.key_wall_upgrades)
        game_state.attempt_spawn(TURRET, self.additional_turrets)
        game_state.attempt_upgrade(self.initial_turret_locations)
        game_state.attempt_upgrade(self.additional_turrets)
        game_state.attempt_spawn(SUPPORT, self.support_locations)

        
    def self_destruct(self, is_left):
        if is_left:
            game_state.attempt_spawn(WALL, self.self_destruct_walls_left)
            game_state.attempt_remove(self.self_destruct_walls_left)
            if self.is_far_away:
                game_state.attempt_spawn(WALL, [7, 7])
                game_state.attempt_remove([7,7])
                game_state.attempt_spawn(INTERCEPTOR, [6, 7], 1) #change if notice a lot of supports
            else:
                game_state.attempt_spawn(WALL, [[5, 9]])
                game_state.attempt_remove([5,9])
                game_state.attempt_spawn(INTERCEPTOR, [4, 9], 1) #change if notice a lot of supports
        else:
            game_state.attempt_spawn(WALL, self.self_destruct_walls_right)
            if self.is_far_away:
                game_state.attempt_spawn(WALL, [[20, 7]])
                game_state.attempt_remove([20,7])
                game_state.attempt_spawn(INTERCEPTOR, [21, 7], 1) #change if notice a lot of supports
            else:
                game_state.attempt_spawn(WALL, [[22, 9]])
                game_state.attempt_remove([22, 9])
                game_state.attempt_spawn(INTERCEPTOR, [23, 9], 1) #change if notice a lot of supports
        
    def offensive_strategy(self, game_state):
        #if past turn did a lot of damag/scored, keep sending scouts for pressure?
        if game_state.get_resource(1) > 12:
            game_state.attempt_spawn(DEMOLISHER, [23, 9], 4)
            game_state.attempt_spawn(SCOUT, [24, 10], 100)
        else:
            if game_state.get_resource(1, 1) > 15:
                game_state.attempt_spawn(INTERCEPTOR, [21, 8], 1)
                game_state.attempt_spawn(INTERCEPTOR, [19, 7], 1)

    def build_initial_defences(self, game_state):        
        game_state.attempt_spawn(WALL, self.initial_wall_locations)
        game_state.attempt_spawn(TURRET, self.initial_turret_locations)    
        game_state.attempt_upgrade(self.initial_wall_upgrades)

    def build_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where enemy demolishers can attack them.
        """
        # Useful tool for setting up your base locations: https://www.kevinbai.design/terminal-map-maker
        # More community tools available at: https://terminal.c1games.com/rules#Download

        wall_locations = [[0, 13], [1, 13], [2, 13], [3, 13], [4, 13], [5, 13], [6, 13],
                          [26, 13], [27, 13], [6, 12], [6, 11], [8, 11], [25, 11], [6, 10],
                          [8, 10], [9, 10], [24, 10], [8, 9], [23, 9], [9, 8], [22, 8], [9, 7],
                          [21, 7], [10, 6], [20, 6], [10, 5], [11, 5], [12, 5], [13, 5], [14, 5],
                          [15, 5], [16, 5], [17, 5], [18, 5], [19, 5]]
        #TODO Left side of funnel is super vunerable
        turret_locations = [[3, 12], [5, 12], [26, 12], [5, 11], [1, 12], [5, 10], [9, 9], [8, 8]]
        support_locations = [[4, 12], [4, 11], [8, 7], [9, 6], [11, 4], [12, 3]]

        game_state.attempt_spawn(TURRET, turret_locations)
        game_state.attempt_spawn(WALL, wall_locations)    
        game_state.attempt_spawn(SUPPORT, support_locations)

        wall_upgradable = [[0, 13], [1, 13], [2, 13], [3, 13], [4, 13], [5, 13], [6, 13], [26, 13],
                           [27, 13], [6, 12], [6, 11], [8, 11], [25, 11], [6, 10], [8, 10], [9, 10], [8, 9]]

        # upgrade walls so they soak more damage
        if game_state.turn_number % 3 == 0:
            game_state.attempt_upgrade(wall_upgradable)
            game_state.attempt_upgrade(turret_locations)
            game_state.attempt_upgrade(support_locations)


    def stall_with_interceptors(self, game_state):
        """
        Send out interceptors at random locations to defend our base from enemy moving units.
        """
        # We can spawn moving units on our edges so a list of all our edge locations
        friendly_edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)
        
        # Remove locations that are blocked by our own structures 
        # since we can't deploy units there.
        deploy_locations = self.filter_blocked_locations(friendly_edges, game_state)
        
        # While we have remaining MP to spend lets send out interceptors randomly.
        while game_state.get_resource(MP) >= game_state.type_cost(INTERCEPTOR)[MP] and len(deploy_locations) > 0:
            # Choose a random deploy location.
            deploy_index = random.randint(0, len(deploy_locations) - 1)
            deploy_location = deploy_locations[deploy_index]
            
            game_state.attempt_spawn(INTERCEPTOR, deploy_location)
            """
            We don't have to remove the location since multiple mobile 
            units can occupy the same space.
            """

    def demolisher_line_strategy(self, game_state):
        """
        Build a line of the cheapest stationary unit so our demolisher can attack from long range.
        """
        # First let's figure out the cheapest unit
        # We could just check the game rules, but this demonstrates how to use the GameUnit class
        stationary_units = [WALL, TURRET, SUPPORT]
        cheapest_unit = WALL
        for unit in stationary_units:
            unit_class = gamelib.GameUnit(unit, game_state.config)
            if unit_class.cost[game_state.MP] < gamelib.GameUnit(cheapest_unit, game_state.config).cost[game_state.MP]:
                cheapest_unit = unit

        # Now let's build out a line of stationary units. This will prevent our demolisher from running into the enemy base.
        # Instead they will stay at the perfect distance to attack the front two rows of the enemy base.
        for x in range(27, 5, -1):
            game_state.attempt_spawn(cheapest_unit, [x, 11])

        # Now spawn demolishers next to the line
        # By asking attempt_spawn to spawn 1000 units, it will essentially spawn as many as we have resources for
        game_state.attempt_spawn(DEMOLISHER, [24, 10], 1000)

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
            damages.append(damage)
        
        # Now just return the location that takes the least damage
        return location_options[damages.index(min(damages))]

    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units
        
    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        spawns = state["spawn"]
        breaches = events["breach"]
        self_destructs = events["selfDestruct"]
        curr_frame = state["turnInfo"][2]
        for spawn in spawns:
            if spawn[1] > 2 and spawn[3] == 2:
                location = spawn[0]
                self.enemy_spawn_side = 13.5 - location[0]
                


        for self_destruct in self_destructs:
            unit_owner_self = True if self_destruct[5] == 1 else False
            if not unit_owner_self and curr_frame > 5:
                self.self_destruct_times.add(curr_frame)
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))

                if(location[0] <= 13): #left
                    self.scored_on_side.add(1)
                else:
                    self.scored_on_side.add(-1)
                self.scored_times.add(curr_frame)


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
