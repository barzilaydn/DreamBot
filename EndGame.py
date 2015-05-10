# coding=utf-8
import math
from SharedData import *  # Just to ignore the warnings about globals
import SharedData
from Munkres import cross_assign
from Tank import Tank

kamikaze_assignments = {}
kamikaze_assignments_turn = 0


def end_game():
    global kamikaze_assignments, kamikaze_assignments_turn
    globals().update(SharedData.__dict__)  # Ugly hack to import all SharedData vars for use

    if not will_win():
        logger.debug('Still not end-game.')
        return False
    else:
        logger.debug('End-game reached :).')

    enemies = set(filter(lambda enemy_pirate: game.is_passable(enemy_pirate.location),
                         game.enemy_pirates()))
    pirates = set(filter(lambda my_pirate: not game.is_capturing(my_pirate), game.my_pirates()))

    logger.debug([mine.id for mine in pirates])
    logger.debug(list(last_mine))

    logger.debug('------ KAMIKAZE: -------')
    if kamikaze_assignments_turn == 0 \
            or game.get_turn() != kamikaze_assignments_turn + 1 \
            or last_enemy != set([enemy.id for enemy in enemies]) \
            or last_mine != set([mine.id for mine in pirates]):
        logger.debug('Re-assigning kamikaze')
        # Split pirates to blobs (group of nearby pirates):
        enemy_blobs = []
        for pirate in enemies:
            for blob_index, blob in enumerate(enemy_blobs):
                for pirate_in_blob in blob:
                    if my_in_range(pirate_in_blob, pirate, custom_attack_radius=((radius - 1) ** 2 + 1)):
                        enemy_blobs[blob_index].append(pirate)
                        break
                else:
                    continue
                break
            else:
                enemy_blobs.append([pirate])

        # Get locations of pirates in blobs and decide how many pirates to send to each blob
        blob_targets = []
        for blob_i, enemy_blob in enumerate(enemy_blobs):
            blob_targets += enemy_blob
            if len(enemy_blob) > 1:
                blob_targets.append(enemy_blob[0])

            # TODO: see if helpful
            if enemy_blob != enemy_blobs[-1] \
                    and len(blob_targets) + (len(enemy_blobs[blob_i+1])
                                             + int(len(enemy_blobs[blob_i+1]) > 1)) > len(pirates):
                for x in xrange(len(pirates) - len(blob_targets)):
                    blob_targets.append(enemy_blob[0])
                break

        kamikaze_assignments.clear()
        assignments = cross_assign(pirates, blob_targets, injective=True, score_Func=scoreKamikaze)
        for assignment in assignments:
            chosen_pirate = assignment[1]
            chosen_enemy = assignment[0]
            kamikaze_assignments[chosen_pirate.id] = chosen_enemy.id

    # TODO: make one ship a ghost and reveal it when it is in enemy radius and enemy will die.

    kamikaze_assignments_turn += 1
    tank_pirates = list(pirates)
    for chosen_pirate, chosen_enemy in kamikaze_assignments.iteritems():
        pirate = game.get_my_pirate(chosen_pirate)
        enemy = game.get_enemy_pirate(chosen_enemy)
        tank_pirates.remove(pirate)
        logger.debug('Pirate {} kamikaze on enemy {}'.format(chosen_pirate, chosen_enemy))
        movePirate(pirate, enemy, kamikaze=True)

    logger.debug('----- SPAWN TANK: ------')
    # TODO: adjust for multiple spawns
    if len(tank_pirates) > 0:
        logger.debug('Spawn tank is {}'.format([p.id for p in tank_pirates]))
        target_spawn = enemySpawns[0]
        # target_spawn = (target_spawn[0], target_spawn[1] - int(math.ceil(len(tank_pirates) / 2)))
        with Tank(tank_pirates, 'spawnTank', _starting_location=target_spawn) as spawnTank:
            spawnTank.moveTank(target_spawn)
    return True


def scoreKamikaze(enemy, mine):
    our_distance = game.distance(enemy, mine)
    islands = [isl for isl in game.islands() if isl not in game.enemy_islands()]
    nearest_island = min(islands, key=lambda island: game.distance(island, enemy))
    island_value = nearest_island.value
    enemy_to_nearest_island = game.distance(nearest_island, enemy)
    mine_to_nearest_island = game.distance(nearest_island, mine)
    can_make_it = mine_to_nearest_island < enemy_to_nearest_island + \
        (nearest_island.capture_turns - nearest_island.turns_being_captured)

    if not can_make_it:
        return game.get_cols() * game.get_rows() * our_distance
    else:
        return mine_to_nearest_island / island_value


def will_win():
    """ check who will win if the game will stay the same, and how many turns it will take.
     who_wins[0] - who will win
     0 - we,1 - enemy,2 - tie
     who_wins[1] - how many turns until game over """
    # TODO: consider islands being captured (i.e enemy about to capture our only island and we have less score)
    last_points = game.get_last_turn_points()  # [0] = ours [1] = enemy

    if last_points[0] != 0 and last_points[1] != 0:
        my_turns_to_1000 = int(math.ceil((1000 - game.get_my_score()) / float(last_points[0])))
        enemy_turns_to_1000 = int(math.ceil((1000 - game.get_enemy_score()) / float(last_points[1])))
        logger.debug('Predicted score: {} M vs {} E'
                     .format(game.get_my_score() + last_points[0] * min(enemy_turns_to_1000, my_turns_to_1000),
                             game.get_enemy_score() + last_points[1] * min(enemy_turns_to_1000, my_turns_to_1000)))
        return my_turns_to_1000 < enemy_turns_to_1000
    else:
        turns_left = game.get_max_turns() - game.get_turn()
        my_end_score = game.get_my_score() + last_points[0] * turns_left
        enemy_end_score = game.get_enemy_score() + last_points[1] * turns_left
        logger.debug('Predicted score: {} M vs {} E'.format(my_end_score, enemy_end_score))
        return my_end_score > enemy_end_score