import logging
import multiprocessing
import multiprocessing.managers

from . import server


class BackendManager(multiprocessing.managers.BaseManager):
    objects = {}

    @classmethod
    def register(
            cls, obj_cls, path_re, name=None, args=None, kwargs=None,
            init=None, deinit=None):
        if kwargs is None:
            kwargs = {}
        if args is None:
            args = []
        if name is None:
            name = obj_cls.__name__
            if '.' in name:
                name = name.split('.')[-1]
        if name in cls.objects:
            raise ValueError(f"BackendManager: Name[{name}] already registered")
        logging.debug(f"BackendManager: registering object {name}")
        super().register(name, obj_cls)
        cls.objects[name] = (path_re, args, kwargs, init, deinit)

    @classmethod
    def serve(cls, *args, **kwargs):
        with cls() as mgr:
            # make objects
            deinits = {}
            for name in cls.objects:
                path_re, args, kwargs, init, deinit = cls.objects[name]
                logging.debug(f"BackendManager: constructing {name}")
                obj = getattr(mgr, name)(*args, **kwargs)
                server.register(obj, path_re)
                if init is not None:
                    logging.debug(f"BackendManager: init {name}")
                    init(obj)
                if deinit is not None:
                    deinits[name] = (deinit, obj)
            logging.debug(f"BackendManager: starting server")
            server.run_forever(*args, **kwargs)
            for name in deinits:
                logging.debug(f"BackendManager: deinit {name}")
                deinit, obj = deinits[name]
                deinit(obj)


def register(cls, path_re, name=None, args=None, kwargs=None, init=None, deinit=None):
    BackendManager.register(cls, path_re, name, args, kwargs, init, deinit)


def serve(*args, **kwargs):
    BackendManager.serve()
