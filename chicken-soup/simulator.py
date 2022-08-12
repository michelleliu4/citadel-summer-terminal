import gamelib, copy, time
from gamelib.game_map import GameMap
from gamelib.game_state import is_stationary
from gamelib.util import time_this
import math

def euc_dist(a, b):

    return math.sqrt(((a.x - b.x) ** 2) + (a.y - b.y) ** 2)

def calculate_shield_bonus(support):

    y = support.y

    if support.player_index == 1:

        y = 28 - y

    return y * support.shieldBonusPerY

class Simulator():

    def __init__(self, game_state):

        self.game_state = game_state

        self.edges = game_state.game_map.get_edges()

        self.pathfinder = gamelib.navigation.ShortestPathFinder()

        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, REMOVE, UPGRADE, STRUCTURE_TYPES, ALL_UNITS, UNIT_TYPE_TO_INDEX
        UNIT_TYPE_TO_INDEX = {}
        WALL = self.game_state.config["unitInformation"][0]["shorthand"]
        UNIT_TYPE_TO_INDEX[WALL] = 0
        SUPPORT = self.game_state.config["unitInformation"][1]["shorthand"]
        UNIT_TYPE_TO_INDEX[SUPPORT] = 1
        TURRET = self.game_state.config["unitInformation"][2]["shorthand"]
        UNIT_TYPE_TO_INDEX[TURRET] = 2
        SCOUT = self.game_state.config["unitInformation"][3]["shorthand"]
        UNIT_TYPE_TO_INDEX[SCOUT] = 3
        DEMOLISHER = self.game_state.config["unitInformation"][4]["shorthand"]
        UNIT_TYPE_TO_INDEX[DEMOLISHER] = 4
        INTERCEPTOR = self.game_state.config["unitInformation"][5]["shorthand"]
        UNIT_TYPE_TO_INDEX[INTERCEPTOR] = 5

        self.can_attack = [TURRET, SCOUT, DEMOLISHER, INTERCEPTOR]

        self.removal_needed = False
        self.mobile_units_remain = True

        self.units = []

        # the only time we iterate through the game map, yaaay!
        for cell in self.game_state.game_map:

            self.units += self.game_state.game_map[cell]

        self.enemy_health_damage = 0

    def units_in_range(self, unit, units, r, f=lambda x: True):
        # this probably doesn't have to be a class method since self isn't used at all but also who cares

        o = []

        for target in units:

            if euc_dist(unit, target) > r:

                continue

            if target == unit:

                continue

            if not f(target):

                continue
            
            o.append(target)

        return o

    def pathfind_all(self):
        
        # format of key is "{x},{y},{target_edge}" - this saves time for stacked units with the same target
        cache = {}

        self.mobile_units_remain = False

        for unit in self.units:

            if is_stationary(unit.unit_type) or not unit.active:

                continue

            k = f"{unit.x},{unit.y},{unit.target_edge}"

            self.mobile_units_remain = True

            if k in cache:

                unit.path = cache[k]
            
            else:

                #gamelib.debug_write(f"pathfinding for edge {unit.target_edge} at {unit.x},{unit.y}")

                path = self.pathfinder.navigate_multiple_endpoints_faster([unit.x, unit.y], self.edges[unit.target_edge], self.game_state, self.units)
                unit.path = path
                cache[k] = path

        
    def move_all(self):

        for unit in self.units:

            if is_stationary(unit.unit_type):
                
                continue

            if unit.frames_until_move > 0:

                unit.frames_until_move -= 1
                continue

            if unit.path == [[unit.x, unit.y]] or unit.path == []:

                if [unit.x, unit.y] in self.edges[unit.target_edge]:

                    self.enemy_health_damage += 1
                    #gamelib.debug_write(f"unit {unit} scores on enemy.")
                    unit.active = False
                    self.removal_needed = True
                    continue

                # self destruct
                self.handle_self_destruct(unit)
                continue

            # getting next location of unit
            next_loc = unit.path[0]
            
            if next_loc == [[unit.x, unit.y]]:

                next_loc = unit.path[1]
                unit.path = unit.path[2:]
            
            else:

                unit.path = unit.path[1:]

            unit.x, unit.y = next_loc
            unit.frames_until_move = unit.speed # possibly correct

            #gamelib.debug_write(f"move_unit at {unit.x},{unit.y}")

            # unit has been moved?

    def attack_all(self):

        # cache the targetable units at a given location bc when units are stacked it saves a fuckload of time
        cache = {}

        for unit in self.units:

            if unit.unit_type not in self.can_attack or not unit.active:
                
                continue
            
            gamelib.debug_write(f"unit {unit} looking for targets")

            if f"{unit.x},{unit.y}" in cache:
                # then we can use cached targets
                targets = cache[f"{unit.x},{unit.y}"]

            else:

                targets = self.units_in_range(unit, self.units, unit.attackRange, f=lambda x: x.player_index != unit.player_index and x.active)
                cache[f"{unit.x},{unit.y}"] = targets

            if targets == []:
                continue
            
            target = self.game_state.get_target_from_units(unit, targets)
            gamelib.debug_write(f"{target} targeted by {unit}")

            self.handle_attack(unit, target)

    def support_all(self):

        # MAYBE ALLOW SUPPORT UNITS TO KEEP TRACK OF UNITS IT HASN'T YET SUPPORTED - then only check if those units are in range, and remove
        # them from the list once they're supported. This prevents a lot of unit-list loops and cuts time down.

        for unit in self.units:

            if unit.unit_type != SUPPORT:

                continue
            
            # very nice little filter idea here haha, saves some time
            targets = self.units_in_range(unit, self.units, unit.shieldRange, 
                                          f=lambda x: (x.player_index == unit.player_index) and (not is_stationary(x.unit_type)) and (unit not in x.supported_by) and x.active)

            for target in targets:

                target.shield += unit.shieldPerUnit + calculate_shield_bonus(unit)
                #gamelib.debug_write(f"unit at {unit.x},{unit.y} supported {target}")
                target.supported_by.append(unit)

    def handle_self_destruct(self, unit):

        r = 1.5

        # this is config-dependent
        if unit.unit_type == INTERCEPTOR:
            r = 9

        targets = self.units_in_range(unit, self.units, r, f=lambda x: x.player_index != unit.player_index and x.active)

        for target in targets:

            self.damage_unit(target, unit.health)

        unit.health = 0
        self.removal_needed = True
        #gamelib.debug_write(f"{unit} self destructed")


    def handle_attack(self, attacker, target):

        if is_stationary(target.unit_type):
            damage_unit(target, attacker.damage_f)
            return
        
        self.damage_unit(target, attacker.damage_i)

        gamelib.debug_write(f"unit {attacker} damages {target}")

    def remove_destroyed(self):

        self.mobile_units_remain = False

        n = []

        stationary_units_destroyed = False

        for unit in self.units:

            if unit.health > 0 and unit.active:

                n.append(unit)

                if not is_stationary(unit.unit_type):

                    self.mobile_units_remain = True

                #gamelib.debug_write(f"unit {unit} remains")

                continue
            
            if is_stationary(unit.unit_type):

                stationary_units_destroyed = True

            gamelib.debug_write(f"unit {unit} destroyed")

        # this basically forgets the old units
        self.units = n

        return stationary_units_destroyed

    def damage_unit(self, target, amount):

        total = target.health + target.shield
        after_attack = max(0, total - amount)
        if after_attack < target.max_health:
            target.health = after_attack
            target.shield = 0
            return
        target.health = target.max_health
        target.shield = after_attack - target.max_health

        if target.health == 0: 
            self.removal_needed = True

    def simulate(self):

        t = {'path':0, 'support':0, 'move':0, 'attack':0, 'removal':0}

        stationary_units_destroyed = True

        frame_count = 0

        while self.mobile_units_remain:

            gamelib.debug_write(f"simulating frame {frame_count}")

            if stationary_units_destroyed:
                t1 = time.perf_counter()
                self.pathfind_all()
                t2 = time.perf_counter()
                t['path'] += t2 - t1
                stationary_units_destroyed = False
            
            t3 = time.perf_counter()
            self.support_all()
            t4 = time.perf_counter()
            self.move_all()
            t5 = time.perf_counter()
            self.attack_all()
            t6 = time.perf_counter()

            t['support'] += t4 - t3
            t['move'] += t5 - t4
            t['attack'] += t6 - t5 

            if self.removal_needed:
                t7 = time.perf_counter()
                stationary_units_destroyed = self.remove_destroyed()
                t8 = time.perf_counter()
                t['removal'] += t8 - t7
                self.removal_needed = False
            #gamelib.debug_write(f"{stationary_units_destroyed=}, {self.mobile_units_remain=}")
            frame_count += 1

        return {'times': t, 'score': self.enemy_health_damage}







                



