import io
import json
import subprocess
import sys
import threading
from unittest.mock import Mock, patch
from urllib.error import URLError

from django.test import SimpleTestCase

from cloud_worker import supervise, wait_until_ready


class Response(io.BytesIO):
    status = 200


class CloudWorkerTests(SimpleTestCase):
    def test_readiness_accepts_healthy_https_application(self):
        with patch("cloud_worker.urlopen", return_value=Response(json.dumps({"status": "ok"}).encode())) as transport:
            self.assertTrue(wait_until_ready("https://app.example.test", threading.Event()))
        self.assertEqual(transport.call_args.args[0], "https://app.example.test/api/ready/")

    def test_insecure_url_is_rejected(self):
        with self.assertRaises(RuntimeError):
            wait_until_ready("http://app.example.test", threading.Event())

    def test_stop_request_does_not_start_wait_or_services(self):
        stopping = threading.Event()
        stopping.set()
        with patch("cloud_worker.urlopen") as transport, patch("cloud_worker.subprocess.Popen") as spawn:
            self.assertFalse(wait_until_ready("https://app.example.test", stopping))
            supervise([["unused"]], stopping)
        transport.assert_not_called()
        spawn.assert_not_called()

    def test_readiness_timeout_does_not_expose_transport_error(self):
        with patch("cloud_worker.urlopen", side_effect=URLError("private URL")), patch("cloud_worker.time.monotonic", side_effect=[0, 0, 10]):
            with self.assertRaises(RuntimeError) as caught:
                wait_until_ready("https://app.example.test", Mock(is_set=Mock(return_value=False)), timeout=1)
        self.assertNotIn("private URL", str(caught.exception))

    def test_child_failure_cleans_up_other_real_child(self):
        children = []
        real_spawn = subprocess.Popen
        def spawn(*args, **kwargs):
            process = real_spawn(*args, **kwargs)
            children.append(process)
            return process
        with patch("cloud_worker.subprocess.Popen", side_effect=spawn):
            with self.assertRaises(RuntimeError):
                supervise([[sys.executable, "-c", "raise SystemExit(1)"], [sys.executable, "-c", "import time; time.sleep(60)"]], threading.Event())
        self.assertEqual(len(children), 2)
        self.assertTrue(all(child.poll() is not None for child in children))

    def test_stop_cleans_up_running_child(self):
        stopping = threading.Event()
        children = []
        real_spawn = subprocess.Popen
        def spawn(*args, **kwargs):
            process = real_spawn(*args, **kwargs)
            children.append(process)
            stopping.set()
            return process
        with patch("cloud_worker.subprocess.Popen", side_effect=spawn):
            supervise([[sys.executable, "-c", "import time; time.sleep(60)"]], stopping)
        self.assertTrue(all(child.poll() is not None for child in children))
