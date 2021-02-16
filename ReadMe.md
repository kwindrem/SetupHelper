This package manages Victrion VenusOs VeCan (aka CANbus) ports

The setup script's actions are:

    Add - add (or modify) a port's configuraiton
        Configuration simply requires selecting one of the supported interfaces:
            CANable (both slcand and candelight firmware)
            Canberry Hat
            PCAN-USB (which is also the Victron's CANUSB)
            PiCan Hat
            Lawicel CANUSB and other SLCAN USB
            VScom USB-CAN+
            Waveshare Hat
    Remove a port's configuration
    Install the configured ports into the Venus file system
    Uninstall/restore all Venus files installed by this package
    leaving the system in a stock configuraiton

The script also hooks into SetupHelper's boot-time reinstall mechanism which reinstalls Venus file system modifications after they are overwritten by a Venus OS update

Two VeCan ports are defined for these systems: can0 and can1, although support for more could easily be added


Setting up a VeCan interface is a two-step process:
    select a port and choose an interface, or remove the configuration
    install the changes

Separate steps allow for review before changes are committed to the running system

While multiple interfaces are possible, some manual configuraiton may be required.
For example, CANable with Candelight software supports multiple interfaces however
adding a serial number to the udev rules is necessary and is currently not part of this package.

Installing the same interface type for both can0 and can1 gets you part way.

It is then necessary to determine the serial number of each interface.
Connect one interface at a time then search dmesg for that interface and note the serial number.
Manually edit the udev rule for that interface in instert the serial number
Repeat for the other interface.

Using a different interface type for each CANbus should work OK

Note: I have only tested this package with CANable. CANbus hats that support two interfaces are at the most risk of working properly. The configurations for other interfaces was taken from

https://github.com/victronenergy/venus/wiki/RaspberryPi-CAN-Interfaces

and for USB interfaces, with my own exeperiences with CANable.


Setup:

Copy the entire repo from GitHub as a zip file to /data on the Venus device
then unzip it. This should populate /data/VeCanSetup with the package contents.

You must also install SetupHelper from here:

https://github.com/kwindrem/Victron-VeusOs-Setup-Helper

Once both packages are installed run setup and follow the prompts.
./setup

You will need root access to the Venus device. Instructions can be found here:
https://www.victronenergy.com/live/ccgx:root_access
The root password needs to be reentered following a Venus update.
Setting up an authorization key (see documentation referenced above) will save time and avoid having to reset the root password after each update.

