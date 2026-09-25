import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

_state_dir = tempfile.TemporaryDirectory()
os.environ['XDG_STATE_HOME'] = _state_dir.name

from app import create_app
from app.controller import UxPlayController


def output(transform='normal', name='HDMI-A-1', enabled='yes'):
    return f'{name} "Monitor"\n  Enabled: {enabled}\n  Transform: {transform}\n'


class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.controller = UxPlayController()
        self.config_patch = patch('app.config.DISPLAY_OUTPUT', '')
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def test_all_rotations_and_verification(self):
        for mode, transform in [('landscape', 'normal'), ('portrait-right', '90'),
                                ('portrait-left', '270'), ('landscape-flipped', '180')]:
            with self.subTest(mode=mode), patch.object(
                self.controller, '_display_command',
                side_effect=[output('flipped'), '', output(transform)],
            ) as command:
                result = self.controller.set_display_mode(mode)
                self.assertTrue(result['changed'])
                self.assertEqual(result['mode'], mode)
                self.assertEqual(command.call_args_list[1].args,
                                 ('--output', 'HDMI-A-1', '--transform', transform))

    def test_same_mode_is_noop(self):
        with patch.object(self.controller, '_display_command', return_value=output()) as command:
            self.assertFalse(self.controller.set_display_mode('landscape')['changed'])
            command.assert_called_once_with()

    def test_multiple_displays_require_selection(self):
        with patch.object(self.controller, '_display_command',
                          return_value=output() + output(name='HDMI-A-2')):
            with self.assertRaisesRegex(RuntimeError, 'Multiple displays'):
                self.controller.display_status()
            with patch('app.config.DISPLAY_OUTPUT', 'HDMI-A-2'):
                self.assertEqual(self.controller.display_status()['output'], 'HDMI-A-2')

    def test_disabled_display_rejected(self):
        with patch.object(self.controller, '_display_command', return_value=output(enabled='no')):
            with self.assertRaisesRegex(RuntimeError, 'No enabled display'):
                self.controller.display_status()

    def test_unsuccessful_transform_detected(self):
        with patch.object(self.controller, '_display_command', return_value=output()):
            with self.assertRaisesRegex(RuntimeError, 'did not apply'):
                self.controller.set_display_mode('portrait-right')

    def test_command_failures(self):
        failures = [FileNotFoundError(), subprocess.TimeoutExpired('wlr-randr', 5),
                    subprocess.CalledProcessError(1, 'wlr-randr', stderr='Failed'),
                    PermissionError('Denied')]
        with patch('pathlib.Path.is_socket', return_value=True):
            for failure in failures:
                with self.subTest(failure=failure), patch('subprocess.run', side_effect=failure):
                    with self.assertRaises(RuntimeError):
                        self.controller.display_status()

    def test_api_validation_and_errors(self):
        app = create_app()
        app.extensions['uxplay_controller'] = self.controller
        client = app.test_client()
        for payload in [{}, {'mode': 'bad'}, {'mode': []}, [], 'portrait', None]:
            with self.subTest(payload=payload):
                self.assertEqual(client.put('/api/display', json=payload).status_code, 400)
        with patch.object(self.controller, '_display_command', return_value=output()):
            self.assertEqual(client.get('/api/display').json['mode'], 'landscape')
            self.assertFalse(client.put('/api/display', json={'mode': 'landscape'}).json['changed'])
        with patch.object(self.controller, '_display_command', side_effect=RuntimeError('Offline')):
            self.assertEqual(client.get('/api/display').status_code, 503)
            self.assertEqual(client.put('/api/display', json={'mode': 'portrait-right'}).status_code, 503)


if __name__ == '__main__':
    unittest.main()
