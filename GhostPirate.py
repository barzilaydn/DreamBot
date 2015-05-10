# coding=utf-8
from SharedData import *  # Just to ignore the warnings about globals
import SharedData


class GhostPirate(object):
    def __init__(self):
        globals().update(SharedData.__dict__)  # Ugly hack to import all SharedData vars for use
        self.cloaked_Pirate_id = None
        self.cloaked_on_this_turn = False

    def cloakPirate(self, pirate):
        if self.cloaked_Pirate_id is not None and pirate.id != self.cloaked_Pirate_id:
            raise Exception('Pirate {} already cloaked, can\'t cloak another pirate ({}).'
                            .format(self.cloaked_Pirate_id, pirate.id))
        elif self.cloaked_on_this_turn:
            logger.debug('Can\'t cloak pirate {}, {} got cloaked on this turn.'
                         .format(pirate.id, self.cloaked_Pirate_id))
            return False
        elif not game.can_cloak():
            logger.debug('Can\'t cloak pirate {}, not enough turns passed since last cloaking,'
                         ' or pirate already cloaked.'
                         .format(pirate.id))
            return False

        logger.debug('Cloaking pirate {}'.format(pirate.id))
        self.cloaked_on_this_turn = True
        self.cloaked_Pirate_id = pirate.id
        game.cloak(pirate)
        return True

    def revealPirate(self):
        if self.cloaked_on_this_turn:
            logger.debug('Can\'t reveal pirate {}, {} got cloaked on this turn.'
                         .format(self.cloaked_Pirate_id, self.cloaked_Pirate_id))
            return False

        logger.debug('Revealing pirate {}'.format(self.cloaked_Pirate_id))
        self.cloaked_on_this_turn = True
        game.reveal(game.get_my_pirate(self.cloaked_Pirate_id))
        return True

    def update(self):
        self.cloaked_on_this_turn = False

        current_cloaked = game.get_my_cloaked()
        if current_cloaked is not None:
            self.cloaked_Pirate_id = current_cloaked.id
