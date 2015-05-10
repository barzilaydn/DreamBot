# coding=utf-8
import sys
from SharedData import *  # Just to ignore the warnings about globals
import SharedData


class Tank(object):
    def __init__(self, _pirates, _identifier, _starting_location=None):
        globals().update(SharedData.__dict__)  # Ugly hack to import all SharedData vars for use
        self._pirates = _pirates
        self._identifier = _identifier
        self._starting_location = _starting_location
        pass

    def __enter__(self):
        # noinspection PyGlobalUndefined
        class TankInstance(object):
            """
                    Creates a Tank and manage it.

                    :var baseLoc: the base location of the Tank
                    :var pirates: list of pirates (objects) (updated each turn to
                    :var game: the game
                    :var tankFormations: locations to form tank
                    """
            baseLoc = (0, 0)
            pirates = []
            game = None
            tankFormations = []
            last_path = 'n'
            bad_locations = []

            def __init__(self, pirates, identifier=None, startingLocation=None):
                """
                Creates Tank instance
                :param pirates: list of the pirates of the tank
                :param identifier: tankInstance identifier
                :param startingLocation: tuple - base location of the Tank (Location - LocationObject)
                       after first time - list. used to resume data: contains Tank's base location
                """
                self.pirates = pirates
                if identifier is None:
                    identifier = tuple(pirates)
                self.identifier = identifier
                tank_data = tankData.get(identifier, None)

                if tank_data is not None:
                    self.resumeFromData(tank_data)
                else:
                    self.calculateFormation()
                    if startingLocation is None:
                        startingLocation = self.findBaseLoc()
                    self.baseLoc = nearestPassableLoc(startingLocation, caller_loc=self.findBaseLoc(),
                                                      exclude_locations=[p.location for p in pirates])

                # logger.debug('Base is {}'.format(self.baseLoc))

            def findBaseLoc(self):
                """
                used when no startingLocation is passed to __init__ (default value is None)
                :rtype:  LocationObject
                :return: location for tank base - average of pirates location
                """

                # Centre of islands, more weight to valued islands:
                # islands = []
                # center = []
                #
                # for island in game.islands():
                # for v in xrange(island.value):
                # islands.append(island)
                #
                # center.append(sum([island.location[0] for island in islands]) / len(islands))
                # center.append(sum([island.location[1] for island in islands]) / len(islands))
                #
                # return tuple(center)

                # Centre of pirates
                return tuple((sum([pirate.location[0] for pirate in self.pirates]) / len(self.pirates),
                              sum([pirate.location[1] for pirate in self.pirates]) / len(self.pirates)))

            def moveTank(self, dest):
                """
                Move the Tank, only if Tank already in form, if not - form tank

                uses 'movePirate' to move Tank
                :param dest: destination to move the Tank to.
                """
                old_dest = dest
                dest = nearestPassableLoc(dest, caller_loc=self.findBaseLoc(),
                                          exclude_locations=[p.location for p in self.pirates])
                path = createPath(self.baseLoc, dest, alternating=False, pirate=self.findBaseLoc(),
                                  exclude_locs=[p.location for p in self.pirates])

                if path != '-':
                    self.last_path = path

                form_path = path
                if path == '-':
                    form_path = game.get_directions(self.baseLoc, old_dest)[0]
                    if form_path == '-':
                        form_path = self.last_path

                # logger.debug("Tank going to target {} with path '{}'".format(dest, path))

                if self.formTank(form_path):
                    logger.debug("We've got a tank! prepare to die..")
                    if path is not None and path != '-':
                        for pirate in self.pirates:
                            dest = game.destination(pirate, path)
                            movePirate(pirate, dest)

                        # Apply new base
                        if self.baseLoc != old_dest:
                            self.baseLoc = game.destination(self.baseLoc, path)
                    else:
                        logger.debug("Stopped tank from moving.")

            def changeReference(self, locations):
                # # Fix out-of map tank
                # max_rows = game.get_rows()
                # max_cols = game.get_cols()
                # if max_cols - self.baseLoc[1] < radius:
                #     self.baseLoc = (self.baseLoc[0], max_cols - radius - 1)
                # elif self.baseLoc[1] < radius:
                #     self.baseLoc = (self.baseLoc[0], radius)
                #
                # if max_rows - self.baseLoc[0] < radius:
                #     self.baseLoc = (max_rows - radius - 1, self.baseLoc[1])
                # elif self.baseLoc[0] < radius:
                #     self.baseLoc = (radius, self.baseLoc[1])

                # Adjust location list to be around a new base location
                newList = []
                for loc in locations:
                    newList.append((loc[0] + self.baseLoc[0], loc[1] + self.baseLoc[1]))

                for loc in newList:
                    nearest_new_loc = nearestPassableLoc(loc, caller_loc=self.findBaseLoc(),
                                                         exclude_locations=newList+[p.location for p in self.pirates])
                    diff_r = nearest_new_loc[0] - loc[0]
                    diff_c = nearest_new_loc[1] - loc[1]

                    if diff_r != 0 or diff_c != 0:
                        logger.debug('Tank location {} not reachable, changing baseLoc'.format(loc))
                        if self.baseLoc not in self.bad_locations:
                            self.bad_locations.append(loc)
                            self.bad_locations.append(self.baseLoc)

                        oldBase = self.baseLoc
                        tempLoc = (self.baseLoc[0] + diff_r, self.baseLoc[1] + diff_c)
                        if tempLoc in self.bad_locations:
                            self.baseLoc = nearestPassableLoc(tempLoc, caller_loc=self.findBaseLoc(),
                                                              exclude_locations=
                                                              [p.location for p in self.pirates],
                                                              bad_locations=self.bad_locations)
                        else:
                            self.baseLoc = tempLoc

                        logger.debug('New base-loc: {}'.format(self.baseLoc))
                        newList = self.changeReference(locations)
                        self.baseLoc = oldBase
                return newList

            def formTank(self, path='-', base_loc=None):
                if base_loc is not None:
                    self.baseLoc = nearestPassableLoc(base_loc, caller_loc=self.findBaseLoc(),
                                                      exclude_locations=[p.location for p in self.pirates])

                if len(self.pirates) == 0:
                    return False
                elif len(self.pirates) == 1 and self.pirates[0].location == self.baseLoc:
                    return True

                self.pirates = [pirate for pirate in self.pirates if not pirate.is_lost]

                if path == '-':
                    path = self.last_path
                paths = ['n', 'w', 's', 'e']
                targetLocations = [pos for pirate, pos in zip(self.pirates, self.tankFormations[paths.index(path)])]
                logger.debug("Tank front is faced to the '{}'".format(path))

                # Calculate position for each pirate
                targetLocations = self.changeReference(targetLocations)

                logger.debug('Building tank on baseLoc {}'.format(self.baseLoc))

                self.pirates = [pirate for pirate, pos in zip(self.pirates, targetLocations)]

                # Check available target locations
                tempPirates = list(self.pirates)
                tempLocs = list(targetLocations)

                for pirate_index, pirate in enumerate(self.pirates):
                    if pirate.location in targetLocations:
                        tempPirates.remove(pirate)
                        tempLocs.remove(pirate.location)
                        targetLocations[pirate_index] = pirate.location

                # Update target locations for pirates that are not in a target location.
                for pirate in tempPirates:
                    # Update the target location to be one that is still not occupied:
                    target = min(tempLocs, key=lambda loc: game.distance(loc, pirate))  # Nearest location
                    targetLocations[self.pirates.index(pirate)] = target
                    tempLocs.remove(target)

                # Debug print-out
                # for pirate, pos in zip(self.pirates, targetLocations):
                #     logger.debug("Pirate: {} Location: {} Target: {}".format(pirate.id, pirate.location, pos))

                # Check if pirates are blocking each other and change their targets if so:
                reset = True
                while reset:
                    reset = False
                    for pirate, pos in zip(self.pirates, targetLocations):
                        path = game.get_directions(pirate, pos)[(game.get_turn() % 2) * -1]
                        if not len(path) == 0:
                            dest = game.destination(pirate.location, path)
                            pirateOnLocation = [p for p in self.pirates if p != pirate and p.location == dest]
                            blocker = pirateOnLocation[0] if len(pirateOnLocation) > 0 else None
                            # If some pirate is blocking the way:
                            if blocker is not None:
                                blocker_index = self.pirates.index(blocker)
                                # logger.debug("Pirate %d is blocking %d", blocker.id, pirate.id)
                                # If blocker is where he should be:
                                if blocker.location == targetLocations[blocker_index]:
                                    # Switch target locations between blocker and active pirate:
                                    targetLocations[self.pirates.index(pirate)] = targetLocations[blocker_index]
                                    targetLocations[blocker_index] = pos
                                    # logger.debug("Switched pirate %d with pirate %d", pirate.id,
                                    #              blocker.id)
                                    reset = True

                # Move pirates to formation:
                in_formation = True  # Number of pirates in target place
                for pirate, pos in zip(self.pirates, targetLocations):
                    # logger.debug("P: {}, Loc: {}, T: {} ".format(pirate.id, pirate.location, pos))
                    movePirate(pirate, pos)
                    in_formation &= pirate.location == pos  # if arrived already

                return in_formation

            def onLocation(self, loc):
                loc = nearestPassableLoc(loc, caller_loc=self.findBaseLoc(),
                                         exclude_locations=[p.location for p in self.pirates])
                return all([my_in_range(pirate, loc) for pirate in self.pirates])

            def exportData(self):
                """
                export Tank class instance data to use in next turn

                :return: list with Tank class instance data
                """
                global tankData
                resumeData = [self.baseLoc, self.tankFormations, self.last_path]
                # resumeData.append([p.id for p in self.pirates])

                tankData[self.identifier] = resumeData

            def resumeFromData(self, resumeData):
                """
                resume Tank from data

                :param resumeData: Tank class instance data to use from last turn
                :raise if run into error, debug error but dismass exception
                """
                if resumeData is not None:
                    try:
                        self.baseLoc = resumeData.pop(0)
                        self.tankFormations = resumeData.pop(0)
                        self.last_path = resumeData.pop(0)
                        # To overcome that pirates are passed by value
                        # self.pirates = [game.get_my_pirate(id) for id in resumeData.pop(0)]

                        # logger.debug("Successful resumed data!")
                    except Exception as e:
                        logger.debug("Error while resuming data: {}".format(e.message))

            def calculateFormation(self):
                """
                Calculate positions to form Tank in current game radius (base is (0,0))

                :return: sorted list of good Tank's location, when base is (0,0)
                """

                # Path-faced tank formation calculation:
                # -----------------------------------

                starting_loc = (0, 0)
                direction_forms = []
                for direction in xrange(4):  # n, w, s, e
                    goodloc = []
                    count = 1
                    row = 0
                    while count > 0:
                        count = 0
                        for col in xrange(radius + 1):
                            col_or_row = (direction % 2 == 1)
                            possible_loc = (starting_loc[0] + col_or_row * col + (not col_or_row) * row,
                                            starting_loc[1] + col_or_row * row + (not col_or_row) * col)
                            for test_loc in goodloc:
                                if not my_in_range(possible_loc, test_loc):
                                    break
                            else:
                                count += 1
                                goodloc.append(possible_loc)
                                continue

                        row += 1 + -2 * int(direction >= 2)
                    direction_forms.append(goodloc)

                self.tankFormations = direction_forms  # n, w, s, e

                # Centered tank formation calculation:
                # -----------------------------------

                # starting_loc = (0, 0)
                # goodloc = [starting_loc]
                #
                # possible_loc = starting_loc
                # startedDown = False
                #
                # while True:
                # count = 0
                # while abs(possible_loc[1] - starting_loc[1]) <= radius:
                # for test_loc in goodloc:
                # if not my_in_range(possible_loc, test_loc):
                #                 break
                #         else:
                #             count += 1
                #             goodloc.append(possible_loc)
                #
                #         possible_loc = (possible_loc[0], possible_loc[1] + 1)
                #
                #     if count > 0 and not startedDown:
                #         possible_loc = (possible_loc[0] + 1, starting_loc[1])
                #     else:
                #         if not startedDown:
                #             possible_loc = (starting_loc[0] - 1, starting_loc[1])
                #         else:
                #             possible_loc = (possible_loc[0] - 1, starting_loc[1])
                #
                #         if startedDown and count == 0:
                #             break
                #
                #         startedDown = True
                #
                # goodloc = list(set(goodloc))
                # self.tankFormations = [sorted(goodloc, key=lambda loc: (abs(loc[0]), abs(loc[1])))] * 4

        self.tank_obj = TankInstance(self._pirates,
                                     identifier=self._identifier,
                                     startingLocation=self._starting_location)
        return self.tank_obj

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tank_obj.exportData()
