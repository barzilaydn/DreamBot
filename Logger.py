# coding=utf-8
import SharedData


class Logger(object):
    last_debug_time = 0

    def __init__(self, debug=True, starting_line=0, ending_line=None):
        self.do_debug = debug
        self.starting_line = starting_line
        self.ending_line = ending_line if ending_line is not None else 1000

    def debug(self, msg, *args):
        if self.do_debug:
            if self.ending_line >= SharedData.game.get_turn() >= self.starting_line:
                msg = str(msg)
                if msg.startswith('----'):  # if head-line, start a new line
                    SharedData.game.debug('/')

                time_took = self.last_debug_time - SharedData.game.time_remaining()
                self.last_debug_time = SharedData.game.time_remaining()

                if time_took > 0:
                    SharedData.game.debug('[{} ms - {} ms]'.format(time_took, SharedData.game.time_remaining()))
                SharedData.game.debug(msg, *args)