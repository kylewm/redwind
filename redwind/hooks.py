from . import app

actions = {}


def register(hook, action):
    app.logger.debug('registering hook %s -> %s', hook, action)
    actions.setdefault(hook, []).append(action)


def fire(hook, *args, **kwargs):
    app.logger.debug('firing hook %s', hook)
    return [action(*args, **kwargs)
            for action in actions.get(hook, [])]
