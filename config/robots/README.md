# Per-robot pursuit profiles

Copy `default.conf` to `<robot-name>.conf` and tune that file for one robot.

Install or switch a Beelink to the profile with:

```bash
sudo A075_CONTROL_PROFILE=<robot-name> ./scripts/install.sh
```

Supplying `A075_CONTROL_PROFILE` intentionally replaces `/etc/frc8324-a075/control.conf`. Running the installer without
that variable preserves the installed profile and any pit tuning.

Physical speed limits and drivetrain hardware mappings remain in each robot's adapter. These profiles only tune the
normalized pursuit planner.
