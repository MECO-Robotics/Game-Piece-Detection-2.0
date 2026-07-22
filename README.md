# FRC 8324 A075 Game Piece Vision

This project bridges one or two Sipeed MaixSense A075 RGBD cameras into PhotonVision on an Ubuntu 24.04 Beelink Mini S12. The cameras become stable Video4Linux devices (`/dev/video20` and, when present, `/dev/video21`) that can be activated and viewed in the PhotonVision UI.

The bridge also marks likely 2026 FUEL (yellow balls) in magenta so detections are visible in Driver Mode. PhotonVision can independently produce robot targeting data from the same feed with a Colored Shape pipeline.

## Why a bridge is required

The A075 is a USB RNDIS network device, not a UVC webcam. It serves RGBD frames over HTTP at `192.168.233.1`. Both cameras use that same fixed address, so this project places each USB interface in a separate Linux network namespace before publishing the RGB image through `v4l2loopback`. The installer also creates stable `/dev/v4l/by-path/frc8324-a075-*` links so PhotonVision enumerates the virtual feeds.

PhotonVision does not officially support virtual cameras. This bridge supplies a conventional, fixed-format V4L2 capture stream and is intended for this specific x86/RNDIS setup, but it must be tested on the final robot hardware before competition.

## Install on the Beelink

Requirements:

- Ubuntu 24.04
- PhotonVision already installed and working
- One or two A075 cameras connected directly or through a powered USB hub
- Internet access for the first installation

Clone the repository and run:

```bash
git clone https://github.com/MECO-Robotics/Game-Piece-Detection-2.0.git
cd Game-Piece-Detection-2.0
sudo ./scripts/install.sh
```

The installer automatically selects one or two USB network interfaces using the `rndis_host`, `cdc_ether`, or `cdc_ncm` driver. With one camera, it installs only `FRC8324-A075-Left` on `/dev/video20`. If other USB network adapters are connected, specify the interface explicitly:

```bash
sudo A075_LEFT_IFACE=enx001122334455 ./scripts/install.sh
```

For two cameras, set both interfaces:

```bash
sudo A075_LEFT_IFACE=enx001122334455 A075_RIGHT_IFACE=enx66778899aabb ./scripts/install.sh
```

After installation, power-cycle the connected cameras or reboot the Beelink. Check a one-camera bridge with:

```bash
sudo systemctl status a075-bridge@left
v4l2-ctl --list-devices
```

For two cameras, also check `a075-bridge@right`. Restart PhotonVision after the bridge services are running. Open `http://photonvision.local:5800`, activate the available `FRC8324-A075` cameras, and rename them `fuel-left` and `fuel-right` as applicable.

## PhotonVision yellow-ball pipeline

For each camera, create a **Colored Shape** pipeline named `fuel-yellow` and start with:

| Setting | Initial value |
| --- | --- |
| Hue | 4–42 |
| Saturation | 45–255 |
| Value | 55–255 |
| Contour shape | Circle |
| Area | 0.05–35% |
| Fullness | 55–100% |
| Aspect ratio | 0.65–1.45 |
| Sort mode | Largest |
| Maximum targets | 8 |

Tune HSV values under actual field lighting. The bridge additionally checks Lab yellow chroma and yellow dominance (`min(red, green) - blue`) so automatic exposure changes do not cause the ball to disappear against warm walls or skin. These thresholds are configured with `LAB_YELLOW_LOW` and `YELLOW_DOMINANCE_LOW` in `bridge.conf`. Camera exposure cannot be controlled through PhotonVision because the A075 HTTP API does not expose it as a V4L2 control.

The magenta boxes and labels are produced by the bridge for driver feedback. PhotonVision thresholds only the yellow ball pixels, so the overlay does not become a target.

## Configuration and operations

Installed configuration lives in `/etc/frc8324-a075/`:

- `left.conf` and optional `right.conf`: source interface, namespace, and virtual video device
- `bridge.conf`: resolution, frame rate, HSV thresholds, and contour filters

Apply configuration changes with:

```bash
sudo systemctl restart a075-bridge@left
```

Include `a075-bridge@right` when two cameras are installed. Rerun the installer after connecting a second camera to expand an existing one-camera installation.

Follow logs with:

```bash
journalctl -u 'a075-bridge@*' -f
```

The services automatically retry while a camera is booting or temporarily disconnected. The A075 normally takes 10–15 seconds to become ready.

## Development

Run the unit tests without camera hardware:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
