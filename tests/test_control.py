import unittest

from a075_bridge.control import ControlSettings, plan_drive
from a075_bridge.targeting import SCHEMA_VERSION, DetectionFrame, TargetObservation


def frame(*targets: TargetObservation, connected: bool = True) -> DetectionFrame:
    return DetectionFrame(SCHEMA_VERSION, "left", connected, 7, 1.0, targets)


def target(center_x: float = 0.0, area: float = 0.01) -> TargetObservation:
    return TargetObservation(center_x, 0.0, 0.1, 0.1, area, 0.0)


class ControlTests(unittest.TestCase):
    def test_inactive_without_target(self):
        intent = plan_drive(frame(), ControlSettings())

        self.assertFalse(intent.active)
        self.assertEqual(0.0, intent.forward)
        self.assertEqual(0.0, intent.turn)

    def test_inactive_when_camera_is_disconnected(self):
        intent = plan_drive(frame(target(), connected=False), ControlSettings())

        self.assertFalse(intent.active)

    def test_inactive_when_control_is_disabled(self):
        intent = plan_drive(
            frame(target()), ControlSettings(enabled=False)
        )

        self.assertFalse(intent.active)

    def test_approaches_centered_target(self):
        intent = plan_drive(frame(target()), ControlSettings())

        self.assertTrue(intent.active)
        self.assertEqual(0.55, intent.forward)
        self.assertEqual(0.0, intent.turn)

    def test_turns_without_forward_motion_for_off_center_target(self):
        intent = plan_drive(frame(target(center_x=0.8)), ControlSettings())

        self.assertTrue(intent.active)
        self.assertEqual(0.0, intent.forward)
        self.assertEqual(0.65, intent.turn)

    def test_stops_at_goal(self):
        intent = plan_drive(frame(target(area=0.08)), ControlSettings())

        self.assertTrue(intent.active)
        self.assertTrue(intent.at_goal)
        self.assertEqual(0.0, intent.forward)

    def test_signs_allow_per_robot_direction_changes(self):
        intent = plan_drive(
            frame(target(center_x=0.2)),
            ControlSettings(forward_sign=-1, turn_sign=-1),
        )

        self.assertLess(intent.forward, 0)
        self.assertLess(intent.turn, 0)


if __name__ == "__main__":
    unittest.main()
