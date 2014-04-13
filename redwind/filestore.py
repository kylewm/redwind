import os
import time


def _get_lock_filename(path):
    if os.path.isdir(path):
        lockfile = os.path.join(path, '.lock')
    else:
        lockfile = path + '.lock'
    return lockfile


def acquire_lock(path, retries):
    lockfile = _get_lock_filename(path)

    if not os.path.exists(os.path.dirname(lockfile)):
        os.makedirs(os.path.dirname(lockfile))

    while os.path.exists(lockfile) and retries > 0:
        time.sleep(1)
        retries -= 1

    if os.path.exists(lockfile):
        raise RuntimeError("Timed out waiting for lock to become available {}"
                           .format(lockfile))

    with open(lockfile, 'w') as f:
        f.write("1")
    return True


def release_lock(path):
    lockfile = _get_lock_filename(path)
    os.remove(lockfile)


def open(path):
    pass

def open_writeable(path):
    pass
