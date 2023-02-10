import asyncio
import logging


class Lock(asyncio.Lock):
    def __init__(self, id: str, logger, level=logging.DEBUG):
        super(Lock, self).__init__()
        self.id = id
        self.logger = logger
        self.level = level

    @property
    def state(self):
        return "locked" if self.locked() else "unlocked"

    async def acquire(self) -> bool:
        self.logger.log(
            self.level, f"{self.id}: + acquiring. Current state: {self.state}"
        )
        # traceback.print_stack()
        ret = await super(Lock, self).acquire()
        self.logger.log(self.level, f"{self.id}: + locked")
        return ret

    def release(self) -> None:
        self.logger.log(self.level, f"{self.id}: - release")
        # logger.debug('waiters: %s', str(self._waiters))
        # traceback.print_stack()
        super(Lock, self).release()
