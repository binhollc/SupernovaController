import os
import unittest
from supernovacontroller.sequential.supernova_device import SupernovaDevice
from supernovacontroller.sequential.i3c import SupernovaI3CBlockingInterface

from binhosimulators import BinhoSupernovaSimulator

BMM350_DATA = {"asString": ["0x07", "0x70", "0x10", "0x33", "0x00", "0x00"], "asInt": [7, 112, 16, 51, 0, 0]}
BMI323_DATA = {"asString": ["0x07", "0x70", "0x10", "0x43", "0x10", "0x00"], "asInt": [7, 112, 16, 67, 16, 0]}

class TestSupernovaController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Initializes the testing class. Determines whether to use the simulator or real device
        based on the "USE_REAL_DEVICE" environment variable. Default is to use the simulator.
        """
        cls.use_simulator = not os.getenv("USE_REAL_DEVICE", "False") == "True"

    def setUp(self):
        self.device = SupernovaDevice()

        if self.use_simulator:
            self.device.driver = BinhoSupernovaSimulator()

        self.device_info = self.device.open()
        self.i3c : SupernovaI3CBlockingInterface = self.device.create_interface("i3c.controller")

    def tearDown(self):
        self.device.close()

    def test_i3c_ccc_setaasa(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        self.i3c.init_bus(3300)
        (deviceFound, bmm350) = self.i3c.find_target_device_by_pid(BMM350_DATA["asString"])
        if not deviceFound:
            self.skipTest("For BMM350")

        (success, response) = self.i3c.ccc_getpid(0x08)
        self.assertTupleEqual((True, BMM350_DATA["asInt"]), (success, response))

        self.i3c.ccc_rstdaa()

        (success, response) = self.i3c.ccc_setaasa([0x14])
        self.assertTupleEqual((True, None), (success, response))

        (success, response) = self.i3c.ccc_getpid(0x14)
        self.assertTupleEqual((True, BMM350_DATA["asInt"]), (success, response))

    def test_i3c_ccc_setaasa_errors(self):
        if self.use_simulator:
            self.skipTest("For real device only")
        self.i3c.init_bus(3300)
        (deviceFound, bmm350) = self.i3c.find_target_device_by_pid(BMM350_DATA["asString"])
        if not deviceFound:
            self.skipTest("For BMM350")

        self.i3c.ccc_rstdaa()
        (res, msg) = self.i3c.ccc_setaasa([0x00])
        self.assertTupleEqual((res, msg), 
                              (False,
                               {"error": "INVALID_ADDRESS", "error_data": [{"address": "0x00", "error": "ADDRESS_RESERVED"}]}))

        (res, msg) = self.i3c.ccc_setaasa([0x14]) # Correctly set DA
        self.assertTupleEqual((True, None), (res, msg))

        (res, msg) = self.i3c.ccc_setaasa([0x14])
        self.assertTupleEqual((res, msg), 
                              (False,
                               {"error": "INVALID_ADDRESS", "error_data": [{"address": "0x14", "error": "ADDRESS_ALREADY_ASSIGNED_TO_I3C_DEVICE"}]}))

    def test_i3c_ccc_setdasa_errors(self):
        if self.use_simulator:
            self.skipTest("For real device only")
        self.i3c.init_bus(3300)
        (deviceFound, bmm350) = self.i3c.find_target_device_by_pid(BMM350_DATA["asString"])
        if not deviceFound:
            self.skipTest("For BMM350")

        self.i3c.ccc_rstdaa()
        (res, msg) = self.i3c.ccc_setdasa(0x14, 0x00)
        self.assertTupleEqual((res, msg), 
                              (False,
                               {"error": "INVALID_ADDRESS", "error_data": [{"address": "0x00", "error": "ADDRESS_RESERVED"}]}))

        (res, msg) = self.i3c.ccc_setdasa(0x14, 0x08) # Correctly set DA
        self.assertTupleEqual((True, None), (res, msg))

        (res, msg) = self.i3c.ccc_setdasa(0x14, 0x08)
        self.assertTupleEqual((res, msg), 
                              (False,
                               {"error": "INVALID_ADDRESS", "error_data": [{"address": "0x08", "error": "ADDRESS_ALREADY_ASSIGNED_TO_I3C_DEVICE"}]}))

    def test_i3c_ccc_entdaa(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        self.i3c.init_bus(3300)
        (deviceFound, bmi323) = self.i3c.find_target_device_by_pid(BMI323_DATA["asString"])
        if not deviceFound:
            self.skipTest("For BMI323")

        entdaa_target_dict = {
            "bmi323" : {
            "staticAddress" : 0x14,
            "dynamicAddress" : 0x09,
            "i3cFeatures": 11,
            "maxIbiPayloadLength": 233,
            "bcr" : 6,
            "dcr" : 239,
            "pid" : [7, 112, 16, 67, 16, 0]
            },
        }

        (success, response) = self.i3c.ccc_getpid(bmi323["dynamic_address"])
        self.assertTupleEqual((True, BMI323_DATA["asInt"]), (success, response))

        (res, msg) = self.i3c.reset_bus()
        self.assertTupleEqual((True, 3300), (res, msg))

        (res, msg) = self.i3c.ccc_entdaa(entdaa_target_dict)
        self.assertTupleEqual((True, None), (res, msg))
        
        (success, response) = self.i3c.ccc_getpid(0x09)
        self.assertTupleEqual((True, BMI323_DATA["asInt"]), (success, response))

        (deviceFound, bmi323) = self.i3c.find_target_device_by_pid(BMI323_DATA["asString"])
        self.assertTupleEqual((True, {
                "static_address" : 0x14,
                "dynamic_address" : 0x09,
                "bcr" : 6,
                "dcr" : 239,
                "pid" : ["0x07", "0x70", "0x10", "0x43", "0x10", "0x00"]
                },), (deviceFound, bmi323))
    
    def test_i3c_ccc_entdaa_invalid_address(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        self.i3c.init_bus(3300)
        (deviceFound, bmi323) = self.i3c.find_target_device_by_pid(BMI323_DATA["asString"])
        if not deviceFound:
            self.skipTest("For BMI323")

        entdaa_target_dict = {
            "bmi323" : {
            "staticAddress" : 0x14,
            "dynamicAddress" : 0x00,
            "i3cFeatures": 11,
            "maxIbiPayloadLength": 233,
            "bcr" : 6,
            "dcr" : 239,
            "pid" : [7, 112, 16, 67, 16, 0]
            },
        }

        (res, msg) = self.i3c.reset_bus()
        self.assertTupleEqual((True, 3300), (res, msg))

        (res, msg) = self.i3c.ccc_entdaa(entdaa_target_dict)
        self.assertTupleEqual((False, 
                               {"error": "INVALID_ADDRESS", "error_data": [{"address": "0x00", "error": "ADDRESS_RESERVED"}]}), 
                               (res, msg))

    def test_i3c_ccc_broadcast_setxtime(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        self.i3c.init_bus(3300)

        (success, response) = self.i3c.ccc_broadcast_setxtime(0xDF)
        self.assertTupleEqual((True, None), (success, response))

        (success, response) = self.i3c.ccc_getxtime(0x08)
        self.assertEqual(success, True, "Could not getxtime for validation")

        self.assertEqual(response["stateByte"], 2, "xtime state does not match set")

        (success, response) = self.i3c.ccc_broadcast_setxtime(0xFF, [0xAA, 0xBB])
        self.assertTupleEqual((True, None), (success, response))

        (success, response) = self.i3c.ccc_getxtime(0x08)
        self.assertEqual(success, True, "Could not getxtime for validation")

        self.assertEqual(response["stateByte"], 0, "xtime state does not match reset")

    def test_i3c_ccc_getxtime(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        self.i3c.init_bus(3300)
        (deviceFound, bmi323) = self.i3c.find_target_device_by_pid(BMI323_DATA["asString"])
        if not deviceFound:
            self.skipTest("For BMI323")

        def expected_getxtime_result(expected_state):
            return {
                    "supportedModesByte": 3,
                    "stateByte": expected_state,
                    "frequency": 6.5,
                    "inaccuracy": 12
            }

        (success, response) = self.i3c.ccc_broadcast_setxtime(0xDF)
        self.assertEqual(True, success)

        (success, response) = self.i3c.ccc_getxtime(bmi323["dynamic_address"])
        self.assertTupleEqual((success, response), (True, expected_getxtime_result(2)), "got unexpected xtime")


        (success, response) = self.i3c.ccc_broadcast_setxtime(0xFF, [0xAA, 0xBB])
        self.assertEqual(True, success)

        (success, response) = self.i3c.ccc_getxtime(bmi323["dynamic_address"])
        self.assertTupleEqual((success, response), (True, expected_getxtime_result(0)), "got unexpected xtime")

        self.assertEqual(response["stateByte"], 0, "xtime state does not match reset")

    def test_i3c_ccc_get_set_mrl_mwl(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.i3c.init_bus(3300)

        (success, _) = self.i3c.ccc_broadcast_setmwl(0x0A)
        self.assertEqual(True, success)
        (success, _) = self.i3c.ccc_broadcast_setmrl(0x0B)
        self.assertEqual(True, success)

        result = self.i3c.ccc_getmwl(0x08)
        self.assertTupleEqual((True, 10), result)
        result = self.i3c.ccc_getmrl(0x08)
        self.assertTupleEqual((True, 11), result)

        (success, _) = self.i3c.ccc_unicast_setmwl(0x08, 0x0C)
        self.assertEqual(True, success)
        (success, _) = self.i3c.ccc_unicast_setmrl(0x08, 0x0D)
        self.assertEqual(True, success)

        result = self.i3c.ccc_getmwl(0x08)
        self.assertTupleEqual((True, 12), result)
        result = self.i3c.ccc_getmrl(0x08)
        self.assertTupleEqual((True, 13), result)

if __name__ == "__main__":
    unittest.main()