# coding=utf-8
import math
import SharedData
from Strategies import *
from Logger import Logger
from GhostPirate import GhostPirate
from Movements import Movement
from EndGame import end_game

# Choose strategy here:
# -------------------------
STRATEGY = BestAssignIsland
# STRATEGY = TwoByTwo

# Config debug here:
# -------------------------
DEBUG = True
STARTING_ON_LINE = 0
ENDING_ON_LINE = None  # None for no limit

# ------------------------------------------------------- #
#                    DO NOT EDIT BELOW                    #
# ------------------------------------------------------- #
# TODO: replace all caching mechanisems with 'pylru'

# import cProfile
# def do_turn(_game):
#     SharedData.game = _game
#     profiler = cProfile.Profile()
#     profiler.runctx('main()', globals(), locals())
#     profiler.print_stats('cumtime')


# def main():
def do_turn(_game):
    # _game = SharedData.game  # Needed when profiling
    SharedData.game = _game
    start_time = _game.time_remaining()

    # First turn initializations
    if _game.get_turn() == 1:
        SharedData.logger = Logger(DEBUG, STARTING_ON_LINE, ENDING_ON_LINE)
        SharedData.ghostPirate = GhostPirate()
        SharedData.attack_radius = _game.get_attack_radius()
        SharedData.radius = int(math.sqrt(SharedData.attack_radius))
        SharedData.locateEnemySpawnsCenters()
        SharedData.islands_locations = set([isl.location for isl in _game.islands()])
        SharedData.last_pirates_locs = {pirate: SharedData.deque(maxlen=3) for pirate in _game.all_my_pirates()}

    # Reset turn data
    SharedData.logger.last_debug_time = start_time
    SharedData.pirates_dests.clear()
    SharedData.enemiesInRadius_cache.clear()
    SharedData.location_testing_cache.clear()
    # SharedData.nearestPassableLoc.clear()
    SharedData.enemy_danger_locs = {pirate: [(pirate.location[0] + r, pirate.location[1] + c)
                                    for r in xrange(-1, 2) for c in xrange(-1, 2)
                                    if r == 0 or c == 0] for pirate in _game.enemy_pirates()}

    SharedData.my_pirates_potential_locs = {pirate: [(pirate.location[0] + r, pirate.location[1] + c)
                                            for r in xrange(-1, 2) for c in xrange(-1, 2)
                                            if r == 0 or c == 0] for pirate in _game.my_pirates()}
    SharedData.enemy_capturing_pirates = set([pirate for pirate in _game.enemy_pirates() if _game.is_capturing(pirate)])

    # Run turn
    movements = Movement()
    SharedData.ghostPirate.update()
    if not end_game():
        STRATEGY.run()

    SharedData.last_enemy = set([pirate.id for pirate in filter(
        lambda enemy_pirate: _game.is_passable(enemy_pirate.location), _game.enemy_pirates())])
    SharedData.last_mine = set([pirate.id for pirate in filter(
        lambda my_pirate: not _game.is_capturing(my_pirate), _game.my_pirates())])

    movements.run()

    # Time stats
    turn_time = start_time - _game.time_remaining()
    SharedData.max_turn_time = max(SharedData.max_turn_time, turn_time)
    SharedData.logger.debug('------- TIMING: --------')
    SharedData.logger.debug('This turn took {} ms / 100 ms [Max: {} ms]'.format(turn_time, SharedData.max_turn_time))
    return
