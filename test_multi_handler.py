"""CPU-only checks for request routing and media validation."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest


class HandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_comfy = types.ModuleType("handler")
        fake_comfy.handler = lambda job: {"received": job["input"]}
        fake_runpod = types.ModuleType("runpod")
        sys.modules["handler"] = fake_comfy
        sys.modules["runpod"] = fake_runpod
        spec = importlib.util.spec_from_file_location(
            "multi_handler_under_test", Path(__file__).with_name("multi_handler.py")
        )
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("handler", None)
        sys.modules.pop("runpod", None)

    def test_flux_delegates_original_workflow_and_images(self):
        payload = {"mode": "flux", "workflow": {"104": {"class_type": "SaveImage"}}, "images": []}
        result = self.module.route({"id": "test", "input": payload})
        self.assertEqual(result["received"], {"workflow": payload["workflow"], "images": []})

    def test_media_and_mode_validation(self):
        self.assertEqual(self.module.decode_media("iVBORw0KGgo=", "image")[1], ".png")
        self.assertEqual(self.module.route({"input": {"mode": "unknown"}})["error"], "invalid_mode")
        self.assertEqual(self.module.route({"input": {"mode": "facefusion_video"}})["error"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
