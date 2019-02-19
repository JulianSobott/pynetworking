"""
@author: Julian Sobott
@brief:
@description:

@external_use:

@internal_use:

@TODO: test id's when packets are implemented
"""
from unittest import TestCase

from networking.ID_management import *
from Packets import FunctionPacket, DataPacket
from Logging import logger


class TestIDManager(TestCase):

    def test_multiple_same_managers(self):
        manager1_0 = IDManager(1)
        manager1_1 = IDManager(1)
        self.assertEqual(manager1_0, manager1_1)

    def test_multiple_different_managers(self):
        manager1 = IDManager(1)
        manager2 = IDManager(2)
        self.assertNotEqual(manager1, manager2)

    def test_remove_manager(self):
        manager1_0 = IDManager(1)
        remove_manager(1)
        manager1_1 = IDManager(1)
        self.assertNotEqual(manager1_0, manager1_1)

    def test_one_func_packet(self):
        packet = FunctionPacket("dummy")
        IDManager(0).set_ids_of_packet(packet)
        expected_ids = (0, 0)
        self.assertEqual(expected_ids, packet.header.id_container.get_ids())
        expected_function_stack = [0]
        self.assertEqual(expected_function_stack, IDManager(0).get_function_stack())

    def test_func_data(self):
        func_packet = FunctionPacket("dummy")
        IDManager(0).set_ids_of_packet(func_packet)

        data_packet = DataPacket(ret="Nothing")
        IDManager(0).set_ids_of_packet(data_packet)
        expected_ids = (0, 1)
        self.assertEqual(expected_ids, data_packet.header.id_container.get_ids())
        expected_function_stack = []
        self.assertEqual(expected_function_stack, IDManager(0).get_function_stack())

    def test_func_func_data_data(self):
        self.assertEqual([], IDManager(0).get_function_stack())

        func_packet_0 = FunctionPacket("dummy")
        IDManager(0).set_ids_of_packet(func_packet_0)
        self.assertEqual((0, 0), func_packet_0.header.id_container.get_ids())
        self.assertEqual([0], IDManager(0).get_function_stack())

        func_packet_1 = FunctionPacket("Dummy")
        IDManager(0).set_ids_of_packet(func_packet_1)
        self.assertEqual((1, 1), func_packet_1.header.id_container.get_ids())
        self.assertEqual([0, 1], IDManager(0).get_function_stack())

        data_packet_1 = DataPacket(ret="Nothing")
        IDManager(0).set_ids_of_packet(data_packet_1)
        self.assertEqual((1, 2), data_packet_1.header.id_container.get_ids())
        self.assertEqual([0], IDManager(0).get_function_stack())

        data_packet_0 = DataPacket(ret="Nothing")
        IDManager(0).set_ids_of_packet(data_packet_0)
        self.assertEqual((0, 3), data_packet_0.header.id_container.get_ids())
        self.assertEqual([], IDManager(0).get_function_stack())
