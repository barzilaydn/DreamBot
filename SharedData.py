# coding=utf-8
# noinspection PyUnresolvedReferences
from collections import deque
from Movements import movePirate, createPath
# from pylru import lrudecorator

game = None
pirates_dests = {}
max_turn_time = 0
logger = None
ghostPirate = None
tankData = {}
attack_radius = 0
radius = 0
enemySpawns = {}
island_killers = True  # Enemies go off islands to escape danger. TODO: detect this
enemiesInRadius_cache = {}
location_testing_cache = {}
islands_locations = set()
last_enemy = []
last_mine = []
enemy_danger_locs = {}
my_pirates_potential_locs = {}
enemy_capturing_pirates = set()
last_pirates_locs = {}
last_pirates_dests = {}
joiners = {}


def piratesInRadius(loc, find_enemies=True, next_locs=None, exclude_pirate=None, debug=False):
    """
    Find how many enemies in location radius


    function can work both on our pirates(find enemies)
    :type loc: tuple
    :type next_locs: dict
    :rtype: set
    :return: list of enemy pirates in radius
    """
    global enemiesInRadius_cache

    use_current_locations = find_enemies or (next_locs is None)
    # Check if available in cache:
    if use_current_locations and ((loc, find_enemies) in enemiesInRadius_cache):
        if debug:
            logger.debug('Taking {} from cache for loc {} find_enemies {}'
                         .format(enemiesInRadius_cache[(loc, find_enemies)], loc, find_enemies))
        return enemiesInRadius_cache[(loc, find_enemies)].copy()

    strong_enemies = set()
    if find_enemies:
        test_locs = enemy_danger_locs.copy()
    else:
        if next_locs is None:
            next_locs = {}
        test_locs = my_pirates_potential_locs.copy()
        test_locs.update(next_locs)

    for pirate, locations in test_locs.iteritems():
        if debug:
            logger.debug('Testing enemy {} with locations {}'.format(pirate.id, locations))
        if pirate == exclude_pirate:
            if debug:
                logger.debug('Skipping excluded {} == {}'.format(exclude_pirate, pirate))
            continue

        # If he might be able to attack me:
        locations = locations if type(locations) is list else [locations]
        for location in locations:
            # Skip enemies on islands
            if not island_killers or not find_enemies:
                if not find_enemies or pirate in enemy_capturing_pirates:
                    if not use_current_locations:  # Using next_locs
                        if location in islands_locations:
                            if debug:
                                logger.debug('Skipping {} continue'.format(pirate.id))
                            continue
                    elif location in islands_locations:
                        if debug:
                            logger.debug('Skipping {} breaked'.format(pirate.id))
                        break

            if my_in_range(loc, location):
                strong_enemies.add(pirate)
                break
            else:
                if debug:
                    logger.debug('Pirate {} not in range with loc {}'.format(pirate.id, location))

    if use_current_locations:
        enemiesInRadius_cache[(loc, find_enemies)] = strong_enemies

    if debug:
        logger.debug('Found enemies {}'.format(strong_enemies))
    return strong_enemies


def pirateWillDie(pirate=None, location=None, owned_pirate=None, next_locs=None, kamikaze_target=False,
                  exclude_pirate=None):
    if pirate is not None:
        pirate_on_location = pirate
        if location is None:
            location = pirate.location
    elif location is not None:
        pirate_on_location = game.get_pirate_on(location)
    else:
        return True

    if owned_pirate is None:
        owned_pirate = (pirate_on_location.owner == game.ME) if pirate_on_location is not None else True

    enemies = piratesInRadius(location, find_enemies=owned_pirate, next_locs=next_locs, exclude_pirate=exclude_pirate)
    friends = piratesInRadius(location, find_enemies=(not owned_pirate), next_locs=next_locs,
                              exclude_pirate=exclude_pirate)
    friends.discard(pirate_on_location)  # Remove self from friends list

    if kamikaze_target and len(enemies) == 0:
        enemies.add(None)

    # logger.debug('Pirate {} (owned: {}) || Friends: {} | Enemies: {}'
    #              .format(pirate_on_location.id if pirate_on_location is not None else location,
    #                      owned_pirate,
    #                      [p.id for p in friends],
    #                      [p.id for p in enemies if p is not None]))

    return len(enemies) > len(friends)


# Location testing:
def testLoc(loc, goal=None, enemy_attack_radius=1, is_kamikaze=False, next_locs=None, bad_locations=None,
            no_pirates=False, exclude_locations=None):
    global location_testing_cache

    # Check locations first, these interrupt with cache because they might change mid-turn
    bad_locations = list(bad_locations) if bad_locations is not None else []
    exclude_locations = list(exclude_locations) if exclude_locations is not None else []

    if not no_pirates:
        if next_locs is not None:
            bad_locations += [next_loc for next_loc in next_locs.values()]
        else:
            bad_locations += [pirate.location for pirate in game.my_pirates()]

    if loc in bad_locations and loc not in exclude_locations:
        return False

    # Than check if available in cache
    key = (loc, enemy_attack_radius, is_kamikaze)
    if key in location_testing_cache:  # need to re-check if next_locs changed
        return bool(location_testing_cache[key])
    else:  # If not, calculate value and save in cache
        result = testLoc_no_cache(loc, goal, enemy_attack_radius, is_kamikaze)
        location_testing_cache[key] = result  # Cache result
        return bool(result)


def testLoc_no_cache(loc, goal=None, enemy_attack_radius=1, is_kamikaze=False):
    if not game.is_passable(loc):
        return False
    # elif loc == goal:
    #     return True
    # elif (goal is None or not my_in_range(loc, goal, custom_attack_radius=1))\
    #         and any(my_in_range(loc, ep.location, enemy_attack_radius)
    #                 for ep in game.enemy_pirates() if ep.location != goal):
    #     return False
    elif any(my_in_range(loc, ep.location, enemy_attack_radius) for ep in game.enemy_pirates()):
        return False
    elif is_kamikaze:
        # If is_kamikaze make sure not to step on islands
        on_island = loc in islands_locations
        if on_island:
            return False
    return True


def nearestPassableLoc(loc, caller_loc=None, next_locs=None, is_kamikaze=False, no_pirates=False, enemy_attack_radius=1,
                       exclude_locations=None, bad_locations=None, testFunc=None):
    if testFunc is None:
        testFunc = testLoc

    if testFunc(loc, is_kamikaze=is_kamikaze, next_locs=next_locs, bad_locations=bad_locations,
                no_pirates=no_pirates, exclude_locations=exclude_locations, enemy_attack_radius=enemy_attack_radius):
        return loc

    testXY = lambda Px, Py: testFunc((Py, Px), is_kamikaze=is_kamikaze, next_locs=next_locs,
                                     bad_locations=bad_locations, no_pirates=no_pirates,
                                     exclude_locations=exclude_locations, enemy_attack_radius=enemy_attack_radius)

    # Midpoint circle algorithm
    x0 = loc[1]
    y0 = loc[0]
    test_radius = 1
    while test_radius < max(game.get_rows(), game.get_cols()):
        good_locs = set()
        f = 1 - test_radius
        ddf_x = 1
        ddf_y = -2 * test_radius
        x = 0
        y = test_radius
        if testXY(x0, y0 + test_radius):
            good_locs.add((y0 + test_radius, x0))
        if testXY(x0, y0 - test_radius):
            good_locs.add((y0 - test_radius, x0))
        if testXY(x0 + test_radius, y0):
            good_locs.add((y0, x0 + test_radius))
        if testXY(x0 - test_radius, y0):
            good_locs.add((y0, x0 - test_radius))

        while x < y:
            if f >= 0:
                y -= 1
                ddf_y += 2
                f += ddf_y
            x += 1
            ddf_x += 2
            f += ddf_x

            xy = [x, y]
            for var in xrange(2):
                for xsign in xrange(-1, 2):
                    for ysign in xrange(-1, 2):
                        if ysign != 0 and xsign != 0:
                            if testXY(x0 + xsign * xy[var], y0 + ysign * xy[1 - var]):
                                good_locs.add((y0 + ysign * xy[1 - var], x0 + xsign * xy[var]))

            if len(good_locs) > 0:
                good_locs = list_min(good_locs, key=lambda good_loc: game.distance(loc, good_loc))
                if caller_loc is not None:
                    good_locs = list_min(good_locs, key=lambda good_loc: game.distance(caller_loc, good_loc))

                return good_locs[0]
        test_radius += 1
    return loc  # Did not find passable location


def pathNotPassable(loc_a, loc_b, testFunc=None, check_any=False):
    if testFunc is None:
        testFunc = lambda loc, no_pirates: game.is_passable(loc)

    current = loc_a
    i = 0
    while current != loc_b:
        # Get the path between two locations
        path = [pathi for pathi in game.get_directions(current, loc_b) if pathi != '-']
        if len(path) == 0:
            break

        current = game.destination(current, path[i % 2 * -1])  # Zig-Zag the route (will reduce false-negatives)
        # logger.debug('Traveling loc {} (loc_a: {} ; loc_b: {}'.format(current, loc_a, loc_b))
        if testFunc(current, no_pirates=True) or (not check_any and current == loc_b):  # Make sure we can't step there!
            if check_any or current == loc_b:
                return False
        elif not check_any:
            # logger.debug('Path from {} to {} canceled because of loc {}'.format(loc_a, loc_b, current))
            break
        i += 1
    return True


# Spawns finding:
def locateEnemySpawnsCenters():
    global enemySpawns

    spawns = []
    spawn_enemies = []
    for enemy in game.all_enemy_pirates():
        initial_loc = enemy.initial_loc
        for spawn_index, spawn in enumerate(spawns):
            if pathNotPassable(initial_loc, spawn, check_any=True):
                avr_r = (initial_loc[0] + spawn[0]) / 2
                avr_c = (initial_loc[1] + spawn[1]) / 2
                spawns[spawn_index] = (avr_r, avr_c)
                spawn_enemies[spawn_index].append(enemy)
                break
        else:  # No break
            spawns.append(initial_loc)  # New spawn
            spawn_enemies.append([enemy])

    logger.debug("Enemy spawns located: {}".format(spawns))

    for spawn, enemies in zip(spawns, spawn_enemies):
        enemySpawns[spawn] = enemies


# Range checking
def my_in_range(loc1, loc2, custom_attack_radius=None):
    # Check if two objects or locations are in attack range - faster than game.in_range()
    if type(loc1) is not tuple:
        if hasattr(loc1, 'location'):
            loc1 = loc1.location
        else:
            raise Exception('No \'location\' attribute for {}'.format(loc1))
            # return False
    if type(loc2) is not tuple:
        if hasattr(loc2, 'location'):
            loc2 = loc2.location
        else:
            raise Exception('No \'location\' attribute for {}'.format(loc2))
            # return False

    d_row, d_col = loc1[0] - loc2[0], loc1[1] - loc2[1]
    distance = d_row * d_row + d_col * d_col
    return 0 <= distance <= (custom_attack_radius if custom_attack_radius is not None else attack_radius)


# min / max with list return
def list_max(my_list, key=lambda x: x):
    my_list_copy = list(my_list)
    max_count = None
    temp_list = []
    for item in my_list_copy:
        value = key(item)
        if max_count is None or value > max_count:
            temp_list = [item]
            max_count = value
        elif value == max_count:
            temp_list.append(item)
    return temp_list


def list_min(my_list, key=lambda x: x):
    my_list_copy = list(my_list)
    min_count = None
    temp_list = []
    for item in my_list_copy:
        value = key(item)
        if min_count is None or value < min_count:
            temp_list = [item]
            min_count = value
        elif value == min_count:
            temp_list.append(item)
    return temp_list


# Hashable dict:
class hashabledict(dict):
    def __key(self):
        return frozenset(self.iteritems())

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()
