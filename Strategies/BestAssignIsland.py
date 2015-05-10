# coding=utf-8
import math
from SharedData import *  # Just to ignore the warnings about globals
import SharedData
from Munkres import cross_assign


islands = None


def run():
    global islands
    globals().update(SharedData.__dict__)  # Ugly hack to import all SharedData vars for use

    # Goal: gain advantage as fast as possible
    if islands is None:
        islands = set(game.islands())
        while len(islands) > math.ceil(len(islands_locations) / float(2)):
            islands.discard(furthestIsland(islands))

    turn_islands = islands.copy()
    guardians = set()
    for island in turn_islands.copy():
        if island in game.my_islands():
            if island.team_capturing == game.ENEMY:
                guardians.add(island)
            turn_islands.discard(island)

    all_interest_islands = guardians.copy()
    all_interest_islands.update(turn_islands)
    assignments = cross_assign(game.my_pirates(), all_interest_islands)
    for assignment in assignments:
        chosen_pirate = assignment[1]
        chosen_island = assignment[0]
        movePirate(chosen_pirate, chosen_island,
                   importance=(3 if game.is_capturing(chosen_pirate) else 1),
                   kamikaze=(chosen_island in guardians))


def furthestIsland(isls):
    return max(isls, key=lambda isl: game.distance(isl, piratesCenter()))


def piratesCenter():
    pirates = game.my_pirates()
    return tuple((sum([pirate.location[0] for pirate in pirates]) / len(pirates),
                  sum([pirate.location[1] for pirate in pirates]) / len(pirates)))