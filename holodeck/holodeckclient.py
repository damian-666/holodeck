import os
import numpy as np

from holodeck.exceptions import HolodeckException
from holodeck.shmem import Shmem


class HolodeckClient:
    def __init__(self, uuid=""):
        self._uuid = uuid

        # Important functions
        self._get_semaphore_fn = None
        self._release_semaphore_fn = None
        self._semaphore1 = None
        self._semaphore2 = None
        self.unlink = None

        self._memory = dict()
        self._sensors = dict()
        self._agents = dict()
        self._settings = dict()

        if os.name == "nt":
            self.__windows_init__()
        elif os.name == "posix":
            self.__posix_init__()
        else:
            raise HolodeckException("Currently unsupported os: " + os.name)

    def __windows_init__(self):
        import win32event
        semaphore_all_access = 0x1F0003
        self._semaphore1 = win32event.OpenSemaphore(semaphore_all_access, False,
                                                    "Global\\HOLODECK_SEMAPHORE_SERVER" + self._uuid)
        self._semaphore2 = win32event.OpenSemaphore(semaphore_all_access, False,
                                                    "Global\\HOLODECK_SEMAPHORE_CLIENT" + self._uuid)

        def windows_acquire_semaphore(sem):
            win32event.WaitForSingleObject(sem, 100000)  # 100 second timeout

        def windows_release_semaphore(sem):
            win32event.ReleaseSemaphore(sem, 1)

        def windows_unlink():
            pass

        self._get_semaphore_fn = windows_acquire_semaphore
        self._release_semaphore_fn = windows_release_semaphore
        self.unlink = windows_unlink

    def __posix_init__(self):
        import posix_ipc
        self._semaphore1 = posix_ipc.Semaphore("/HOLODECK_SEMAPHORE_SERVER" + self._uuid)
        self._semaphore2 = posix_ipc.Semaphore("/HOLODECK_SEMAPHORE_CLIENT" + self._uuid)

        def posix_acquire_semaphore(sem):
            sem.acquire(None)

        def posix_release_semaphore(sem):
            sem.release()

        def posix_unlink():
            posix_ipc.unlink_semaphore(self._semaphore1.name)
            posix_ipc.unlink_semaphore(self._semaphore2.name)
            for shmem_block in self._memory.values():
                shmem_block.unlink()

        self._get_semaphore_fn = posix_acquire_semaphore
        self._release_semaphore_fn = posix_release_semaphore
        self.unlink = posix_unlink

    def acquire(self):
        self._get_semaphore_fn(self._semaphore2)

    def release(self):
        self._release_semaphore_fn(self._semaphore1)

    def malloc(self, key, shape, dtype):
        if key not in self._memory or self._memory[key].shape != shape or self._memory[key].dtype != dtype:
            self._memory[key] = Shmem(key, shape, dtype, self._uuid)

        return self._memory[key].np_array
