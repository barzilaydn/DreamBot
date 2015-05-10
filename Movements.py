# coding=utf-8
import heapq
from SharedData import *  # Just to ignore the warnings about globals
import SharedData


# DESCRIPTION:
# ==============
# > Handle all pirates movements while considering the consequences of each path.
#
# > This file knows to:
# > --- Create best paths.
# > --- Avoid obstacles and enemies.
# > --- Make pirates help each other in battles.
# > --- Reroute stuck pirate to another pirate with same task.
# > --- Regroup multiple stuck pirates with same task together.
# > --- Escape from enemies.
#
#  LOGIC FLOW:
# =============
# - > Add non-moving pirates.
# - > Remove cloaked pirate if got cloaked on this turn.
#
# - > Iterate multiple times while still having enough time for the turn:
# --- > Until all paths stay the same:
# ----- > Create shortest path to nearest possible location to destination
#          and pirate while avoiding un-passable locations and enemy pirates.
#
# --- > For pirates who die on next step:
# ----- > Try getting other pirates to help by changing their final destination
#          to current pirate destination if their movement importance allows it.
#           - break if successful (to re-create all paths with new destinations).
#
# ----- > If current pirate is a kamikaze pirate, check if an enemy from dangerous
#          enemies dictionary will die.
#           - continue if so (check next pirate)
#
# ----- > If another pirate with valid path headed to same final destination,
#          go to the other pirate going to the same destination.
#           - break if successful (to re-create all paths with new destinations).
#
# ----- > If at least one more pirate headed to same final destination and all
#          these pirates are stuck, regroup all of them at a new location.
#           - break if successful (to re-create all paths with new destinations).
#
# ----- > Escape enemy pirates or not move - chain escape if needed.
#           - break if successful (to re-create all paths with new destinations).
#
# - > Move pirates.
# _________________________________________________________________________________________________
#
#  MISC:
# =======
# ---- * Detect if enemies go off islands to kill you (assume not as default)
# _________________________________________________________________________________________________
#
#  PROPERTIES:
# =============
# -- > List of moving pirates sorted by movement importance (highest first)
# -- > Dictionary of pirate as key and movement importance as value (1 = Low ; 2 = Medium ; 3 = High).
# -- > Dictionary of pirate as key and final dest as value.
# -- > Dictionary of pirate as key and next location as value.
# -- > Dictionary of pirate as key and path as value.
# -- > Dictionary of pirate as key and a boolean of whether this pirate does kamikaze or not as value.
# -- > Dictionary of pirate as key and a boolean of whether this pirate is stuck or not as value.
# -- > Dictionary of pirate as key and list of enemies dangering him.
#
#  IMPORTANCE:
# =============
# -- > Low = Can be rerouted to help other pirates + $Medium
# -- > Medium = Can be joined with other pirates sharing a near final destination
# -- > High = Can not be rerouted to help other pirates or joined.

# TODO: update all functions to work with ghostPirate


def movePirate(pirate, dest, importance=1, kamikaze=False):
    importance = int(importance)
    importance = 1 if importance < 1 else 3 if importance > 3 else importance  # Constrain importance between 1-3
    if pirate.id == ghostPirate.cloaked_Pirate_id and ghostPirate.cloaked_on_this_turn:
        logger.debug('Can\'t move pirate {}, cloaked on this turn.'.format(pirate.id))
    elif type(dest) is tuple:
        pirates_dests[pirate] = (dest, importance, bool(kamikaze))
    elif hasattr(dest, 'location'):
        pirates_dests[pirate] = (tuple(dest.location), importance, bool(kamikaze))
    else:
        raise Exception('Dest {} does not describe a location'.format(dest))
    return


class Movement(object):
    pirates = []
    movement_importance = {}
    final_dests = {}
    next_locs = {}
    paths = {}
    kamikaze = {}
    stucks = {}
    helpers = set()

    # Turn-to-turn saved data:
    joiners = {}

    def __init__(self):
        globals().update(SharedData.__dict__)  # Ugly hack to import all SharedData vars for use
        # noinspection PyGlobalUndefined
        global enemiesInRadius_cache, pirates_dests

        # Reset all object properties
        self.pirates[:] = []  # Empty and clear references
        self.helpers.clear()
        self.movement_importance.clear()
        self.final_dests.clear()
        self.next_locs.clear()
        self.paths.clear()
        self.kamikaze.clear()
        self.stucks.clear()
        self.paths_created = False

        # Restore last turn data
        self.joiners = SharedData.joiners

    def run(self):
        logger.debug('------ MOVEMENTS: ------')

        self.unpack()  # Prepare class properties for processing.

        changed = True
        while changed:
            changed = False
            self.createPaths()

            for pirate, next_loc in self.next_locs.iteritems():
                stuck_on_place = not self.stucks[pirate] and self.final_dests[pirate] != next_loc == pirate.location
                if pirateWillDie(pirate, next_loc, True, self.next_locs) or stuck_on_place:
                    changed = True
                    if self.stucks[pirate]:  # Already stuck
                        pass
                    elif (not stuck_on_place or len(piratesInRadius(next_loc)) > 0) and \
                            self.helpPirate(pirate, next_loc):  # Try helping pirate
                        logger.debug('Pirate {} got help.'.format(pirate.id))
                        self.stucks[pirate] = True
                        self.pirates.remove(pirate)
                        self.pirates.insert(0, pirate)
                        break
                    else:
                        # Verify if will be able to join
                        possible_followed = self.findPirateToJoin(pirate) \
                            if self.movement_importance[pirate] <= 2 else None

                        if (not stuck_on_place or possible_followed is None)\
                                and self.kamikaze[pirate] and self.checkKamikaze(pirate):
                            logger.debug('Pirate {} is kamikaze and enemy will die.'
                                         .format(pirate.id))
                            changed = False
                            self.stucks[pirate] = False
                            continue  # It's ok not to move
                        elif self.joinPirate(pirate, possible_followed):
                            logger.debug('Pirate {} is joining other pirate with a shared destination.'
                                         .format(pirate.id))
                            self.stucks[pirate] = True
                            self.pirates.remove(pirate)
                            self.pirates.insert(0, pirate)
                            break

                    if self.escapeEnemies(pirate):
                        logger.debug('Pirate {} is escaping.'
                                     .format(pirate.id))
                        self.stucks[pirate] = True
                        self.pirates.remove(pirate)
                        self.pirates.insert(0, pirate)
                        break

                    self.stucks[pirate] = True
                    changed = False
                    logger.debug('Pirate {} has nothing to do, RIP.'.format(pirate.id))

        # Actually move the pirates
        logger.debug('------- SAILING: -------')
        for pirate, path in self.paths.iteritems():
            last_dest = last_pirates_dests.get(pirate, None)
            if last_dest is not None and not my_in_range(self.final_dests[pirate], last_dest):
                last_pirates_locs[pirate].clear()
            last_pirates_locs[pirate].append(pirate.location)
            last_pirates_dests[pirate] = self.final_dests[pirate]
            logger.debug('Pirate {} moving to the \'{}\''.format(pirate.id, path))
            game.set_sail(pirate, path)

        # Export data for next turn
        SharedData.joiners = self.joiners

    def unpack(self):
        for pirate, data in pirates_dests.iteritems():
            dest, importance, kamikaze = data
            self.pirates.append(pirate)
            self.movement_importance[pirate] = importance
            self.kamikaze[pirate] = kamikaze
            self.stucks[pirate] = False
            self.final_dests[pirate] = dest

        # Add non-moving pirates:
        for pirate in game.my_pirates():
            if pirate not in self.pirates:
                # Don't add cloaked pirate if he just got cloaked (can't also move)
                if not (pirate.id == ghostPirate.cloaked_Pirate_id and ghostPirate.cloaked_on_this_turn):
                    self.pirates.append(pirate)
                    self.movement_importance[pirate] = 3 if game.is_capturing(pirate) else 1
                    self.final_dests[pirate] = pirate.location
                    self.kamikaze[pirate] = False
                    self.stucks[pirate] = False

        # Restore joiners and regroupers:
        self.restoreJoiners()

        # Sort by importance and than ID (Highest first):
        self.pirates.sort(key=lambda _pirate: (self.movement_importance[_pirate], _pirate.id), reverse=True)

        for pirate in self.pirates:
            logger.debug('P: {} | T: {} | I: {} | K: {}'.format(pirate.id,
                                                                self.final_dests[pirate],
                                                                self.movement_importance[pirate],
                                                                self.kamikaze[pirate]))

    def restoreJoiners(self):
        for data_key, followed_pirate_id in self.joiners.copy().iteritems():
            pirate_id, old_dest = data_key
            pirate = game.get_my_pirate(pirate_id)
            followed_pirate = game.get_my_pirate(followed_pirate_id)

            if pirate in self.pirates and followed_pirate in self.pirates:
                if not my_in_range(pirate, followed_pirate, 2):
                    if my_in_range(self.final_dests[pirate], old_dest, 50):  # If kept near final destination
                        # If the pirate getting followed also kept near final destination
                        if my_in_range(self.final_dests[followed_pirate], self.final_dests[pirate], 50):
                            # Find where to join
                            directions = game.get_directions(followed_pirate, self.final_dests[followed_pirate])
                            directions.sort(key=lambda _dir: game.distance(game.destination(followed_pirate, _dir),
                                                                           pirate))
                            dest = game.destination(followed_pirate, directions[0])
                            if dest == pirate.location or not testLoc(dest, no_pirates=True):
                                dest = game.destination(followed_pirate, directions[-1])
                            # Join him
                            self.final_dests[pirate] = dest
                            logger.debug('Pirate {} is still joining pirate {}'.format(pirate.id, followed_pirate.id))
                            continue

            # Did not continue, need to break join
            logger.debug('Pirate {} is no longer joining pirate {}'.format(pirate.id, followed_pirate.id))
            self.joiners.pop(data_key)

    def createPaths(self):
        already_tried_paths_combinations = set()
        changed = True
        while changed:
            changed = False
            for x in xrange(1 if self.paths_created else 2):
                for pirate in self.pirates:
                    logger.debug('Creating path for pirate {}'.format(pirate.id))
                    testFunc = lambda loc, goal=None, bad_locations=None, no_pirates=False, **_: self.enemyTest(
                        loc, bad_locations, no_pirates, pirate)

                    path = createPath(pirate.location, self.final_dests[pirate], is_kamikaze=self.kamikaze[pirate],
                                      pirate=pirate, next_locs=self.next_locs, testFunc=testFunc)

                    old_path = self.paths.get(pirate, path)

                    self.next_locs[pirate] = game.destination(pirate, path)
                    self.paths[pirate] = path
                    if not hashabledict(self.paths) in already_tried_paths_combinations:
                        already_tried_paths_combinations.add(hashabledict(self.paths))
                        if old_path != path:
                            logger.debug('Pirate {} path changed from {} to {}'.format(pirate.id, old_path, path))
                            if x == 1:
                                changed = True
                                break
                else:  # no break
                    continue
                break

            self.paths_created = True
            # if game.time_remaining() < 70:  # TODO: either optimize or find a better breaking point
            #     break

    def enemyTest(self, loc, bad_locations=None, no_pirates=False, pirate=None):
        # logger.debug('Testing {}'.format(loc))

        # Make sure pirate is not stuck (zig-zags between 2 locations)
        if pirate is not None:
            if not self.stucks[pirate]:
                last_locs = last_pirates_locs[pirate]
                for last_loc in last_locs:
                    if loc == last_loc != pirate.location:
                        # logger.debug('Pirate loc canceled - stuck')
                        return False

        next_locs_without_me = self.next_locs.copy()
        next_locs_without_me.pop(pirate, None)
        if not testLoc(loc,
                       goal=self.final_dests[pirate],
                       is_kamikaze=self.kamikaze[pirate],
                       next_locs=next_locs_without_me,
                       bad_locations=bad_locations,
                       no_pirates=no_pirates):
            # logger.debug('Testing {} - not passable.'.format(loc))
            return False

        # Test for enemies
        if not pirateWillDie(pirate, loc, owned_pirate=True, next_locs=self.next_locs):
            # logger.debug('Testing {} - will not die.'.format(loc))
            return True

        if self.checkKamikaze(pirate, loc):
            return True

        # logger.debug('Testing {} - will die.'.format(loc))
        return False

    def helpPirate(self, my_pirate, my_next_loc=None):
        my_next_loc = my_next_loc if my_next_loc is not None else my_pirate.location
        enemies_len = len(piratesInRadius(my_next_loc))
        if enemies_len == 0:
            return True

        my_helpers = set()
        for pirate, potential_locs in my_pirates_potential_locs.copy().iteritems():
            if len(my_helpers) >= enemies_len:
                break  # Don't force more than needed

            if pirate != my_pirate:
                if self.movement_importance[pirate] == 1:  # Low movement importance
                    if pirate in self.helpers:
                        potential_locs = [self.next_locs[pirate]]  # Don't re-force pirates already forced to help

                    if any([my_in_range(my_next_loc, potential_loc) and potential_loc not in islands_locations
                            for potential_loc in potential_locs]):
                        my_helpers.add(pirate)  # Can help

        if len(my_helpers) >= enemies_len:
            self.helpers.update(my_helpers)
            for helper in my_helpers:
                if not my_in_range(my_next_loc, self.next_locs[helper]) or self.next_locs[helper] in islands_locations:
                    testFunc = lambda loc, goal=None, bad_locations=None, no_pirates=False, **_: self.enemyTest(
                        loc, bad_locations, no_pirates, my_pirate)
                    self.final_dests[helper] = nearestPassableLoc(my_pirate.location,
                                                                  my_pirate.location,
                                                                  self.next_locs,
                                                                  self.kamikaze[helper],
                                                                  bad_locations=islands_locations,
                                                                  testFunc=testFunc)

            logger.debug('Pirate {} (going \'{}\') is getting help from pirates {}'
                         .format(my_pirate.id, self.paths[my_pirate], [p.id for p in my_helpers]))
            return True
        return False

    def checkKamikaze(self, pirate, loc=None):
        if self.kamikaze[pirate]:
            loc = pirate.location if loc is None else loc
            enemy_list = piratesInRadius(loc)
            if len(enemy_list) == 0:
                return True

            # logger.debug('Testing loc {} for Pirate {} enemies: {}'.format(loc, pirate.id, [p.id for p in enemy_list]))
            for enemy in enemy_list:
                next_locs_with_me = self.next_locs.copy()
                if loc is not None or pirate not in next_locs_with_me:
                    next_locs_with_me[pirate] = [(loc[0] + r, loc[1] + c)
                                                 for r in xrange(-1, 2)
                                                 for c in xrange(-1, 2)
                                                 if r == 0 or c == 0]

                # Build enemy possible interesting directions:
                directions_to_me = set(game.get_directions(enemy, loc))
                directions_to_me.add('-')
                directions_escaping_me = set([('n', 'w', 's', 'e')[('n', 'w', 's', 'e').index(direction) - 2]
                                             for direction in directions_to_me if direction != '-'])

                for direction in directions_to_me.union(directions_escaping_me):
                    # Verify that pirate was the one actually killing the enemy
                    enemy_dest = game.destination(enemy, direction)
                    if not game.is_passable(enemy_dest):
                        continue

                    enemy_dies_with_me = pirateWillDie(enemy,
                                                       location=enemy_dest,
                                                       owned_pirate=False,
                                                       next_locs=next_locs_with_me,
                                                       kamikaze_target=True)

                    enemy_dies_without_me = pirateWillDie(enemy,
                                                          location=enemy_dest,
                                                          owned_pirate=False,
                                                          next_locs=self.next_locs,
                                                          exclude_pirate=pirate)

                    if not enemy_dies_with_me or enemy_dies_without_me:
                        # Check if would still die
                        enemy_danger_locs_backup = SharedData.enemy_danger_locs.copy()
                        SharedData.enemy_danger_locs[enemy] = [enemy_dest]
                        will_die = pirateWillDie(pirate, loc, True, self.next_locs)
                        SharedData.enemy_danger_locs = enemy_danger_locs_backup
                        if will_die:
                            return False

                # logger.debug('Testing {} - enemy {} will die.'.format(loc, enemy.id))
                return True
        return False

    def joinPirate(self, my_pirate, followed):
        if followed is not None:
            # Add joiner
            data_key = (my_pirate.id, self.final_dests[my_pirate])
            self.joiners[data_key] = followed.id  # Add to joiners
            self.final_dests[my_pirate] = self.next_locs[followed]
            logger.debug('Pirate {} is now following pirate {}'.format(my_pirate.id, followed.id))
            return True
        return False

    def findPirateToJoin(self, my_pirate):
        # If not already joined
        for data_key in self.joiners:
            pirate_id, old_dest = data_key
            if pirate_id == my_pirate.id:
                return None

        for pirate, final_dest in self.final_dests.iteritems():
            if pirate != my_pirate:
                if not self.stucks[pirate]:  # Other pirate has a valid path
                    if my_in_range(self.final_dests[my_pirate], final_dest, 50):  # Both going to a near destination
                        # Check if not following a pirate following my_pirate
                        # noinspection PyArgumentEqualDefault
                        # chain_join_key = next((data_key
                        #                        for data_key, following_id
                        #                        in self.joiners.iteritems()
                        #                        if following_id == my_pirate.id), None)
                        # if chain_join_key is not None:
                        #     pirate_id, old_dest = chain_join_key
                        #     if pirate_id == pirate.id:
                        #         continue

                        return pirate
        return None

    def escapeEnemies(self, my_pirate):
        logger.debug('Pirate {} trying to escape.'.format(my_pirate.id))
        # Try creating a path to nearest passable location
        testFunc = lambda loc, goal=None, bad_locations=None, no_pirates=False, **_: self.enemyTest(
            loc, bad_locations, no_pirates, my_pirate)
        # TODO: testFunc shows location good for location where enemy dies (probably kamikaze problem)
        safe_loc = nearestPassableLoc(my_pirate.location, my_pirate.location, self.next_locs, self.kamikaze[my_pirate],
                                      testFunc=testFunc)
        path = createPath(my_pirate.location, safe_loc, is_kamikaze=self.kamikaze[my_pirate], pirate=my_pirate,
                          next_locs=self.next_locs, testFunc=testFunc)
        safe_dest = game.destination(my_pirate, path)

        # TODO Chain escape.

        if self.helpPirate(my_pirate, safe_dest):
            self.final_dests[my_pirate] = safe_dest
            logger.debug('Pirate {} escaping to the \'{}\' to {}'.format(my_pirate.id, path, safe_dest))
            return True
        else:
            logger.debug('Pirate {} failed to escape to {}.'.format(my_pirate.id, safe_dest))
            return False


def createPath(src, dest, alternating=True, is_kamikaze=False, pirate=None, next_locs=None, enemy_attack_radius=1,
               exclude_locs=None, testFunc=None):
    if testFunc is None:
        testFunc = testLoc

    if src == dest:
        return '-'

    exclude_locs = exclude_locs if exclude_locs is not None else []
    if pirate is not None:
        if next_locs is not None and pirate in next_locs:
            exclude_locs.append(next_locs[pirate])
        else:
            exclude_locs.append(pirate if type(pirate) is tuple else pirate.location)

    # logger.debug('Source before: {} | Dest before: {}'.format(src, dest))
    next_locs = hashabledict(next_locs) if next_locs is not None else None
    dest = nearestPassableLoc(dest, pirate, next_locs, is_kamikaze, exclude_locations=exclude_locs,
                              testFunc=testFunc)
    # logger.debug('Source after: {} | Dest after: {}'.format(src, dest))

    if src == dest:
        return '-'

    smart_dest = obstaclePass(src, dest, is_kamikaze, next_locs, enemy_attack_radius=enemy_attack_radius,
                              exclude_locs=exclude_locs, testFunc=testFunc)
    paths = game.get_directions(src, smart_dest) if smart_dest is not None else []
    paths = sorted([p for p in paths if p != '-'], key=lambda _p: ['n', 'e', 's', 'w'].index(_p))

    if len(paths) == 0:
        logger.debug('No path found from {} to {}'.format(src, dest))
        return '-'

    path = paths[alternating * (-1 * (game.get_turn() % 2))]
    if not testFunc(game.destination(src, path), goal=dest):
        path = paths[paths.index(path) - 1]

    return path


def obstaclePass(src, dest, is_kamikaze=False, next_locs=None, enemy_attack_radius=1,
                 exclude_locs=None, testFunc=None, max_steps=6):
    """
    :param max_steps: Max nodes for bfs to transverse. Set to 0 to unlimit.
    :type next_locs: dict
    :rtype : location of the next step that should be taken towards dest. None if no path found
    """
    if testFunc is None:
        testFunc = testLoc
    testPoint = lambda point, no_pirates=False: testFunc(point, goal=dest, enemy_attack_radius=enemy_attack_radius,
                                                         is_kamikaze=is_kamikaze, next_locs=next_locs,
                                                         exclude_locations=exclude_locs, no_pirates=no_pirates)

    # See if regular path is safe:
    # if not pathNotPassable(dest, src, testFunc=testPoint):
    #     logger.debug('Pirate {} using regular path.'.format(src))
    #     return dest

    # If not, pass obstacle using Best First Search
    # logger.debug('Pirate on location {} using BFS.'.format(src))

    goal = dest
    start = src

    # Bi-directional greedy Best-First Search Algorithm:
    # ----------------------------------
    # heuristic(loc) = Manhattan distance on a square grid from loc to target

    frontier = PriorityQueue()
    frontier.put(start, 0)
    came_from = {start: None}

    goal_frontier = PriorityQueue()
    goal_frontier.put(goal, 0)
    goal_came_from = {goal: None}

    # TODO: find best heuristic function.
    heuristic = lambda loc, target: (abs(loc[0] - target[0]) + abs(loc[1] - target[1])) *\
                                    ((1 + len(piratesInRadius(loc, next_locs=next_locs)))
                                     / (float(1 + len(game.enemy_pirates()))))

    current = None
    goal_current = None
    while not frontier.empty() or not goal_frontier.empty():
        old_current = current
        current = frontier.get() if not frontier.empty() else current
        old_goal_current = goal_current
        goal_current = goal_frontier.get() if not goal_frontier.empty() else goal_current

        # logger.debug('obstaclePass checking {} | {} for search from {} to {}'
        #              .format(current, goal_current, start, goal))

        found_way = current in goal_came_from or goal_current in came_from or current == goal_current
        if found_way or (max_steps != 0 and len(came_from) + len(goal_came_from) >= max_steps + 2):
            if goal_current in came_from:
                current = goal_current
            start_current = current

            if not found_way:  # Limited by steps
                current = goal_current

            # Reconstruct path
            path = []
            while current != goal:
                path.append(current)
                current = goal_came_from[current]
            path.append(goal)
            path.reverse()
            current = start_current
            while current != start:
                if current not in path:
                    path.append(current)
                current = came_from[current]
            path.reverse()

            # Smooth path
            # logger.debug('Smoothing path from {} to {}'.format(start, goal))
            if len(path) > 1:
                if not pathNotPassable(src, path[1], testFunc=testPoint):
                    del path[0]

            i = 0
            for j in xrange(len(path) - 2):
                if len(path) > 2:
                    # Line-of-sight available
                    if not pathNotPassable(path[i+j], path[i+j+2], testFunc=testPoint):
                        del path[i+j+1]
                        i -= 1  # Align indexes
                elif len(path) == 2 and not pathNotPassable(path[0], path[1], testFunc=testPoint):
                    del path[1]

            # logger.debug('Found path {}'.format(path))
            return path[0]

        # Transverse to next nodes
        if current != old_current:
            for next_loc in [(current[0] + r, current[1] + c) for r in xrange(-1, 2) for c in xrange(-1, 2)
                             if ((c == 0) != (r == 0))]:
                if testPoint(next_loc):
                    if next_loc not in came_from:
                        frontier.put(next_loc, heuristic(next_loc, goal))
                        came_from[next_loc] = current

        if goal_current != old_goal_current:
            for next_loc in [(goal_current[0] + r, goal_current[1] + c) for r in xrange(-1, 2) for c in
                             xrange(-1, 2) if ((c == 0) != (r == 0))]:
                if testPoint(next_loc):
                    if next_loc not in goal_came_from:
                        goal_frontier.put(next_loc, heuristic(next_loc, start))
                        goal_came_from[next_loc] = goal_current

    logger.debug('Pirate on location {} could not find path to goal {}'.format(src, dest))
    return None


class PriorityQueue(object):
    def __init__(self):
        self.elements = []

    def empty(self):
        return len(self.elements) == 0

    def put(self, item, priority):
        heapq.heappush(self.elements, (priority, item))

    def get(self):
        return heapq.heappop(self.elements)[1]
