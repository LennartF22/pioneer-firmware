# Pioneer AVH/AVIC Firmware Tools

This repository contains tools for building clean firmware images for SD cards
in Pioneer AVH and AVIC head units from a firmware update package. Replacing
the SD card in such a head unit is usually required when it shows a "software
error" screen or is bootlooping.

To avoid violating any copyrights, this repository **does not** and
**will not** provide pre-built firmware images. Instead, you will need to
acquire one of the publicly available firmware update packages to build
firmware images yourself.

## Supported Models

For each generation, there are multiple models for different regions of the
world, based on the same hardware platform. All models of the same generation
seem to share the same firmware, which detects the specific model it runs on
by reading some information from the internal NOR flash. Therefore, a firmware
update for the AVH-Z9200DAB (and the resulting firmware image) can also be
used for an AVH-W4500NEX, for example, since they are from the same
generation.

### 2018 AVH Generation (AVH18)

Firmware update downloads:

- [Version 1.08](https://pioneer03.s3.amazonaws.com/firmware/AVH-Z9100BT_DAB_FW_Ver_108.zip)
  (Pioneer CDN)

Models:

- AVH-W4400NEX/XNUC
- AVH-Z9100DAB/XNEU5
- AVH-Z9100BT/XNUR
- AVH-Z9150BT/XNRC
- AVH-Z9150BT/XNRI
- AVH-Z9150BT/XNRD
- AVH-Z9190BT/XNID
- AVH-Z9180TV/XNBR

### 2019 AVH Generation (AVH19)

Firmware update downloads:

- [Version 1.07](https://pioneer03.s3.amazonaws.com/firmware/AVH-Z9200BT_DAB_FW_Ver_107.zip)
  (Pioneer CDN)

Models:

- AVH-W4500NEX/XNUC
- AVH-Z9200DAB/XNEU5
- AVH-Z9200BT/XNUR
- AVH-Z9250BT/XNRC
- AVH-Z9250BT/XNRI
- AVH-Z9250BT/XNRD
- AVH-Z9290BT/XNID
- AVH-Z9280TV/XNBR

### 2018 AVIC Generation (AVIC18)

**Note:** AVIC models are currently not fully supported. Critical AVIC-related
components will be missing from the firmware image.

Firmware update downloads:

- [Version 1.06](https://pioneer03.s3.amazonaws.com/firmware/AVIC-Zx10BT_DAB_EU5_FW_VER106.ZIP)
  (Pioneer CDN)

Models:

- AVIC-W8400NEX/XNUC
- AVIC-Z910DAB/XNEU5
- AVIC-Z910DAB/XNAU
- AVIC-Z810DAB/XNEU5
- AVIC-W6400NEX/XNUC
- AVIC-Z710DAB/XNEU5
- AVIC-Z710DAB/XNAU
- AVIC-Z610BT/XNEU5

### 2019 AVIC Generation (AVIC19)

**Note:** AVIC models are currently not fully supported. Critical AVIC-related
components will be missing from the firmware image.

Firmware update downloads:

- [Version 1.07](https://pioneer03.s3.amazonaws.com/firmware/AVIC-Zx20BT_DAB_EU5_FW_VER107.ZIP)
  (Pioneer CDN)

Models:

- AVIC-W8500NEX/XNUC
- AVIC-Z920DAB/XNEU5
- AVIC-Z920DAB/XNAU
- AVIC-Z820DAB/XNEU5
- AVIC-W6500NEX/XNUC
- AVIC-Z720DAB/XNEU5
- AVIC-Z720DAB/XNAU
- AVIC-Z620BT/XNEU5

## Usage

### Requirements

Since this tool is based on Docker, Docker is the only requirement.

### Preparation

Download a firmware update package for the target generation (see "Supported
Models" section), rename it to `AVH18.zip` or `AVH19.zip` and place it in the
`data/` folder.

### Building

Depending on the target generation, run `build-AVH18.sh` or `build-AVH19.sh`.
This first builds the Docker image and then runs it to build the image. If you
are on Windows, you will need to look at what the scripts do and build/run the
image manually (or use WSL).

After the building process finishes with the message `OK`, the built firmware
image will be available as `AVH18.img` or `AVH19.img` in the `data/` folder.

### Final Steps

Use your utility of choice (`dd`, balenaEtcher, ...) to flash the firmware
image to an **8GB** SD card.

Bigger SD cards (at least up to 32GB) generally also work, but firmware
updates seem to get stuck when the installed SD card is more than 8GB big.
See below for notes on recovering from this situation.

Finally, install the new SD card into the internal SD card slot of the head
unit, and enjoy the (hopefully) restored head unit.

Note that at every boot attempt, the head unit will add password protection
to the SD card via `CMD42`, if it is not already protected. This means that it
cannot easily be used again using a standard operating system, so make sure
the new SD card is correctly flashed with the correct image before attempting
to boot the head unit.

## Miscellaneous

### General Architecture

The 2018 and 2019 models are based on an i.MX 6 SoC and run Android (and
therefore Linux).

"Warp!!" by Lineo is used to speed up the boot time of the head unit, which
would otherwise be rather long. It works by loading a partially booted
snapshot of the system, which was captured during a regular boot by Pioneer,
into RAM, so that the system does not need to boot "from scratch".

A modified U-Boot build, installed on the internal NOR flash, is used as the
bootloader. It reads some settings from a configuration area ("BSP") in the
flash, which can partially be modified via the debug menu.

Since Pioneer relies on open source software, where licenses usually require
source code to be made available, buyers can request source code for parts
of their products (like U-Boot) via their open source code distribution
service.

### SD Card Protection

Pioneer uses `CMD42` (see SD specification) to add password protection to the
internal firmware SD card. This means that the SD card cannot simply be
accessed from standard operating systems. In fact, it usually will not even be
detected.

By using special tooling or a modified Linux kernel, one can unlock the SD
and remove the password protection. In case there is demand, I may add further
information on this in the future.

Pioneer uses the following passwords:

- 2018 and earlier models: `LKPFeD4BcVzESR2Y`
- 2019 and possibly later models: `gJ6NK7hSQWKs5Age`

### Stuck Firmware Updates

When the SD card is bigger than 8GB or broken/corrupted in some way already,
initiating a firmware update can cause the head unit to get stuck in a loop
of (unsuccessfully) attempting to perform the firmware update.

From experience, it is usually possible to recover from this situation by
replacing the SD card with an intact, high-quality **8GB** one that ideally
has been freshly flashed.

As a last resort, it is also possible to clear the firmware update flag in the
BSP on the internal NOR flash. This is the definitive way of getting the head
unit unstuck, but this requires special tooling and advanced soldering skills.

### Debug Menu

**Warning:** Before enabling the debug menu, beware that some options in there
can brick the device in a way that it can only be recovered by restoring the
internal NOR flash via JTAG. Specifically, **do not** select "CATCH_SNAPSHOT"
in the "Set Boot SubMode" menu.

1. Insert a USB drive with a file named `GeAdCKPdjrDgolniDearueeuogdorDys`
   into any of the two USB ports.

2. Switch the audio source to "Source OFF".

3. Touch and hold the middle of the screen for some seconds until a pop-up
   saying that the debug menu has been activated appears.

4. Remove the USB drive.

5. Touch and hold the middle of the screen again until the debug menu opens.

The same procedure can be used to deactivate the debug menu again.

There is also a second (less interesting) debug menu, which can be activated
using the same procedure but with a file named
`KamiokarodeBallonyakitoricerveja`.

Credits for the information in this section go to user "asd255" from the
4pda.to forum.

### ADB

ADB can be enabled in the debug menu via the option "ADB On USB". It will
subsequently be available on USB port 1. If you have issues connecting to it,
try rebooting the head unit while already having the USB cable connected.

### Root Shell

The `root-shell/` folder contains a small assembly program for the 32-bit ARM
architecture of the i.MX 6, which is used in the 2018 and 2019 models. It uses
the `setuid`, `setgid` and `execve` Linux syscalls for launching the
`/system/bin/sh` shell with root privileges as a normal user, for example via
the ADB shell.

To successfully run the program, the compiled version (see Makefile) must be
placed somewhere where the unprivileged user can access it and where the
corresponding mount does neither have the `noexec` nor `nosuid` flag set.

A suitable candidate for this is the `bin/` folder of the system partition of
the firmware image (partition 7). After placing the binary there, the
permissions need to be adjusted as follows:

```sh
chown 0:2000 bin/root-shell
chmod 6754 bin/root-shell
```

However, beware that modifying the system partition is always a bit hacky
when "Warp!!" boot is enabled, because we are externally modifying a
filesystem that effectively is already mounted in the "Warp!!" snapshot,
which could lead to weird stability issues.

Instead, one would ideally perform the following steps to permanently install
the root shell:

1. Disable "Warp!!" boot via the debug menu and remove the SD card from the
   head unit.

2. Add the root shell to the system partition by mounting the partition on a
   computer after unlocking the SD card (or by using a newly flashed one) and
   boot the head unit up again. Booting should take considerably longer now
   due to the disabled "Warp!!" boot.

3. Invoke the root shell via the ADB shell with `/system/bin/root-shell` and
   copy the root shell binary to the `/mnt/backup_flash/` folder, which
   corresponds to `/dev/block/mtdblock1` (internal NOR flash) and is
   independent from the SD card. Remember to adjust the permissions again as
   described above!

4. Restore the original state of the system partition. Since the system
   partition is mounted read-only and there are only minor differences
   compared to the original data, it should be possible to do this by plugging
   a USB drive with the original system partition into the head unit and using
   `dd` via the root shell. Alternatively, unlock and reflash the SD card or -
   if unable to unlock the SD card - use the previously used SD card.

5. Enable "Warp!!" boot again and reboot the head unit. The root shell can
   now be invoked via `/mnt/backup_flash/root-shell`.

### Internal NOR Flash Backup

The internal NOR flash can be backed up by inserting a FAT32-formatted USB
drive into USB port 2 and running the following commands in a root shell:

```sh
dd if=/dev/block/mtdblock0 of=/udisk1/mtdblock0.img
dd if=/dev/block/mtdblock1 of=/udisk1/mtdblock1.img
dd if=/dev/block/mtdblock2 of=/udisk1/mtdblock2.img
sync
```

Only ever write to the internal NOR flash when you know exactly what you are
doing, as this can easily brick the head unit in a way that it can only be
recovered by restoring the original contents via JTAG.

### Serial Interface

A serial interface should be available on the yellow RGB input connector. It
runs at 3.3V and 115200 baud. The RX signal is on pin 17 (bottom row) and the
TX signal is on pin 16 (top row). On the booted system, the serial interface
is available under `/dev/ttymxc0`.

Unfortunately, at least on 2019 models, it only provides some limited output
from U-Boot and does not accept input. However, there are some related options
in the debug menu to somewhat change this behavior.
