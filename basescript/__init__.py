from basescript import BaseScript

ENTRY_POINT = "basescript.extensions"
try:
    from pkg_resources import iter_entry_points
except ImportError:
    pass
else:
    # adding all extensions here
    for ep in iter_entry_points(ENTRY_POINT):
        extension_class = ep.load()
        # add only those that are subclasses of BaseScript
        if issubclass(extension_class, BaseScript):
            globals()[ep.name] = extension_class
