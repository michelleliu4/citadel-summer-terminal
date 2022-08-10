import gamelib, copy
from gamelib.game_map import GameMap
from gamelib.game_state import is_stationary

def targets(units):

    targets = []

    for unit in units:

        if (unit.target_edge not in targets) and not is_stationary(unit.unit_type):

            targets.append(unit.target_edge)

    return targets

def conditional_append(l, e):

    if l == []:
        l += [e]
        return
    
    l.append(e)

def damage_unit(target, amount):

    total = target.health + target.shield
    after_attack = max(0, total - amount)
    if after_attack < target.max_health:
        target.health = after_attack
        target.shield = 0
        return
    target.health = target.max_health
    target.shield = after_attack - target.max_health

def calculate_shield_bonus(support):

    y = support.y

    if support.player_index == 1:

        y = 28 - y

    return y * support.shieldBonusPerY

class Simulator():

    def __init__(self, game_state):

        self.game_state = game_state
        # game state _deploy/build_stack can be referenced for deployment order of moving units
        # if more precision is necessary, unit class can have attribute tracking deploy/build number
        # allowing for units to be sorted accordingly at the beginning of a simulation by age

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

        self.it = GameMap(self.game_state.config)

    def pathfind_all(self):

        for cell in self.it: # would like to avoid this deepcopy - not sure why it's necessary

            #gamelib.debug_write(f"{cell}")

            if self.game_state.game_map[cell] == []:

                continue
            
            #gamelib.debug_write(f"units at {cell} (pathfind_all)")

            tpd = [None, None, None, None]

            for target in targets(self.game_state.game_map[cell]):

                tpd[target] = self.pathfinder.navigate_multiple_endpoints(cell, self.edges[target], self.game_state)
                #gamelib.debug_write(f"pathfinding at {cell} for edge {target}")

            for unit in self.game_state.game_map[cell]:

                if is_stationary(unit.unit_type):

                    break

                unit.path = [x for x in tpd[unit.target_edge]] # do a deepcopy here to ensure that units don't reference the same 
                # path by accident (then popping becomes catastrophic)
                #gamelib.debug_write(f"unit {unit} assigned path {unit.path}")

    def move_all(self):

        for cell in self.it:

            if self.game_state.game_map[cell] == []:

                continue

            remaining = []

            for i in range(len(self.game_state.game_map[cell])):

                unit = self.game_state.game_map[cell][i]

                if is_stationary(unit.unit_type):

                    remaining.append(unit)
                    break

                gamelib.debug_write(f"non-stationary unit at {cell}")

                if unit.frames_until_move > 0:
                    
                    unit.frames_until_move -= 1
                    remaining.append(unit)
                    continue
                    
                if unit.path == [] or unit.path == [cell]:
                    # unit self-destructs
                    # technically check if unit has moved some number of spaces here, but in the 
                    # current config it doesn't matter
                    remaining.append(unit)
                    self.handle_self_destruct(unit)                  
                    continue
                
                # i wish python had do {} while ();
                # anyways, get the next position to move to
                next_loc = unit.path[0]
                unit.path = unit.path[1:]

                if next_loc == cell:

                    next_loc = unit.path[0]
                    unit.path = unit.path[1:]
                
                gamelib.debug_write(f"next_loc = {next_loc}")

                #if not self.game_state.game_map.in_arena_bounds(next_loc):

                #    # player # unit.player_index has scored, might want more stuff here
                #    gamelib.debug_write(f"player {abs(unit.player_index - 1)} scored on by {unit}")
                #    # unit gets deleted since we don't move it to a new cell, and it isn't in remaining
                #    continue
                
                unit.x, unit.y = next_loc
                unit.frames_until_move = unit.speed #unit speed? check this
                self.append_game_map_list(next_loc, unit)
                gamelib.debug_write(f"unit {unit} moved")
                # gamelib.debug_write(f"proof {self.game_state.game_map[next_loc]}")

            self.game_state.game_map.remove_unit(cell)
            self.game_state.game_map[cell] = remaining

    def attack_all(self):

        # now's when specific orders are important, although are they really?
        # the docs say that units attack even if their health is 0, but will not be targeted
        # if it's 0, so the order of attack doesn't really change anything right? I guess
        # it changes exactly which units are attacked by which other units, however the same amount of
        # damage is done to the enemy in either case, (although since negative health gets corrected to 0,
        # attacking a low health unit with a high damage unit wastes more, however this is not depended on the
        # order of spawning....)
        
        attacking_units = [TURRET, INTERCEPTOR, SCOUT, DEMOLISHER] # define this

        for cell in self.it:

            for unit in self.game_state.game_map[cell]:

                if unit.unit_type not in attacking_units:
                    continue

                target = self.game_state.get_target(unit)

                if target == None:
                    # no units in range
                    continue
                
                self.handle_attack(unit, target)
        
        #for cell in self.game_state.game_map:

        #    remaining = []

        #    for unit in self.game_state.game_map[cell]:

        #        if unit.health != 0:
        #            remaining.append(unit)
                
        #    self.game_state.game_map[cell] = remaining

    def support_all(self):

        for cell in self.it:

            if self.game_state.game_map[cell] == [] or len(self.game_state.game_map[cell]) > 1:

                continue

            unit = self.game_state.game_map[cell][0]

            if unit.unit_type != SUPPORT:

                continue

            possible_locations = self.game_state.game_map.get_locations_in_range(cell, unit.shieldRange)

            for location in possible_locations:

                if self.game_state.game_map[location] == []:

                    continue

                for target in self.game_state.game_map[location]:

                    if target.player_index != unit.player_index or is_stationary(target) or unit in target.supported_by:

                        continue 

                    target.shield += unit.shieldPerUnit + calculate_shield_bonus(unit)
                    target.supported_by.append(unit)
                    gamelib.debug_write(f"unit {target} receives support from {unit}")

    def handle_self_destruct(self, unit):
        loc = [unit.x, unit.y]
        sd_range = 9

        if unit.unit_type in [SCOUT, DEMOLISHER]: # this probably doesn't work, need to use numbers haha
            sd_range = 1.5

        possible_locations = self.game_state.game_map.get_locations_in_range(loc, sd_range)

        for location in possible_locations:

            if self.game_state.game_map[location] == []:

                continue

            for target in self.game_state.game_map[location]:

                if target.player_index == unit.player_index:

                    continue

                damage_unit(target, unit.health)

        gamelib.debug_write(f"unit {unit} self destructs")
        unit.health = 0


    def handle_attack(self, attacker, target):

        towers = []

        if target.unit_type in towers:
            damage_unit(target, attacker.damage_f)
            return
        
        damage_unit(target, attacker.damage_i)

        gamelib.debug_write(f"unit {attacker} damages {target}")

    def remove_destroyed(self):

        stationary_destroyed = False
        mobile_units_remain = False

        for cell in self.it:

            remaining = []

            for i in range(len(self.game_state.game_map[cell])):
                
                unit = self.game_state.game_map[cell][i]
                
                if unit.health != 0:

                    remaining.append(unit)

                    if not is_stationary(unit):
                        gamelib.debug_write(f"mobile unit {unit} still exists") # ISSUE HERE IS THE is_stationary FUNCTION! It don't work!
                        mobile_units_remain = True

                    continue

                if is_stationary(unit):

                    stationary_destroyed = True
                    continue

                gamelib.debug_write(f"unit destroyed: {unit}")
            
            self.game_state.game_map.remove_unit(cell)
            self.game_state.game_map[cell] = remaining

        return stationary_destroyed, mobile_units_remain

    def append_game_map_list(self, l, e):

        t = self.game_state.game_map[l]
        conditional_append(t, e)
        self.game_state.game_map[l] = t

    def simulate(self):

        stationary_units_destroyed = True
        mobile_units_remain = True

        frame_count = 0

        while mobile_units_remain:

            gamelib.debug_write(f"simulating frame {frame_count}")

            if stationary_units_destroyed:
                self.pathfind_all()
                stationary_units_destroyed = False

            self.support_all()
            self.move_all()
            self.attack_all()

            stationary_units_destroyed, mobile_units_remain = self.remove_destroyed()
            gamelib.debug_write(f"{stationary_units_destroyed=}, {mobile_units_remain=}")
            frame_count += 1

            assert frame_count < 120







                



