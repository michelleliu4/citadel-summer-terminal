import gamelib

def targets(units):

    targets = []

    for unit in units:

        if unit.target not in targets and not is_stationary(unit.unit_type):

            targets.append(unit.targets)

    return targets

def conditional_append(l, e):

    if l == []:
        l = [e]
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

        self.pathfinder = ShortestPathFinder()

        # self.scores = 

    def pathfind_all(self):

        for cell in self.game_state.game_map:

            if self.game_state.game_map[cell] == []:

                continue
            
            tpd = {}

            for target in targets(self.game_state.game_map[cell]):

                tpd[target] = self.pathfinder.navigate_multiple_endpoints(cell, self.edges(target), self.game_state)
                print(f"pathfinding at {cell} for edge {target}")

            for unit in self.game_state.game_map[cell]:

                if is_stationary(unit.unit_type):

                    continue

                unit.path = [x for x in tpd[unit.target]] # do a deepcopy here to ensure that units don't reference the same 
                # path by accident (then popping becomes catastrophic)

    def move_all(self):

        for cell in self.game_state.game_map:

            if self.game_state.game_map[cell] == []:

                continue

            remaining = []

            for unit in self.game_state.game_map[cell]:

                if is_stationary(unit.unit_type):

                    remaining.append(unit)
                    continue

                elif unit.frames_until_move != 0:
                    
                    unit.frames_until_move -= 1
                    remaining.append(unit)
                    continue
                    
                if unit.path == []:
                    # unit self-destructs
                    # technically check if unit has moved some number of spaces here, but in the 
                    # current config it doesn't matter
                    remaining.append(unit)
                    self.handle_self_destruct(unit)                  
                    continue
                
                # i wish python had do {} while ();
                # anyways, get the next position to move to
                next_loc = unit.path[:1]
                unit.path = unit.path[1:]

                if next_loc == cell:

                    next_loc = unit.path[:1]
                    unit.path = unit.path[1:]

                if not self.game_state.game_map.in_arena_bounds(next_loc):

                    # player # unit.player_index has scored, might want more stuff here
                    print(f"player {abs(unit.player_index - 1)} scored on by {unit}")
                    # unit gets deleted since we don't move it to a new cell, and it isn't in remaining
                    continue
                
                unit.x, unit.y = next_loc
                unit.frames_until_move = self.speed #unit speed? check this
                conditional_append(self.game_state.game_map[next_loc], unit)

            self.game_state.game_map[cell] = remaining

    def attack_all(self):

        # now's when specific orders are important, although are they really?
        # the docs say that units attack even if their health is 0, but will not be targeted
        # if it's 0, so the order of attack doesn't really change anything right? I guess
        # it changes exactly which units are attacked by which other units, however the same amount of
        # damage is done to the enemy in either case, (although since negative health gets corrected to 0,
        # attacking a low health unit with a high damage unit wastes more, however this is not depended on the
        # order of spawning....)
        
        attacking_units = [] # define this

        for cell in self.game_state.game_map:

            for unit in self.game_state.game_map[cell]:

                if unit.unit_type not in attacking_units:
                    continue

                target = self.game_state.get_target(unit)

                if target == None:
                    # no units in range
                    continue
                
                self.handle_attack(unit, target)
        
        for cell in self.game_state.game_map:

            remaining = []

            for unit in self.game_state.game_map[cell]:

                if unit.health != 0:
                    remaining.append(unit)
                
            self.game_state.game_map[cell] = remaining

    def support_all(self):

        for cell in self.game_state.game_map:

            if self.game_state.game_map[cell] == [] or len(self.game_state.game_map[cell]) > 1:

                continue

            unit = self.game_state.game_map[cell][0]

            if unit.unit_type != SUPPORT: #check this here, probably cant us SUPPORT enum

                continue

            possible_locations = self.game_state.game_map.get_locations_in_range(cell, unit.shield_range)

            for location in locations:

                if self.game_state.game_map[location] == []:

                    continue

                for target in self.game_state.game_map[location]:

                    if target.player_index != unit.player_index or is_stationary(target) or unit in target.supported_by:

                        continue 

                    target.shield += unit.shieldPerUnit + calculate_shield_bonus(unit)
                    target.supported_by.append(unit)
                    print(f"unit {target} receives support from {unit}")

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

        print(f"unit {unit} self destructs")
        unit.health = 0


    def handle_attack(self, attacker, target):

        towers = []

        if target.unit_type in towers:
            damage_unit(target, attacker.damage_f)
            return
        
        damage_unit(target, attacker.damage_i)

        print(f"unit {attacker} damages {target}")

    def remove_destroyed(self):

        stationary_destroyed = False
        mobile_units_remain = False

        for cell in self.game_state.game_map:

            remaining = []

            for unit in self.game_state.game_map[cell]:

                if unit.health != 0:

                    remaining.append(unit)

                    if not is_stationary(unit):
                        mobile_units_remain = True

                    continue

                if is_stationary(unit):

                    stationary_destroyed = True
                    continue

                mobile_units_remain = True

                print(f"unit destroyed: {unit}")
            
            self.game_state.game_map[cell] = remaining

        return stationary_destroyed, mobile_units_remain


    def simulation_loop(self):

        self.pathfind_all()

        stationary_units_destroyed = False
        mobile_units_remain = True

        frame_count = 0

        while mobile_units_remain:

            print(f"simulating frame {frame_count}")

            if stationary_units_destroyed:
                self.pathfind_all()
                stationary_units_destroyed = False

            self.support_all()
            self.move_all()
            self.attack_all()

            stationary_units_destroyed, mobile_units_remain = self.remove_destroyed()









                



