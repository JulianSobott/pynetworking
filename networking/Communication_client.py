"""
@author: Julian Sobott
@brief:
@description:

@external_use:

@internal_use:
"""
from typing import Optional

from networking.Logging import logger
from networking.Communication_general import SingleConnector, MultiConnector, Functions, Communicator


class ServerCommunicator(SingleConnector):
    """A static accessible class, that is responsible for communicating with the server.
    This class needs to be overwritten. The overwritten class needs to set the attributes :code:`local_functions` and
    :code:`remote_functions`. To call a function at the server type:
    :code:`ServerCommunicator.remote_functions.dummy_function(x, y)`
    """
    pass


class MultiServerCommunicator(MultiConnector):
    """A class that allows in contrast to the :class:`ServerCommunicator` multiple instances. This class also needs
    to be overwritten, just like :class:`ServerCommunicator`. To create and use call :code:`MultiServerCommunicator(n)`,
    where n is any number below 30. The object may not be stored, but can be called in different parts of the Code and
    the same object is returned, like a Singleton.
    """
    pass


class ServerFunctions(Functions):
    """Static class that contains all available server side functions. All functions must be stored in the
    :attr:`__dict__` attribute."""
    pass

