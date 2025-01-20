# Overview

The SetupHelper package provides:
  - a mechanism to automatically reinstall packages following a Venus OS update
  - an automatic update mechanism to keep packages up to date from GitHub archives or USB stick
	- control of the automatic download and install from the GUI
	- add and remove packages from the system
	- manual download, install, uninstall from the GUI
	- checks for package conflicts and prevents one package installing over another when the same files are modified
	- provides a "conflict resolution" option when such conflicts exist

  - a "blind" install of SetupHelper from SD/USB media

  - a blind uninstall mechanism which optionally includes reinstalling Venus OS

  - backup and restore SOME settings from `com.victronenergy.settings`
	
	This includes custom logos and copying logs to removable media
	- SetupHelper
	- PackageManager
	- gui

  - Restart or initialize PackageManager
  - Restart the GUI

> [!NOTE]
> Support for firmware prior to v3.10 has been dropped starting with SetupHelper v8.10
> if you are running older versions, change the branch/tag to preV3.10support
> for any packages you wish to run on that firmware
>
> While this branch will remain active, there will be no features added to it
> and only serious bug fixes will be applied.

# Changes

**SetupHelper v8**
  - adds the ability for multiple packages to modify the same file
  
	  - Packages must be written to "patch" a file rather than "replace" it

**SetupHelper v7.0**
- adds a conflict resolution mechanism.
  
  - Packages can identify known conflicts with other packages with a "packageDependencies" list
  - One package can specify that other packages must be uninstalled or installed
	before allowing the package to be installed
  - PackageManager also checks all files that will be modified to see if another package has already modified the same file.
    
    > [!NOTE] 
    > All packages should be uninstalled, then reinstalled to create the necessary
    > information for these file-based conflicts to be identified.
    
    If a conflict exists it is reported on in the PackageManager menus and install is blocked. These conflicts can be resolved from within the Package editor menu.

**SetupHelper v6.0**

> [!NOTE]
> SetupHelper v6.0 changes significantly from prevous versions

- providing more automatic installation and installation of files, services and dBus Settings
	- v6.0 will install older packages but package setup scripts that utilize the new
	automated install and uninstall functions **will not work with SetupHelper v5.x**
	
	  For this reason, packages that rely on the v6.0 setup helper functionality
	should also include a copy of the **HelperResources** found in SetupHelper v6.0 and newer
	
	  Sourcing these helpers has also changed in v6.0. But there is also a backward
	compatible hook for older packages.
	
	  The new sourcing mechanism can be found in the file `SetupHelper/HelperResources/forSetupScript`.

# Helper resources

Other packages use "helper resources" provided by SetupHelper

Helper Resources simplify the package's setup script and include hooks that PackageManager uses to control installs and uninstalls.

More information about Setup Helper and how to create packages that use it can be found in the file PackageDevelopmentGuidelines.md in the package directory.

# Blind Install:

By far, the easiest way to install SetupHelper is the "blind install" which requires no command-line interaction.

1. Download `venus-data.tgz` from the SetupHelper GitHub [repo](https://github.com/kwindrem/SetupHelper/raw/main/venus-data.tgz).
> [!NOTE]
> Mac OS and Safari are set by default to unzip packages.
> The Open "safe" files after downloading (bottom of Safari Preferences General)
> must be disabled in order to retain the zip file. 

2. copy it to the root of a freshly formatted SD card or USB memory stick
3. place the media in the GX device (Cerbo, CCGX, etc)
4. reboot the GX device and allow the system to display the GUI

   - if you are running Venus OS v2.90 and beyond:
        - you should find the Package Manager menu at the bottom of the Settings menu
        - you should remove the media at this point
            
          Mechanisms are in place to prevent reinstallation, but removal is still a good idea!

*If you are running Venus OS **prior to v2.90**, perform these additional steps:*

5. reboot the GX device a second time
6. WHILE the GX device is booting, **REMOVE THE MEDIA** from the GX device *to prevent the next reboot from starting the process all over again.* Failure to do so could disable reinstalls following a Venus OS firmware update !!!

You should find the Package Manager menu at the bottom of the Settings menu

> [!CAUTION]
> Prior to v2.90, this mechanism overwrites /data/rcS.local !!!!
> If you are using rcS.local to perform boot-time activities,
> /data/rcS.local must be recreated following this "blind" install
> 
> Note that SetupHelper also uses /data/rcS.local for
> reinstallation following a firmware update so use caution in
> recreating rcS.local.
        

Another way to install SetupHelper is to use the following from the command line of the GX device:

```bash
wget -qO - https://github.com/kwindrem/SetupHelper/archive/latest.tar.gz | tar -xzf - -C /data
mv -f /data/SetupHelper-latest /data/SetupHelper
/data/SetupHelper/setup
```

Once SetupHelper is installed, updates to it and other packages can be performed through the GUI using the PackageManager menus.

> [!CAUTION]
>  Package Manager allows uninstalling SetupHelper.
>
>  This can not be undone since the menus to control Package Manager will go away.
	You would need to use the Blind Install or run /data/SetupHelper/setup again to reinstall SetupHelper
>	
> Note that removal does not actually remove the package so other setup scripts
> will continue to function.

> [!NOTE]
> You can install other packages using wget as described above.
> Or you can download the .tgz file and put that on a USB stick and plug that into the GX device.
> 
> PackageManager will detect the file and install the package.
		

# ssh access:

Setting up ssh access with ssh keys is highly recommended for any system,
but especially when installing third party extensions to Venus OS.
Attaching a serial terminal for direct console access is another option,
especially if you don't have a network setup.

[This document](https://www.victronenergy.com/live/ccgx:root_access) describes ssh access and also serial terminal connections on Cerbo GX. 

Remote ssh access is now available via tailscale using the **TailscaleGX** package

# System Recovery:

It is unlikely, but some users have reported a package install leaving their system unresponsive or with a nonfunctional GUI (white screen). In this case, your options depend on the current state of the system.

1. (as always) reboot. This may clear the problem.

2. if you have a functioning GUI (either locally or via remote console, see if you can access the PackageManager menu.
    - If so, you can remove pacakges one at a time from there.
    - If you find an offeding package, post an issue to the GitHub repo for that package and include:
	    - Platform (Cerbo, CCGX, Raspberry PI, etc)
	    - Venus OS firmware version
	    - Run a Settings backup and post the logs.zip file on the removable media.
    - Remove SetupHelper last since once you do, you loose the PackageManager menus!

3. if you have terminal or ssh access, try running the package setup scripts to uninstall packages one at a time.

4. try booting to the previous Venus OS version (in Stored backup firmware)
	Then perform a fresh Online firmware update to the latest version or use the .swu update via removable media.

	Use the Settings / Firmware / Stored backup firmware menu if you have GUI access.

	If you don't have GUI access, you can also switch to the backup version from the command line:
	
	```bash
	/opt/victronenergy/swupdate-scripts/set-version.sh 2
    ```
    
	You can also force a firmware update from the command line if you have ssh or terminal access:
	- For on-line updates:
	  ```bash
	  /opt/victronenergy/swupdate-scripts/check-swupdate.sh -force -update
	  ```
	- For updates from removable media:
	  ```bash
	  /opt/victronenergy/swupdate-scripts/check-swupdate.sh -force -update -offline
	  ```

5. If PackageManager is still running, it will detect a file named AUTO_UNINSTALL_PACKAGES on removable media.
   - Create a file of that name (no extension, content unimportant) on a USB memory stick or SD card and insert this into the GX device.

   - The system should eventually reboot. In most cases, this should occur within 1-2 minutes.
   - After reboot, the system should come up in the stock configuration with no packages installed.

   - If the system does not reboot, it is likely PackageManager is no longer running, so try other options.

   - Remember to remove the media containing the `AUTO_UNINSTALL_PACKAGES` file to this will be repeated the next time PackageManager runs.

6. perform the Blind uninstall procedure below.

**Finally:**
- If you are running on a Raspberry PI, you can reimage the system SD card.
	
- If you have a Cerbo, you can reimage it using this procedure:
		https://community.victronenergy.com/questions/204255/cerbo-gx-bricked-how-to-recover.html

> [!NOTE]
> This will wipe out all settings and you'll need to reconfigure the GX device from scratch.

- The Victron "restore factory default" procedure can be used to will wipe out all settings.
  - You'll need to reconfigure the GX device from scratch.
  - However, it will NOT replace the operating system and Victron application, nor will it uninstall any packages.
  - You will most likely be locked out of ssh access since log-in information and ssh keys
	are stored in the /data partition which is completey erased by this procedure.
  - For this reason, I do not recommend using this as part of your attempt to recover a system with no GUI.


# Blind UNINSTALL:

A blind uninstall mechanism is provided to recover a system with an unresponsive GUI (white screen) or no ssh/terminal access.
This will run all package setup scripts to uninstall that package from system files.

In addition to uninstalling all packages, the blind uninstall can optionally reinstall VenusOS. To do so, include a `.swu` file for the platform and desired firmware version on the removable media containing the blind uninstall `venus-data.tar.gz` file.

The archive for this is named `venus-data.UninstallPackages.tar.gz`.

  1. Copy `venus-data.UninstallPackages.tar.gz` to a USB memory stick or SD card
  2. Rename the copy to `venus-data.tar.gz`
  3. Plug the removable media into the GX device
  4. Reboot, wait 2 minutes and reboot a second time
  5. When the system automatically reboots after the second manual one, remove the media.
     You should eventually see the GUI on the local display if there is one
     or be able to connect via remote console.

> [!CAUTION]
> Removing media or power cycling the GX device during the uninstall,
> especially if reinstalling firmware could render the system unresponsive!
> Wait to see the GUI before removing media or power cycling.

Note that a firmware update can take several minutes to complete but will eventually reboot.

When the blind uninstall finishes, `venus-data-tar.gz` file on the removable media
is renamed to `venus-data.UninstallPackages.tar.gz` so that the blind install will run only once.
This renaming is necessary to prevent a loop where the system uninstalls and reboots.

# System automatic configuration and package installation:

It is possible to use SetupHelper to set up a new system based on a template saved from a working system.
  - Setup the working system the way you want the new system to behave including custom icons,
  - then perform a Settings backup.
  - Remove the flash drive from the GX device and plug into a computer that has internet access.
  - Copy `venus-data.tgz` from the SetupHelper GitHub repo to the same flash drive.
  - If you wish packages to also be installed, copy the package -latest.tgz file from those repos as well.
  - Create `SETTINGS_AUTO_RESTORE` on the flash drive (contents don't matter - file may be empty).
  - Create `AUTO_INSTALL_PACKAGES` on the flash drive as well.
  - Place the flash drive into the GX device to be configured and reboot (once for v2.90 or twice for prior versions).
  - **REMOVE THE FLASH DRIVE** after you have verified that all packages have been installed (check Active packages in PackageManager).
