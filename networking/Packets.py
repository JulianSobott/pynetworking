"""
@author: Julian Sobott
@brief:
@description:

all available packets:
-Function_packet:
-Status_packet:
-DataPacket:
-File_meta_packet:

general packet byte string:
<packet_byte_string_len><function_id><inner_id><outer_id><packet_cls_id><specific_packet_data>


GeneralPacket:
    Header:
        - PacketType (Function, Data, Status, File)
        - ID's
        - specific data size
    Specific Data:

@external_use:
packet = <cls>_packet(args)
byte_string = packet.pack()
same_packet = Packet.unpack(byte_string)


@internal_use:
New <cls>_packet:
    extend from packet
    implement: pack, unpack, __eq__, __str__
    add to packets

@TODO:
- create concept of Byte stream and extract packets (maybe in other file)
- save delete unpack function in Packet
"""
from enum import Enum
import os

from .utils import Ddict
from .Logging import logger
from .Data import IDContainer, pack_int_type, unpack_int_type, NUM_INT_BYTES, BYTEORDER, NUM_TYPE_BYTES, _unpack, _pack, \
    ByteStream, pack_int


class Header:

    def __init__(self, id_container, packet_type, specific_data_size):
        self.id_container = id_container
        self.packet_type = packet_type
        self.specific_data_size = specific_data_size

    @classmethod
    def from_packet(cls, packet):
        packet_type = packets[packet.__class__]
        id_container = IDContainer.default_init()
        specific_data_size = 0
        return cls.__call__(id_container, packet_type, specific_data_size)

    @classmethod
    def from_bytes(cls, byte_stream):
        id_container = IDContainer.from_bytes(byte_stream)
        packet_type = unpack_int_type(byte_stream.next_bytes(NUM_TYPE_BYTES))
        specific_data_size = byte_stream.next_int()
        return cls.__call__(id_container, packet_type, specific_data_size)

    def pack(self, len_packet_data):
        """id's + packet_type + len_packet_data"""
        self.specific_data_size = len_packet_data
        byte_string = b""
        byte_string += self.id_container.pack()
        byte_string += pack_int_type(self.packet_type)
        byte_string += pack_int(len_packet_data)
        return byte_string

    def __eq__(self, other):
        if not isinstance(other, Header):
            return False
        return (self.id_container == other.id_container and
                self.packet_type == other.packet_type and
                self.specific_data_size == other.specific_data_size)

    def __repr__(self):
        return packets[self.packet_type].__name__ + ": " + str(self.id_container) + "\n\t"


class Packet:

    def __init__(self, packet):
        self.header = Header.from_packet(packet)

    def pack(self):
        pass

    def _pack_all(self, specific_data_bytes):
        byte_string = b""
        data_length = len(specific_data_bytes)
        byte_string += self.header.pack(data_length)
        byte_string += specific_data_bytes
        return byte_string

    @classmethod
    def from_bytes(cls, header, byte_stream):
        if header.packet_type not in packets.values():
            raise ValueError("Unknown packet ID: (" + str(header.packet_type) + ")")
        packet = packets[header.packet_type].from_bytes(header, byte_stream)
        return packet

    def __eq__(self, other):
        if isinstance(other, Packet):
            return self.header == other.header
        else:
            return False

    def __repr__(self):
        return str(self.header)


class DataPacket(Packet):
    """Packet to send named data
    Available data types are all defined in :py:const:`~networking.Data.type`"""
    def __init__(self, **kwargs):
        super().__init__(self)
        self.data = kwargs

    @classmethod
    def from_bytes(cls, header, byte_stream):
        all_data = _unpack(byte_stream)
        packet = DataPacket(**all_data[0])
        packet.header = header
        return packet

    def pack(self):
        specific_byte_string = b""
        specific_byte_string += _pack(self.data)
        return super()._pack_all(specific_byte_string)

    @staticmethod
    def get_empty_size(data_name):
        length = IDContainer.TOTAL_BYTE_LENGTH
        length += NUM_TYPE_BYTES
        length += len(_pack(data_name))
        length += NUM_INT_BYTES
        length += 14    # Length of tuple
        return length

    def __eq__(self, other):
        if super().__eq__(other) and isinstance(other, DataPacket):
            return self.data == other.data
        else:
            return False

    def __repr__(self):
        string = super().__repr__()
        string += str(self.data)
        return string


class Function_packet(Packet):

    def __init__(self, func, *args):
        super().__init__(self)
        if type(func) is str:
            self.function_name = func
        else:
            self.function_name = func.__name__
        self.data = args

    def execute(self, connection, functions):
        func = functions.get_function(self.function_name)
        func(connection, *self.data)

    @staticmethod
    def unpack(byte_string):
        all_data = _unpack(byte_string)
        function_name = all_data[0]
        args = all_data[1]
        packet = Function_packet(function_name, *args)
        return packet

    def pack(self):
        byte_string = b""
        byte_string += super().pack()
        byte_string += _pack(self.function_name, self.data)

        len_string = len(byte_string)
        b_len_string = int.to_bytes(len_string, NUM_INT_BYTES, BYTEORDER, signed=False)

        return b_len_string + byte_string

    def __eq__(self, other):
        if super().__eq__(other) and isinstance(other, Function_packet):
            return self.function_name == other.function_name and self.data == other.data
        else:
            return False

    def __str__(self):
        string = super().__str__()
        string += str(self.function_name)
        string += str(self.data)
        return string


class Status_packet(Packet):

    class Status_code(Enum):
        successful = 0
        failed = 1

    def __init__(self, status_code, text="", last_in_func=True):
        super().__init__(self)
        self.status_code = status_code
        self.text = text
        self.last_in_func = last_in_func

    def pack(self):
        byte_string = b""
        byte_string += super().pack()
        val_status_code = self.status_code.value
        byte_string += _pack(val_status_code, self.text, self.last_in_func)
        len_string = len(byte_string)
        b_len_string = int.to_bytes(len_string, NUM_INT_BYTES, BYTEORDER, signed=False)
        return b_len_string + byte_string

    @staticmethod
    def unpack(byte_string):
        all_data = _unpack(byte_string)
        status_code = all_data[0]
        text = all_data[1]
        last_in_func = all_data[2]

        return Status_packet(Status_packet.Status_code(status_code), text, last_in_func)

    def is_success(self):
        return self.status_code == Status_packet.Status_code.successful

    def __eq__(self, other):
        if super().__eq__(other) and isinstance(other, Status_packet):
            return self.status_code == other.status_code and self.text == other.text
        else:
            return self.status_code == Status_packet.Status_code.successful

    def __str__(self):
        string = super().__str__()
        string += str(self.status_code)
        string += ": \""
        string += str(self.text)
        string += "\""
        return string



class File_meta_packet(DataPacket):

    def __init__(self, abs_path):
        if os.path.exists(abs_path):
            self.file_name = os.path.split(abs_path)[1]
            self.extension = os.path.splitext(abs_path)[1]
            self.size = os.path.getsize(abs_path)
        else:
            self.file_name = "NULL"
            self.extension = "NULL"
            self.size = 0
        super().__init__("file meta data", self.file_name, self.extension, self.size)

    def set_attributes(self, name, extension, size):
        self.file_name = name
        self.extension = extension
        self.size = size
        super().__init__("file meta data", self.file_name, self.extension, self.size)

    def pack(self):
        byte_string = b""
        byte_string += super().pack()
        return byte_string

    @staticmethod
    def unpack(byte_string):
        all_data = _unpack(byte_string)
        packet = File_meta_packet("None")
        name = all_data[1][0]
        extension = all_data[1][1]
        size = all_data[1][2]
        packet.set_attributes(name, extension, size)
        return packet

    def __eq__(self, other):
        if super().__eq__(other) and isinstance(other, File_meta_packet):
            return self.file_name == other.file_name and self.extension == other.extension and self.size == other.size
        else:
            return False

    def __str__(self):
        string = super().__str__()
        # string += "File_meta_data: "
        # string += str(self.name) + " (" + str(self.size) + ")"
        return string


packets = Ddict({
    Function_packet:    0x101,
    Status_packet:      0x102,
    DataPacket:        0x103,
    File_meta_packet:   0x104
})