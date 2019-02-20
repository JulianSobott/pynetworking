"""
@author: Julian Sobott
@brief:
@description:

@external_use:

@internal_use:
"""
import threading
import socket
import time
from typing import Tuple, List, Dict, Optional, Callable, Any, Type, Union

from Logging import logger
from Packets import Packet, DataPacket, FunctionPacket, Header
from ID_management import IDManager, remove_manager
from Data import ByteStream

SocketAddress = Tuple[str, int]


class Communicator(threading.Thread):
    CHUNK_SIZE = 1024

    def __init__(self, address: SocketAddress, id_=0, socket_connection=socket.socket(), from_accept=False,
                 on_close: Optional[Callable[['Communicator'], Any]] = None) -> None:
        super().__init__(name=f"{'Client' if from_accept else 'Server'}_Communicator_thread_{id_}")
        self._socket_connection = socket_connection
        self._address = address
        self._id = id_
        self._is_on = True
        self._is_connected = from_accept
        self._keep_connection = not from_accept
        self._packets: List[Packet] = []
        self._exit = threading.Event()
        self._time_till_next_check = 0.3
        self._on_close = on_close

    def run(self) -> None:
        if not self._is_connected:
            self._connect()
        self._wait_for_new_input()

    def _connect(self, seconds_till_next_try=2, timeout=-1) -> bool:
        waited = 0
        while self._is_on and not self._is_connected:
            try:
                self._socket_connection = socket.create_connection(self._address)
                self._is_connected = True
                logger.debug(f"Successfully connected to: {str(self._address)}")
                return True
            except ConnectionRefusedError:
                logger.warning("Could not connect to server with address: (%s)", str(self._address))
            except OSError as e:
                logger.error("Is already connected to server")
                logger.debug(e)
                self._is_connected = True

            self._exit.wait(seconds_till_next_try)
            waited += seconds_till_next_try
            if waited > timeout >= 0:
                logger.warning("Connection timeout")
                return False
        return False

    def _wait_for_new_input(self) -> None:
        packet_builder = PacketBuilder()
        with self._socket_connection:
            while self._is_on:
                # logger.debug(f"{self.getName()} : {self._is_on}")
                if self._is_on and not self._is_connected:
                    if self._keep_connection:
                        self._connect()
                    else:
                        self.stop(is_same_thread=True)
                try:
                    chunk_data = self._socket_connection.recv(self.CHUNK_SIZE)
                    if chunk_data == b"":
                        logger.warning("Connection reset, (%s)", str(self._address))
                        self._is_connected = False
                    else:
                        possible_packet = packet_builder.add_chunk(chunk_data)
                        if possible_packet is not None:
                            self._packets.append(possible_packet)

                except ConnectionResetError:
                    logger.warning("Connection reset, (%s)", str(self._address))
                    self._is_connected = False

                except ConnectionAbortedError:
                    logger.warning("Connection aborted, (%s)", str(self._address))
                    self._is_connected = False

                except OSError:
                    logger.warning("TCP connection closed while listening")
                    self._is_connected = False

                self._exit.wait(self._time_till_next_check)

            logger.debug(f"finished _wait_for_new_input {self.getName()}")

    def send_packet(self, packet: Packet) -> bool:
        # TODO: add type hinting when implementation is finished
        if not self._is_connected:
            self._connect(timeout=2)
        try:
            IDManager(self._id).set_ids_of_packet(packet)
            send_data = packet.pack()
            total_sent = 0
            data_size = len(send_data)
            while total_sent < data_size:
                sent = self._socket_connection.send(send_data[total_sent:])
                if sent == 0:
                    logger.error("Connection closed. Could not send packet")
                    self._is_connected = False
                total_sent += sent
            self._is_connected = True
            return total_sent == data_size
        except OSError:
            logger.error("Could not send packet: %s", str(packet))
            return False

    def wait_for_response(self, timeout=10):
        # TODO: add type hinting when implementation is finished
        waited = 0.
        next_outer_id = IDManager(self._id).get_next_outer_id()
        while self._is_on:
            try:
                next_packet = self._packets.pop(0)
                actual_outer_id = next_packet.header.id_container.outer_id
                if actual_outer_id > next_outer_id:
                    logger.error(f"Packet lost! Expected outer_id: {next_outer_id}. Got instead: {actual_outer_id}")
                    # TODO: handle
                elif actual_outer_id < next_outer_id:
                    logger.error(f"Unhandled Packet! Expected outer_id: {next_outer_id}. "
                                 f"Got instead: {actual_outer_id}")
                    # TODO: handle (if possible)
                else:
                    if isinstance(next_packet, FunctionPacket):
                        #recv_function_function(next_packet)
                        return
                    elif isinstance(next_packet, DataPacket):
                        return next_packet
                    else:
                        logger.error(f"Received not implemented Packet class: {type(next_packet)}")

            except IndexError:
                pass  # List is empty -> wait
            self._exit.wait(self._time_till_next_check)
            waited += self._time_till_next_check
            if waited > timeout >= 0:
                logger.warning("Connection timeout")
                return DataPacket(**{"return": TimeoutError()})

    def received_function_packet(self, packet: FunctionPacket) -> None:
        try:
            func = packet.function_name
            args = packet.args
            kwargs = packet.kwargs
            try:
                ret_value = func(*args, **kwargs)
            except TypeError as e:
                ret_value = e
        except AttributeError as e:
            ret_value = e
        ret_kwargs = {"return": ret_value}
        data_packet = DataPacket(**ret_kwargs)
        # TODO:  handle if communicator is not assigned (None)
        communicator: Optional[Communicator] = cls.__getattr__("communicator")
        communicator.send_packet(data_packet)

    def stop(self, is_same_thread=False) -> None:
        """Calling from another thread"""
        self._is_on = False
        self._exit.set()
        try:
            pass
            self._socket_connection.close()
        except AttributeError:
            logger.debug("Connection already closed")
            pass  # Connection already closed
        self._is_connected = False
        if not is_same_thread:
            self.join()
        remove_manager(self._id)
        if self._on_close is not None:
            try:
                self._on_close(self)
            except TypeError:
                pass  # no function provided

    def is_connected(self) -> bool:
        return self._is_connected

    def get_id(self) -> int:
        return self._id


class PacketBuilder:

    def __init__(self) -> None:
        self.byte_stream = ByteStream(b"")
        self.current_header: Optional[Header] = None

    def add_chunk(self, byte_string: bytes) -> Optional[Packet]:
        self.byte_stream += byte_string
        if self.current_header is None and self.byte_stream.length >= Header.LENGTH_BYTES:
            self.current_header = Header.from_bytes(self.byte_stream)
        if self.current_header and self.byte_stream.remaining_length >= self.current_header.specific_data_size:
            packet = Packet.from_bytes(self.current_header, self.byte_stream)
            self.byte_stream.remove_consumed_bytes()
            return packet
        return None


class MetaFunctionCommunicator(type):

    def __call__(self, *args, **kwargs):
        try:
            timeout = kwargs["timeout"]
            Functions.__setattr__(Functions, "timeout", timeout)
        except KeyError:
            pass
        return self

    def __getattribute__(self, item):

        if item == "__getattr__":
            return type.__getattribute__(self, item)
        if item == "__setattr__":
            return type.__setattr__
        if item == "__call__":
            return type.__call__

        def container(*args, **kwargs):
            function_name = item
            timeout = self.__getattr__("timeout")
            # send function packet
            sent_packet = self.__getattr__("_send_function")(function_name, *args, **kwargs)
            # recv data packet
            if not sent_packet:
                raise ConnectionError()

            data_packet = self.__getattr__("communicator").wait_for_response(timeout=timeout)
            # unpack data packet
            return_values = data_packet.data["return"]
            return return_values

        return container

    def _send_function(cls, function_name: str, *args, **kwargs) -> bool:
        # TODO: add type hinting when implementation is finished
        communicator: Optional[Communicator] = cls.__getattr__("communicator")
        if communicator is None:
            logger.error("No communicator connected. First connect to a server")
            return False
        packet = FunctionPacket(function_name, *args, **kwargs)
        return communicator.send_packet(packet)

    def recv_function(cls, function_name: str, args, kwargs):
        # TODO: add type hinting when implementation is finished
        try:
            func = type.__getattribute__(cls, function_name)
            try:
                ret_value = func(*args, **kwargs)
            except TypeError as e:
                ret_value = e
        except AttributeError as e:
            ret_value = e
        ret_kwargs = {"return": ret_value}
        data_packet = DataPacket(**ret_kwargs)
        # TODO:  handle if communicator is not assigned (None)
        communicator: Optional[Communicator] = cls.__getattr__("communicator")
        communicator.send_packet(data_packet)

    def __getattr__(self, item):
        func = type.__getattribute__(self, item)
        return func


class MetaSingletonConnector(type):
    _instances: Dict[int, 'Connector'] = {}

    def __call__(cls, *args, **kwargs) -> 'Connector':
        id_: int = args[0]
        if id_ not in cls._instances:
            cls._instances[id_] = super(MetaSingletonConnector, cls).__call__(id_)
        return cls._instances[id_]

    @classmethod
    def remove(mcs, id_: int) -> 'Connector':
        return mcs._instances.pop(id_)

    @classmethod
    def remove_all(mcs) -> Dict[int, 'Connector']:
        ret = dict(mcs._instances)
        mcs._instances = {}
        return ret


class Connector:
    functions: Optional[Type['Functions']] = None
    communicator: Optional[Communicator] = None
    id = 0

    @staticmethod
    def connect(connector: Union['Connector', Type['SingleConnector']], addr: SocketAddress, blocking=True,
                time_out=float("inf")) -> bool:
        if connector.communicator is None:
            connector.communicator = Communicator(addr, id_=connector.id)
            connector.functions.__setattr__(connector.functions, "communicator", connector.communicator)
            connector.communicator.start()
            if blocking:
                waited = 0.
                wait_time = 0.01
                while not connector.communicator.is_connected() and waited < time_out:
                    time.sleep(wait_time)
                    waited += wait_time
                if waited >= time_out:
                    logger.debug("Stopped communicator due to timeout")
                    connector.communicator.stop()
        assert isinstance(connector.communicator, Communicator)
        return connector.communicator.is_connected()

    @staticmethod
    def close_connection(connector: Union['Connector', Type['SingleConnector']], blocking=True,
                         time_out=float("inf")) -> None:
        if connector.communicator is not None:
            connector.communicator.stop()
            if blocking:
                waited = 0.
                wait_time = 0.01
                while connector.communicator.is_connected() and waited < time_out:
                    time.sleep(wait_time)
                    waited += wait_time
            connector.communicator = None

    @staticmethod
    def is_connected(connector: Union['Connector', Type['SingleConnector']]) -> bool:
        if connector.communicator is None:
            return False
        return connector.communicator.is_connected()


class MultiConnector(Connector, metaclass=MetaSingletonConnector):

    def __init__(self, id_: int) -> None:
        self.id = id_
        self.communicator: Optional[Communicator] = None

    def connect(self: Connector, addr: SocketAddress, blocking=True, time_out=float("inf")) -> bool:
        return super().connect(self, addr, blocking, time_out)

    def close_connection(self: Connector, blocking=True, time_out=float("inf")) -> None:
        return super().close_connection(self, blocking, time_out)

    @staticmethod
    def close_all_connections() -> None:
        all_instances = MetaSingletonConnector.remove_all()
        for id_, connector in all_instances.items():
            connector.close_connection(connector)

    def is_connected(self) -> bool:
        return super().is_connected(self)


class SingleConnector(Connector):
    """Only static accessible. Therefore only a single connector (per address) per machine possible"""

    @classmethod
    def connect(cls, addr: SocketAddress, blocking=True, time_out=float("inf")) -> bool:
        return super().connect(cls, addr, blocking, time_out)

    @classmethod
    def close_connection(cls, blocking=True, time_out=float("inf")) -> None:
        return super().close_connection(cls, blocking, time_out)

    @classmethod
    def is_connected(cls) -> bool:
        return super().is_connected(cls)


class Functions(metaclass=MetaFunctionCommunicator):
    communicator: Optional[Communicator] = None
    timeout = float("inf")

    def __new__(cls, *args, **kwargs):
        pass

