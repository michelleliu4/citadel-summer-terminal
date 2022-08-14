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
import simulator

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

def count_sp_damage(result):

    t = 0

    su = {TURRET: 6, WALL: 0.5, SUPPORT: 4}
    su_u = {TURRET: 10, WALL: 2, SUPPORT: 6}

    for k in result['enemy_units_destroyed']:

        if k in su:

            t += result['enemy_units_destroyed'][k] * su[k]
    
    for k in result['enemy_upgraded_units_destroyed']:

        if k in su_u:
        
            t += result['enemy_upgraded_units_destroyed'][k] * su_u[k]

    return t

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
        self.interceptor_locations = [[3, 10], [24, 10], [6, 7], [21, 7]]
        self.initial_turret_locations = [[1, 12], [26, 12], [4, 11], [23, 11]]
        self.initial_wall_upgrades = [[4,12], [23, 12]]
        self.key_wall_upgrades = [[0,13], [5, 11], [27,13], [23, 12], [22, 11], [5, 11]]
        self.initial_wall_locations = [[0, 13], [27, 13], [2, 12], [4, 12], [23, 12], [25, 12], [5, 11], [22, 11], [6, 10], [21, 10], [6, 9], [21, 9], [7, 8], [20, 8], [8, 7], [9, 7], [10, 7], [11, 7], [12, 7], [13, 7], [14, 7], [15, 7], [16, 7], [17, 7], [18, 7], [19, 7]]
        self.additional_walls = [[5, 12], [22, 12], [21, 11], [6, 11], [1, 13], [2, 13], [25, 13], [26, 13], [2, 12], [25, 12]]
        self.additional_wall_upgrades = [[5,12],[22,12], [21, 11], [6, 11], [1, 13], [2, 13], [25, 13], [26, 13], [6, 11], [6, 10], [6, 9]]
        self.additional_turrets = [[5, 10],[22, 10], [25, 11], [2, 11]]
        self.support_locations = [[10, 5], [11, 5], [12, 5], [13, 5], [14, 5], [15, 5], [16, 5], [17, 5]]
        self.additional_support_locations = [[8, 8], [9, 8], [10, 8], [11, 8], [12, 8], [13, 8], [14, 8], [15, 8], [16, 8], [17, 8], [18, 8], [19, 8]]
        self.self_destruct_walls_left = [[3, 11]]
        self.self_destruct_walls_right = [[24, 11]]
        self.anti_self_destruct_walls = [[10, 5], [11, 5], [12, 5], [13, 5], [14, 5], [15, 5], [16, 5], [17, 5], [18, 5]]

        self.is_far_away = True
        self.is_left = True
        #positive means left neg means right 0 is no info
        self.enemy_spawn_side = 0
        self.enemy_support_count = 0
        self.num_enemy_self_destructs = 0
        self.cheap_attacks = 0

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
        self.funnel_location(game_state)
        self.starter_strategy(game_state)
        if game_state.turn_number % 10 == 0:
            self.num_enemy_self_destructs = 0
        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """


    def recreate(self, game_state, points):
        gameMap = game_state.game_map
        for point in points:
            if len(point) != 1:
                continue
            currUnit = gameMap[point][0]
            if currUnit.health/currUnit.max_health < 0.5:
                game_state.attempt_remove(point)
    
    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """

        #self.can_attack = True

        # First, place basic defenses
        if game_state.turn_number == 0:
            self.build_initial_defences(game_state)
        else:
            self.build_all(game_state)

        # after self_destruct defense...
        #if self.can_attack:
        if self.num_enemy_self_destructs > 2:
            self.delayed_attack(game_state)
        else:
            self.attack(game_state)

        # remove funnel blocks:
        game_state.attempt_remove([24, 12])
        game_state.attempt_remove([3, 12])
    
    def attack(self, game_state):

        r = random.randint(0, 4)

        def left_funnel(strat):

            def o(state, info):

                if state.attempt_spawn(WALL, [24, 12]) != 0:
                    return strat(state, info)
                return state

            return o

        def right_funnel(strat):

            def o(state, info):

                if state.attempt_spawn(WALL, [3, 12]) != 0:
                    return strat(state, info)
                return state

            return o
        
        def scout_follows_demo_l(state, info):

            if state.number_affordable(SCOUT) > 16 + r:

                state.attempt_spawn(DEMOLISHER, [7, 6], 3)
                state.attempt_spawn(SCOUT, [6, 7], 100)

            return state

        def scout_on_demo_l(state, info):

            if state.number_affordable(SCOUT) > 16 + r:

                state.attempt_spawn(DEMOLISHER, [7, 6], 3)
                state.attempt_spawn(SCOUT, [7, 6], 100)

            return state

        def demo_only_l(state, info):

            if state.number_affordable(SCOUT) > 18 + r:

                state.attempt_spawn(DEMOLISHER, [7, 6], 100)

            return state

        def demo_only_l_cheap(state, info):

            if state.number_affordable(SCOUT) > 6 + r and state.number_affordable(SCOUT) <= 12:

                state.attempt_spawn(DEMOLISHER, [7, 6], 4)

            return state

        def scout_only_l(state, info):

            if state.number_affordable(SCOUT) > 15 - r:

                state.attempt_spawn(SCOUT, [7, 6], 100)

            return state

        def scout_only_l_cheap(state, info):

            if state.number_affordable(SCOUT) > 11 - r and state.number_affordable(SCOUT) <= 11:

                state.attempt_spawn(SCOUT, [7, 6], 11)

            return state

        def demo_follows_interceptor_l(state, info):

            if state.number_affordable(SCOUT) > 18 + r:
                
                state.attempt_spawn(INTERCEPTOR, [24, 10], 3)
                state.attempt_spawn(DEMOLISHER, [7, 6], 100)
                
            return state

        def demo_follows_scout_l(state, info):
            if state.number_affordable(SCOUT) > 15 + r:
                state.attempt_spawn(SCOUT, [7, 6], 3)
                state.attempt_spawn(DEMOLISHER, [6, 7], 100)

            return state

        def demo_follows_scout_r(state, info):
            if state.number_affordable(SCOUT) > 15 + r:
                state.attempt_spawn(SCOUT, [20, 6], 3)
                state.attempt_spawn(DEMOLISHER, [21, 7], 100)

            return state

        def scout_follows_demo_r(state, info):

            if state.number_affordable(SCOUT) > 16 + r:

                state.attempt_spawn(DEMOLISHER, [20, 6], 3)
                state.attempt_spawn(SCOUT, [21, 7], 100)

            return state
        def demo_follows_scout_r(state, info):

            if state.number_affordable(SCOUT) > 16 + r:

                state.attempt_spawn(SCOUT, [20, 6], 3)
                state.attempt_spawn(DEMOLISHER, [21, 7], 100)

            return state

        def scout_on_demo_r(state, info):

            if state.number_affordable(SCOUT) > 16 + r:

                state.attempt_spawn(DEMOLISHER, [20, 6], 4)
                state.attempt_spawn(SCOUT, [20, 6], 100)

            return state

        def demo_only_r(state, info):

            if state.number_affordable(SCOUT) > 18 + r:

                state.attempt_spawn(DEMOLISHER, [20, 6], 100)

            return state

        def demo_only_r_cheap(state, info):

            if state.number_affordable(SCOUT) > 6 + r and state.number_affordable(SCOUT) <= 12:

                state.attempt_spawn(DEMOLISHER, [20, 6], 4)

            return state

        def scout_only_r(state, info):

            if state.number_affordable(SCOUT) > 15 - r:

                state.attempt_spawn(SCOUT, [20, 6], 100)

            return state

        def scout_only_r_cheap(state, info):

            if state.number_affordable(SCOUT) > 11 - r and state.number_affordable(SCOUT) <= 11:

                state.attempt_spawn(SCOUT, [20, 6], 11)

            return state

        def demo_follows_interceptor_r(state, info):

            if state.number_affordable(SCOUT) > 18 + r:
                
                state.attempt_spawn(INTERCEPTOR, [3, 10], 3)
                state.attempt_spawn(DEMOLISHER, [20, 6], 100)
                
            return state

        strats = [right_funnel(scout_follows_demo_l),
                  right_funnel(scout_on_demo_l),
                  right_funnel(demo_only_l),
                  right_funnel(demo_only_l_cheap),
                  right_funnel(scout_only_l),
                  right_funnel(scout_only_l_cheap),
                  right_funnel(demo_follows_interceptor_l),
                  right_funnel(scout_follows_demo_r),
                  left_funnel(scout_follows_demo_r),
                  left_funnel(scout_on_demo_r),
                  left_funnel(demo_only_r),
                  left_funnel(demo_only_r_cheap),
                  left_funnel(scout_only_r),
                  left_funnel(scout_only_r_cheap),
                  left_funnel(demo_follows_interceptor_r),
                  left_funnel(demo_follows_scout_l),
                  right_funnel(demo_follows_scout_l)]

        random.shuffle(strats)

        # what to do if no attack is chosen. in this case, close off one of the funnels
        def default(state, info):

            if self.is_left:
                state.attempt_spawn(WALL, [3, 12])
            else:
                state.attempt_spawn(WALL, [24, 12])


        def count_sp_damage(result):

            t = 0

            su = {TURRET: 6, WALL: 0.5, SUPPORT: 4}
            su_u = {TURRET: 10, WALL: 2, SUPPORT: 6}

            for k in result['enemy_units_destroyed']:

                if k in su:

                    t += result['enemy_units_destroyed'][k] * su[k]
            
            for k in result['enemy_upgraded_units_destroyed']:

                if k in su_u:
                
                    t += result['enemy_upgraded_units_destroyed'][k] * su_u[k]

            return t
        
        def new_opt(strats, results):

            m = 0
            i = 0

            for j, r in enumerate(results):
                
                cheap = False
                score = (r['friendly_score'] * 3 + count_sp_damage(r)) / (game_state.get_resource(1, 0) - r['mp']) if (game_state.get_resource(1, 0) - r['mp']) > 0 else 0
                
                if score > m:
                    m = score
                    i = j

            if m > 2.5:
                return strats[i]

            return None

        best = simulator.simulate_multiple(game_state, strats, {}, new_opt)

        if not best:

            default(game_state, {})
            # don't attack... no simulation rendered damage
            return

        best(game_state, {})

        return

    def delayed_attack(self, game_state):

        r = random.randint(0, 4)

        def right_funnel(strat):

            def o(state, info):
                
                if state.attempt_spawn(WALL, [3, 12]) != 0 or state.attempt_spawn(WALL, [18, 5]) != 0:
                    return strat(state, info)
                return state

            return o

        def scout_follows_demo_r(state, info):

            if state.number_affordable(SCOUT) > 16 + r:

                state.attempt_spawn(DEMOLISHER, [14, 0], 3)
                state.attempt_spawn(SCOUT, [18, 4], 100)

            return state
        def demo_follows_scout_r(state, info):

            if state.number_affordable(SCOUT) > 16 + r:

                state.attempt_spawn(DEMOLISHER, [18, 4], 3)
                state.attempt_spawn(SCOUT, [14, 0], 100)

            return state

        def scout_on_demo_r(state, info):

            if state.number_affordable(SCOUT) > 16 + r:

                state.attempt_spawn(DEMOLISHER, [14, 0], 4)
                state.attempt_spawn(SCOUT, [15, 1], 100)

            return state

        def demo_only_r(state, info):

            if state.number_affordable(SCOUT) > 18 + r:

                state.attempt_spawn(DEMOLISHER, [18, 4], 100)

            return state

        def demo_only_r_cheap(state, info):

            if state.number_affordable(SCOUT) > 6 + r and state.number_affordable(SCOUT) <= 12:

                state.attempt_spawn(DEMOLISHER, [18, 4], 4)

            return state

        def scout_only_r(state, info):

            if state.number_affordable(SCOUT) > 15 - r:

                state.attempt_spawn(SCOUT, [18, 4], 100)

            return state

        def scout_only_r_cheap(state, info):

            if state.number_affordable(SCOUT) > 11 - r and state.number_affordable(SCOUT) <= 11:

                state.attempt_spawn(SCOUT, [18, 4], 11)

            return state

        # what to do if no attack is chosen. in this case, close off one of the funnels
        def default(state, info):

            if self.is_left:
                state.attempt_spawn(WALL, [3, 12])
            else:
                state.attempt_spawn(WALL, [24, 12])


        def new_opt(strats, results):

            m = 0
            i = 0

            cheap_chosen = False

            for j, r in enumerate(results):
                
                cheap = False
                score = (r['friendly_score'] * 3 + count_sp_damage(r)) / (game_state.get_resource(1, 0) - r['mp']) if (game_state.get_resource(1, 0) - r['mp']) > 0 else 0
                if game_state.get_resource(1, 0) - r['mp'] <= 12:
                    cheap = True
                if cheap and self.cheap_attacks >= 3:
                    continue
                
                if score > m:
                    m = score
                    i = j
                    if cheap: cheap_chosen = True
                    else: cheap_chosen = False

            if m > 2.7:
                if cheap_chosen:
                    self.cheap_attacks += 1
                else:
                    self.cheap_attacks = 0
                return strats[i]

            return None

        strats =  [right_funnel(scout_follows_demo_r),
                  right_funnel(scout_follows_demo_r),
                  right_funnel(scout_on_demo_r),
                  right_funnel(demo_only_r),
                  right_funnel(demo_only_r_cheap),
                  right_funnel(scout_only_r),
                  right_funnel(scout_only_r_cheap),
                  right_funnel(demo_follows_scout_r)]

        random.shuffle(strats)

        best = simulator.simulate_multiple(game_state, strats, {}, new_opt)

        if not best:

            default(game_state, {})
            # don't attack... no simulation rendered damage
            return

        best(game_state, {})

        return
    
    def build_all(self, game_state):
        self.build_initial_defences(game_state)
        ran = random.randint(0, 100)
        if game_state.get_resource(1, 1) > 12 and self.enemy_spawn_side != 0 and ran > 50:
            self.self_destruct(self.is_left, game_state)
        game_state.attempt_spawn(WALL, self.additional_walls)
        self.recreate(game_state, self.additional_walls)
        game_state.attempt_upgrade(self.key_wall_upgrades)
        game_state.attempt_spawn(TURRET, self.additional_turrets)
        self.recreate(game_state, self.additional_turrets)
        game_state.attempt_upgrade(self.additional_wall_upgrades)
        game_state.attempt_upgrade(self.initial_turret_locations)
        game_state.attempt_upgrade(self.additional_turrets)
        if game_state.get_resource(0) > 8:
            game_state.attempt_spawn(SUPPORT, self.additional_support_locations)
            game_state.attempt_upgrade(self.additional_support_locations)
        
    def funnel_location(self, game_state):
        right_start = game_state.find_path_to_edge([16, 25])
        left_start = game_state.find_path_to_edge([11, 25])
        if right_start != None:
            for path in right_start:
                if path[1] == 14:
                    if path[0] > 13:
                        self.is_left = False
                    else:
                        self.is_left = True
        elif left_start != None:
            for path in right_start:
                if path[1] == 14:
                    if path[0] > 13:
                        self.is_left = False
                    else:
                        self.is_left = True

        
    def self_destruct(self, is_left, game_state):
        spawn = 1
        if self.enemy_support_count > 5:
            spawn = 2
        if self.is_left and self.enemy_spawn_side > 0:
            gamelib.debug_write(1)
            self.is_far_away = False
        if not self.is_left and self.enemy_spawn_side > 0:
            gamelib.debug_write(2)

            self.is_far_away = True
        if self.is_left and self.enemy_spawn_side < 0:
            gamelib.debug_write(3)

            self.is_far_away = True
        if not self.is_left and self.enemy_spawn_side < 0:
            gamelib.debug_write(4)

            self.is_far_away = False
        if is_left:
            game_state.attempt_spawn(WALL, self.self_destruct_walls_left)
            game_state.attempt_remove(self.self_destruct_walls_left)
            if self.is_far_away:
                game_state.attempt_spawn(WALL, [7, 7])
                game_state.attempt_remove([7,7])
                game_state.attempt_spawn(INTERCEPTOR, [6, 7], spawn) #change if notice a lot of supports
            else:
                game_state.attempt_spawn(WALL, [[5, 9]])
                game_state.attempt_remove([5,9])
                game_state.attempt_spawn(INTERCEPTOR, [4, 9], spawn) #change if notice a lot of supports
        else:
            game_state.attempt_spawn(WALL, self.self_destruct_walls_right)
            game_state.attempt_remove(self.self_destruct_walls_right)
            if self.is_far_away:
                game_state.attempt_spawn(WALL, [[20, 7]])
                game_state.attempt_remove([20,7])
                game_state.attempt_spawn(INTERCEPTOR, [21, 7], spawn) #change if notice a lot of supports
            else:
                game_state.attempt_spawn(WALL, [[22, 9]])
                game_state.attempt_remove([22, 9])
                game_state.attempt_spawn(INTERCEPTOR, [23, 9], spawn) #change if notice a lot of supports
        
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
        self.recreate(game_state, self.initial_wall_locations)
        game_state.attempt_spawn(TURRET, self.initial_turret_locations)
        self.recreate(game_state, self.initial_turret_locations)    
        game_state.attempt_upgrade(self.initial_wall_upgrades)
        self.recreate(game_state, self.initial_wall_upgrades)
        if self.num_enemy_self_destructs > 2:
            game_state.attempt_spawn(WALL, [[i, 5] for i in range(10, 18)])


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
        spawns = events["spawn"]
        breaches = events["breach"]
        self_destructs = events["selfDestruct"]
        curr_frame = state["turnInfo"][2]
        self.enemy_support_count = len(state["p2Units"][1])
        
        for spawn in spawns:
            if spawn[1] == 3 or spawn[1] == 4 and spawn[3] == 2:
                location = spawn[0]
                self.enemy_spawn_side = 13.5 - location[0]
        
        for self_destruct in self_destructs:
            unit_owner_self = True if self_destruct[5] == 1 else False
            if not unit_owner_self and self_destruct[3] == 5:
                self.num_enemy_self_destructs +=1
                break
                
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
