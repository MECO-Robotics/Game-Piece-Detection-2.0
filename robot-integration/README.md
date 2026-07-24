# Reusable robot integration

The Beelink publishes normalized chassis intent, while each robot owns its hardware mapping and every authority that
can permit or stop motion.

The Java implementation under `java/src/main/java` depends only on WPILib 2026. It deliberately has no CTRE, REV,
swerve, or differential-drive dependency.

## Safety model

`GamePieceVisionClient.getRequest()` returns an inactive zero request unless all of these are true:

- Driver Station reports the robot enabled;
- the driver-held assist/dead-man control is pressed;
- manual override is not requested;
- the camera and publisher report connected;
- schema version 1 is present;
- the drive request is active;
- the request is no older than 250 milliseconds.

`GamePieceDriveCommands.driverHeldPursuit()` requires the robot's drivetrain subsystem and invokes the supplied stop
function when interrupted. Releasing the assist control or moving a manual-drive stick past the robot's chosen
threshold ends the command, allowing the normal drivetrain default command to resume.

## Add it to a Java robot project

Copy the `org/mecorobotics/gamepiecevision` directory into the robot project's Java source tree. Construct one client
for the camera the robot should follow:

```java
private final GamePieceVisionClient gamePieceVision =
    new GamePieceVisionClient("left");
```

The robot supplies an adapter through `applyRequest`. For a holonomic drivetrain, map all three normalized axes:

```java
request -> drivetrain.driveRobotRelative(
    request.forward() * MAX_LINEAR_METERS_PER_SECOND,
    request.strafe() * MAX_LINEAR_METERS_PER_SECOND,
    request.turn() * MAX_ANGULAR_RADIANS_PER_SECOND)
```

For differential/tank drive, ignore strafe:

```java
request -> drivetrain.arcadeDrive(
    request.forward() * MAX_FORWARD_OUTPUT,
    request.turn() * MAX_TURN_OUTPUT)
```

Bind the command with a dead-man control and a manual-stick override. The exact drivetrain calls remain in the robot
repository because only that project knows its motor controllers and units:

```java
BooleanSupplier assistHeld = () -> driver.getRightTriggerAxis() > 0.5;
BooleanSupplier manualOverride =
    () -> Math.abs(driver.getLeftY()) > 0.15
        || Math.abs(driver.getLeftX()) > 0.15
        || Math.abs(driver.getRightX()) > 0.15;

driverController.rightTrigger().whileTrue(
    GamePieceDriveCommands.driverHeldPursuit(
        drivetrain,
        gamePieceVision,
        assistHeld,
        manualOverride,
        request -> applyToThisRobotsDrivetrain(request),
        drivetrain::stop));
```

Never schedule the pursuit command without a local enable/dead-man condition. NetworkTables is guidance data, not a
motor-safety system.

## Supporting another robot

For each robot:

1. choose `left` or `right`;
2. map normalized forward/strafe/turn to that drivetrain;
3. choose conservative maximum linear and angular speeds;
4. define the assist-held and manual-override inputs;
5. tune `/etc/frc8324-a075/control.conf` on that robot's Beelink;
6. test camera loss, network loss, Driver Station disable, release, and manual override before driving on the floor.

The pursuit planner does not need to change between swerve and tank robots. Only the small hardware adapter and the
per-robot configuration do.
