from flask import current_app

actions = {}


def register(hook, action):
    # app.logger.debug('registering hook %s -> %s', hook, action)
    actions.setdefault(hook, []).append(action)


def fire(hook, *args, **kwargs):
    current_app.logger.debug('firing hook %s', hook)
    return [action(*args, **kwargs)
            for action in actions.get(hook, [])]
