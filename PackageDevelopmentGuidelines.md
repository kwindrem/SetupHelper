# SetupHelper package development

**Kevin Windrem kwindrem@icloud.com**

**updated for v6.0**

This document provides guidance in developing a package suitable for
PackageManager management. When this guide is followed, PackageManager
should be able to download the package from GitHub or from media
inserted in the GX device and install it (bring it into operation under
Venus OS).

PackageManager is part of the SetupHelper package. It monitors GitHub
for package updates, downloads and installs them automatically (if
desired). It also provides a mechanism to add and remove packages from
those PackageManager will manage. The user interface for PackageManager
is a set of menus in the Venus OS GUI located at Menu / Settings /
PackageManager.

SetupHelper includes a set of utilities intended to handle the bulk of
package installation and uninstallation and also insures the package is
reinstalled following a firmware update. A Venus OS update will restore
any modified files to factory defaults, so any modifications must be
reinstalled following the Venus OS update.

There are a few basic requirements for a package to be recognized by
PackageManager:

1.  The package name must conform to unix file naming convention.

    To be most compatible, limit the package name to Upper and lower case
    alpha characters or numbers. **No spaces are allowed.**

1.  The package must contain a file named `version`. Specifics of the
    version are described later.

2.  The package should contain a file named `setup`. This should be an
    executable shell script that will install, uninstall or reinstall
    the package. SetupHelper includes unix bash shell script
    extensions that must be included in the setup script in order to
    be properly managed for reinstall after a Venus OS update. More
    details on the SetupHelper extension later.

3.  The package should contain a file named `gitHubInfo` which should
    contain the Git Hub user name and default branch separated by `:`
    E.g., `kwindrem:latest`

4.  The primary purpose of the setup script is to install modified files
    to the Venus OS file system. It is important that the package
    setup script is also written to **uninstall** the package,
    restoring any modified files to the factory settings. SetupHelper
    provides a number of utilities for this.

5.  In order for PackageManager to download the package from the
    internet, it must be contained in a GitHub repository. Any GitHub
    branch, tag or release may be referenced as long as it is valid.
    The suggested tag is `latest` which should point to the most
    recent released version. Additional tags matching a version number
    may be created in order to allow download of specific versions.
    Tags or branches such as `beta`, etc may also be created.
    PackageManager can also use branch names for specific downloads.

6.  The package script is run automatically only if a reinstall is
    required. Code that needs to run constantly or once each boot
    should use a service.

7.  A package may modify (replace) files in the Venus OS to enhance or
    change behavior. These replacement files should be stored in "file
    sets" one for each Venus OS version so that the package can be
    installed regardless of the Venus OS version currently running.
    More about file sets later.

8.  A package may optionally restrict its operation to a range of Venus
    OS versions.

9.  A package may also restrict its operation to a specific platform.
    Currently, the only restriction is for RaspberryPi platforms.

10. The package may include a ReadMe file describing the package and how
    to install it.

11. The package may contain a change log indicating what changed in each
    version.

12. The package may modify GUI files (specifically GUI v1 currently).
    Normally these modifications are essential to the functionality
    provided. If GUI v1 is not present on the system, the install will
    fail. This can be overridden with the `GUI_V1_NOT_REQUIRED` flag
    file in the package directory.

13. Setup scripts should execute as rapidly as possible. Time spent
    inside a setup script will delay other activities such as
    installing other packages and Package Manager will appear to be
    hung as there is no status update during lengthy operations. For
    this reason: **Any time-consuming activities such as installing
    files from the internet or compiling code must be offloaded to a
    secondary process.**

14. Dependencies on other packages should be identified in the
    packageDependencies file, described later.

## SetupHelper

SetupHelper oversees the installation, uninstallation or reinstallation
of the package. The package setup script must call ("source")
**IncludeHelpers**, a shell script extension before doing any work to
install or uninstall the package:

```bash
#### following line incorporates helper resources into this script

source "/data/SetupHelper/HelperResources/IncludeHelpers"

#### end of lines to include helper resources
```

IncludeHelpers sources the other helper resources.

These extensions validate the package for the current Venus OS version
and platform and builds a file set for the current Venus OS version if
necessary.

Beginning with SetupHelper v6.0, file and service and dBus Setting
installation is further simplified. These operations will be based on
various list(s) and contents of the services directory located in the
package directory.

Some modifications, such as adding lines to /u-boot/config.txt for
Raspberry PIs will still require code in the setup script, but in
general **installFiles**, **installServices** and **addDbusSettings**
functions will handle the bulk of the activities. These can be called
from the setup script or more conveniently, triggered when calling
**endScript**.

Including the following line in the setup script BEFORE sourcing
IncludeHelpers triggers a default prompt for install or uninstall then
proceeds with the install/uninstall operations:

```bash
standardPromptAndActions='yes'
```

In that case, InstallHelpers never returns to the setup script.

If the `standardPromptAndActions` is not set, the helper resources will
then hand control back to the setup script. A prompt for user input is
then necessary followed by any processing and installation that can't be
handled by the list-based functions mentioned above.

After any special processing has been performed, the script should call
the '**endScript**' function (in CommonResources) in order to exit the
script with the proper exit codes. These exit codes are necessary for
proper behavior of PackageManager and the automated reinstall operations
performed at system boot when the Venus OS is updated.

Parameters passed to endScript triggers automatic install/uninstall.
(described later) For example:

```bash
endScript INSTALL_FILES INSTALL_SERVICE ADD_DBUS_SETTINGS
```

**genericSetupScript** located in the SetupHelper directory will install
any package that does not require in-line prompting, install or
uninstall code. Simply link to this setup script in that package's
directory or copy it there.

## Patched files

Package installation has historically replaced files to modify content
of the active file. Beginning with v8.0, SetupHelper will attempt to
patch an active file in the fileListPatched list rather that replacing
it. This allows multiple packages to modify the same file.

Files to be patched require entries in the PatchSource directory in the
FileSets directory. They also require an entry in the fileListPatched
list. A patch (...patch) file is used during the patch process,
operating on the active file.

The original, unmodified active file(...orig) along with a modified
version are needed to create the patch file. If these files are present
in the PatchSource directory, updatePackage will attempt to create a
patch file, or update it if the orig and modified files have been
changed making the .patch file obsolete.

**diff -u** is used to create the patch file.

A ...patchOptions file can override the default -u option. For example
if the patchOptions file is **-U 0** the patch file will not have any
context lines. If patchOptions includes **MANUAL**, then
**updatePackage** will not attempt to create a patch file. In this case
the patch file will need to be created manually. E.g., with:

```bash
diff -u foo-1.orig foo-1 > foo-1.patch
```

The patch file then needs to be located in the PatchSource directory.

On the GX device, helper resources use the .patch file to create a
patched file. These are stored in a temp directory created by **mktemp**
and can be referenced with $patchedFiles/foo-1.patch.

Some modifications may not be suitable for all Venus OS versions. The
patch mechanism allows multiple patch files. E.g.:

```bash
PageSettings.qm-1.patch, PageSettings.qm-2.patch
```

Any unique string after the - is an acceptable suffix for the set of
patch files.

During installation, each patch file will be tested and the first one to
succeed is used to patch the active file and unpatch it later during
uninstall.

During installation, CommonResources attempts to patch the current
active file, then reverse patch it to insure that original can be
recreated during a future uninstall. If these succeed, the install is
allowed to continue.

During the uninstall process, the active file replaced by the .orig file
if no other packages have modified the file. However, if there are other
package modifications still present in the active file, it is "reverse
patched" to restore the file to it's state before the package was
installed. This would remove the modifications for this package while
preserving modifications from other packages.

There is a slight possibility that this "reverse patch" could fail. If
this occurs, the active file is replaced by the .orig file in order to
prevent a system crash due to a missing or incorrectly patched active
file. **Modifications from other packages are lost, requiring them to be
reinstalled.**

There are restrictions that package authors need to keep in mind. These
restrictions are due to "context" created for the modification. These
are lines prior to and after the modification that are the same with and
without the modification. **patch** uses these to locate the proper
place in the current active file to apply the patch.

1.  Modifications from multiple packages must not overlap. Even
    modifications that occur at the exact same place in the file might
    not produce a patch file that succeeds with and without the other
    package's modifications because the context lines won't match.

2.  Modifications at the very beginning or end of a file may not produce
    a usable patch file. Again, because there is insufficient context.

It is important that the author identify other packages that modify the
same files and test installation and uninstallation of all packages
involved, *and* in different install/uninstall orders.

> [!NOTE] 
> The patch utility provided with Venus OS is part of BusyBox
> and has limitations that prevent its use by SetupHelper. Therefore, a
> more fully functioned version is included with SetupHelper beginning
> with v8.0 and is used by HelperResources.

## Setup script command line options

CommonResources checks for optional command line parameters before
passing control to the body of the setup script.

- **reinstall** indicates this is to be a reinstall. Installed version
  is compared to the version in the package directory and skips
  reinstall if they match. User prompting is skipped. (These version
  checks are now redundant since **reinstallMods** which controls
  package reinstalls following a Venus OS update also check versions
  before calling the package setup script.)

- **install** indicates that the prompts should be skipped and the
 installation begun with stored options (more about this later).
 **uninstall** indicates the prompts should be skipped and the package
 uninstalled.

- **auto** silences all console messages. Progress of the setup is
  logged. Without the **auto** option progress is also written to the
  console.

- **deferReboot** instructs endScript to skip the automatic system
  reboot and return indicating a future reboot is needed.

- **deferGuiRestart** is as above but for automatic GUI restarts.

Without any options, helper resources assumes a user has run the script
and sets up the environment to prompt for user input to control
additional execution.

When the setup script regains control following CommonResources, the
variable 'scriptAction' will be set to either NONE, INSTALL or
UNINSTALL. NONE indicates that the script should prompt for user input
to control further execution. These prompts should be skipped if
scriptAction is either INSTALL or UNINSTALL. Note that if an install
action fails, scriptAction will be set to UNINSTALL, so scriptAction
must be tested again after the install section and perform the uninstall
operations. This prevents a partial install from disrupting the system
operation. Note that this behavior is not automatic and must be written
into all package setup scripts.

Venus OS is a "dual root fs" system. That is, the operating system and
executable parts of the system reside on one of two root partitions. One
partition is active and the other inactive. A Venus OS firmware update
installs files to the inactive partition. Then when the update has been
verified, the active and inactive portions are swapped and the system
rebooted to execute the updated code. If the update is unsuccessful, the
swap does not occur and the old executable files continue to run. This
prevents a partial or corrupted firmware update from bricking the
system. A third partition (/data) holds any persistent information
(settings, etc).

Packages are stored in the data partition so they survive a Venus OS
firmware update, however any system files will be overwritten.

At boot time, the **reinstallMods** script is called. Starting with
SetupHelper 8.0, **reinstallMods** only installs the PackageManager
service. It sets a flag: /etc/venus/REINSTALL_PACKAGES then exists.
**PackageManager** then tests this flag file and installs the ALL
packages, including the remainder of SetupHelper. This was done to avoid
so that all of PackageManager's pre-install checks to be made prior to
installing a package. Plus some of the packages available now take
several minutes to install resulting in a lag to install all packages
after a Venus OS update. Now, status is shown in **PackageManagers**'s
menus and in it's log file.

When packages are reinstalled, the package setup script is called with
the **reinstall**, **auto**, **deferReboot** and **deferGuiRestart**
options. **PackageManager** will then trigger a system reboot or GUI
restart if any package setup scripts have requested those actions.

**PackageManager** acts on requests for system reboot or GUI restarts
when an install or uninstall is triggered from it's menu. A user choice
to defer reboots and GUI restarts is then provided.

A package may sometimes need to manually modify certain files because
the automatic mechanisms are too general. For example, adding device
tree overlays to `/u-boot/config.txt` must be done in a way that it does
not disturb what's currently in the file. All the automatic install
mechanism can do is replace the existing file. Code for such
modifications goes in the `setupAction == 'INSTALL'` section of code and
any restoration code would still go in the `setupAction == 'UNINSTALL'`
section.

Setup scripts written prior to SetupHelper v6.0 will continue to
function. even if the `INSTALL_...` options are set when calling
endScript. endScript will attempt to repeat install and uninstall
operations but no harm will be done (other than taking additional
time).

## Automated install

Beginning with SetupHelper v6.0, install and uninstall can usually be
handled within CommonResources. Prior to SetupHelper v6.0, the setup
script needed code to install and uninstall every modified file or
service using the utilities described in the next section. Calls to
install and uninstall services was also needed.

Installs use "file lists" to install modified files. Each file
modified is saved in a modified files list which is then used to
uninstall the package.

Refer to the section on File Sets below for more details on file
lists.

All services to be installed by the automatic processes must be
located in the services directory. There is no services list since the
directory provides the necessary information. An installed services
list is created to allow for automatic uninstall.

`/data/< package name >/services`

Services are still directories with run and log/run files as before.
Any service directories found in services will be automatically
installed. Automatically installed services are added to an installed
services list and will be automatically uninstalled using that list.

The name of the directory within services will determine the service
name. E.g., the following service directory will create the
PackageManager service

`/data/SetupHelper/services/PackageManager`

Prior to SetupHelper v6.0, services were located in the package
directory. The service name was determined by the package name, or
specified on the installService line. These services will NOT be
automatically installed, so their service directories are moved to
services and named appropriately.

The modified files and services list are located in /etc/venus.

`/etc/venus/installedModifications/installedFiles-<package name>`

`/etc/venus/installedModifications/installedServices-<package name>`

This location was chosen because it is removed on a Venus OS update.
Running the setup script to uninstall a package will therefore do
nothing as expected. If the lists were stored in /data, then an
uninstall would attempt to uninstall the files and services again.
Generally, that isn't a problem but really should not happen.

The package is uninstalled by walking through the installed... lists
to restore the original files. Generally, those calls in the setup
script are no longer necessary.

## SetupHelper utilities

SetupHelper provides a set of utilities to simplify the installation of
modified files (called a "replacement") into the active root file system. It pulls the correct
replacement file from a "file set" for the current Venus OS version,
moves the original out of the way and installs the replacement file. On
uninstall, the original file is moved back to the active location (file
name) leaving the system in an unmodified state.

> [!NOTE]
> Starting with v6.0, these utilities may be of less use but are still
included.

**updateActiveFile** is a function that installs a replacement file as
described above. Typically, the replacement file has the same name as
the original so the simple form of the command can be used. For example,
to replace a GUI file:

`updateActiveFile "/opt/victronenergy/gui/qml/main.qml"`

If however, the replacement file has a different file name, a second
form is used. This may be necessary if the setup script has to build or
modify the replacement file.

`updateActiveFile "$scriptDir/foo.qml" "/opt/victronenergy/gui/qml/main.qml"`

**restoreActiveFile** is a function that undoes the above operation and
is called during uninstall with the same file names as were used with
updateActiveFile during install:

`restoreActiveFile "/opt/victronenergy/gui/qml/main.qml"`

**backupActiveFile** is a function that creates the .orig file used by
restoreActiveFile but does not update the active file. It is preferable
to make modifications in the setup script to a temp file then use
**updateActiveFile** as described above but this is not always possible.

Use only when something modifies the active file in place:

`backupActiveFile "/etc/pointercal"`

`ts_calibrate # modifies /etc/pointercal directly`

**installService** is a function that installs and starts a dameon
service. The service will be placed in the / service directory (or
/opt/victronenergy/service for v2.80 or later). A folder in the package
folder named 'service' must contain the files that will end up in
/service under the service name

`installService FooService`

Will copy the service directory from the package directory into
/service/FooService

**removeService** is a function that removes the service which is
necessary during an uninstall to restore the system to factory.

`removeService FooService`

**logMessage** is a function that will log anything of interest.
Messages are either sent to stdout or to the PackageManager log file:
log file: /var/log/PackageManager/current.
Logging is encouraged as it helps debug systems in
the field (and while developing the package). Without the **auto**
option on the call to the setup script, these messages are also output
to the console.

To conform to Victron guidelines, messages are sent to stdout in
all but a few unavoidable situations:
running the script in **auto** from the command line (discouraged)
**reinstallMods** or **blindInstall** **blindUninstall**.

When scripts are run from PackageManager, stdout is collected
and forwarded to the log using python's logging.info () method.
This way, a the informaiton is persistant for debugging.

When scripts are run from the command line, any messages
appear on the console but are **NOT logged**.

`logMessage "this text will end up in the log"`

**endScript** Function to finish up, prompt the user (if not
reinstalling) and exit the script. (Details are described below.)

*The following functions simplify the task of getting user input.*

**standardActionPrompt** displays a menu of actions and asks the user to
choose

- It sets scriptAction accordingly and returns

- It also handles displaying setup and package logs then asks for an
 action again

- It also handles quitting with no action - the function *exits the
 shell script* without returning in this case

- The basic action prompt includes install, reinstall, quit, display
 logs (2 choices)

- A reinstall option is enabled if the optionsSet option exists

- When reinstall is enabled, selecting install, returns a scriptAction
  of NONE indicating additional prompting may be needed to complete the
  install

- At the end of these prompts, the main script should set scriptAction
  to INSTALL

- If reinstall is selected, the script action is set to INSTALL and the
  main script should then skip additional prompts and allow options set
  previously to control the install

**yesNoPrompt "prompt "**

- Asks the user to answer yes or no to the question

- Any details regarding the question should be output before calling
  yesNoPrompt

- **yesNoPrompt** sets **$yesResponse** to true if the answer was 0 if
  yes and 1 for no so that the return code can be checked rather than
  checking $yesResponse:

    ```bash
    if yesNoPrompt "do it (y/n)?" ; then
      do stuff for yes response
    else
      do stuff for now response
    fi
    ```

A set of utilities manages dbus Settings: creating, removing, updating.
It is sometimes necessary for the setup script to create dbus Settings
so GUI has access to them. This is often the case when the package
doesn't run its own service.

The following functions will create dbus settings if they do not already
exist or update their value if they

```bash
updateDbusStringSetting "/Settings/StringSetting" "the new string" 
updateDbusIntSetting "/Settings/IntegerSetting" 5
updateDbusRealSetting "/Settings/FloatingPointSetting" 6.0
```

**setSetting** is a function that updates the value of an existing dbus
Setting. It is faster than calling one of the above update... functions.
The new value can be any data type but strings must be quoted.

```bash
setSetting "/Settings/foo" "new string" 
setSetting "/Settings/bar" 18
```

The following function removes the settings. Limit the number of
settings to about 20 to avoid some being missed (not sure why). It is
faster to remove multiple settings at the same time than it is to call
'removeDbusSettings' for each one.

```bash
removeDbusSettings "/Settings/foo" "/Settings/bar" 
```

## SetupHelper variables

SetupHelper manages or tests a set of variables that control script
executions:

**$scriptAction** provides direction for the setup script and has the
following values:

- NONE - setup script should prompt the user for the desired action and
  set scriptAction accordingly

- EXIT - the setup script should exit immediately

- INSTALL - the setup script should execute code to install the package

- UNINSTALL - the setup script should execute the code to restore the
  Venus files to stock If installation errors occur within functions in
  CommonResources, scriptAction will be changed to UNINSTALL.

The setup script MUST retest scriptAction after all installation code
has been executed so the package can be removed, rather than leaving the
system with a partially installed package.

**$rebootNeeded** - true signifies a reboot is required after the
script is run. The setup script should set **rebootNeeded** to true if a
reboot is needed following install/uninstall

*The following variables contain useful information but should not be
changed by the setup script:*

- **$scriptDir** - the full path name to the startup script the
  script\'s code can use this to identify the location of files stored
  in the package

- **$scriptName** - the basename of the setup script ("setup")

- **$reinstallScriptsList** - the file containing a list of scripts to be
run at boot to reinstall packages after a Venus software update (by default, this is
/data/reinstallScriptsList)

- **$installedVersionFile** - the name of the installed version file

- **$venusVersion** - the version of VenusOS derived from
/opt/victronenergy/version

- **$fileList** - the version-dependent location for the replacement
files

- **$fileListVersionIndependent** - the location for files that are
independent of Venus OS version

- **$fileListPatched** - the location for files that are to be patched
prior to install

> [!NOTE] 
> Prior to SetupHelper v6.0 version-independent replacement files
were in $pkgFileSets directory.

- **$pkgFileSets** - is the location of all file sets

- **$fileSet** - is the location of version-dependent files for the
current Venus version

- **$runningAtBoot** - true if the script was called from reinstallMods (at boot time) 
 
  signifying this is to be an unattended (automatic) installation

  CommonResoures sets this variable based on command line options

- **$setupOptionsDir** - the location of any files that control installation

  These options are maintained in a separate directory so reinstalling
  the package does not remove them so that a reinstall can proceed
  without prompting again

- **$obsoleteVersion** - prevents installation starting with this Venus
OS version

- **$firstCompatibleVersion** - prevents installation *before* with this
Venus OS version

## Package lists

It is usually necessary to create a specific replacement file for
different Venus OS versions. This allows the package to be installed
regardless of the Venus version. These different replacement file
versions are contained in a "file set": a directory with the Venus OS
version number as it's name. The collection of file sets is stored in
the 'FileSets' directory in the package directory.

Some files in a package may not be tied to specific Venus OS versions.
These are typically additions to the stock files, and when a single file
can be used across all Venus OS versions. Prior to SetupHelper v6.0,
these *version-independent* files were contained in the FileSets
directory. Starting with v6.0, they are located in the
**VersionIndependent** file set.

These two file lists are kept separate because they are treated
differently.

The list **fileList** has always been used by helper resources to guide
installation of *version-dependent* files

Starting with v6.0, three additional lists have been added:

**fileListVersionIndependent** lists all *version-independent* files.
Those files exist in the **VersionIndependent** file set.

**fileListPatched** is a similar list for any replacement files that are
created with the unix patch command. Patch replacements are described
above.

The file lists consist of one line per file with the full path and name
of the file on each line.

The **DbusSettingsList** contains a list of dBus Settings to be added to
the system as part of this package. Settings are traditionally added via
a service but in cases where the package does not have a related
service, this mechanism allows there creation or update from the setup
script. Lines in **DbusSettingsList** are in the format:

```json
{"path":"/Settings/Relay/0/Show", "default":1, "min":0, "max":1}
```

"default" defines the default value plus the data type (1 for an
integer, 1.0 for float, "something" for a string)

"min" and 'max" are optional and set the range of acceptable values.

Refer to Victron dbus documentation for more details

File list for version-dependent files only:

```
/data/< package name >/FileSets/fileList
```

File list for version-independent files:

```
/data/< package name >/FileSets/fileListVersionIndependent
```

File list for patched files:

```
/data/\< package name \>/FileSets/fileListPatched
```

File list for dBus Settings:

```
/data/< package name >/DbusSettingsList
```

### Missing active file directories

Recently, Victron Energy has changed the name of some directories which contain files requring modificaiton by the package.
For example, /opt/victronenergy/bus-generator-starter was renamed /opt/victronenergy/dbus-generator.

In order to accommodate these name changes, SetupHelper v8.23 checks for the existance of the enclosing directory
for an active file and skips the update if the directory does not exist. This is logged but installation is allowed to continue.

[!NOTE]
Developers should review such log entries to insure there are no missing active file updates!

In such situations **fileList** and **fileListPatched** must include **both** enclosing directories. E.g.,:

```bash
/opt/victronenergy/dbus-generator-starter/startstop.py
/opt/victronenergy/dbus-generator/startstop.py
```

## Version file

A package must contain a version file. This is the *package* version,
not the Venus OS version. The package version is used by PackageManager
to decide if an automatic download is needed by comparing the version
from GitHub with the version stored on the system. Likewise, the stored
version is compared to the installed version to trigger an automatic
install.

The version file is a text file with a single line of the form: v1.2,
v1.2\~3 v1.2a3.

Versions that include a \~ or lettered version are treated as
pre-release.

- 'd' represents a development release

- 'a' represents an alpha release 
- 'b' or '\~' represents a beta release
- none of the above represents a released version

Version numbers are prioritized: 'a' is "newer" than 'd', etc.

"newer" versions will replace older versions when automatically
downloading. Exception: if the branch/ tag set in PackageManger is a
specific version (e.g., v.4.6) the stored version must match rather than
being older than. Installs always occur if the versions do not match.

## Restricted install

The package may optionally contain files that place restrictions on
which Venus OS versions or platforms the package may be installed on. If
any of these tests fail, the install will also fail!

If present **obsoleteVersion** identifies the first version that are not
compatible with this package. E.g., of obsoleteVersion contains v7.2 and
the current Venus OS version if v8.0, then the package can't be
installed.

If present **firstCompatibleVersion** identifies the first version that
IS compatible with this package. E.g., if firstCompatibleVersion
contains v8.0 and the current Venus OS version is v7.2, the package
can't be installed.
If **firstCompatibleVersion** is not present, SetupHelper uses v3.10 as the first compatible version.

Note that if both **firstCompatibleVersion** and **obsoleteVersion** are
included in the package directory, the obsoleteVersion must be greater
than firstCompatibleVersion.

If present **validFirmwareVersions** identifies all versions which have been
tested as compatible with the package. It is a list of Venus OS versions, one per line.
If this file is present, **firstCompatibleVersion** and **obsoleteVersion** are redundant.

If the file **raspberryPiOnly** exists in the package directory, the
platform (aka 'machine') MUST be raspberrypi2 or raspberrypi4. If not,
installation will be blocked.

Many packages modify the GUI file system. With the introduction of
gui-v2, some systems will not have the GUI v1 files in place or will not
be running the original GUI.

If GUI v1 files are required for the package, it's installation will
fail. In some cases, the GUI modifications are not essential for package
functionality, so if the flag file **GUI_V1_NOT_REQUIRED** is included
in the package's root directory the package install will not consider
missing GUI v1 files an error.

GUI v1 files are those found in /opt/victronenergy/gui. If files from
that directory appear in the file list and **GUI_V1_NOT_REQUIRED** is
not in the package directory, the install will not be permitted. A check
is also made in **updateActiveFile** and will force a package uninstall.

**NOTE: SetupHelper will allow an install if the GUI v1 files are
present on the system. However, GUI v1 may not currently be running in
which case, the user will not have access to the added/modified menus.**

Failed installs force an UNINSTALL.

## Package conflict management

Prior to SetupHelper v6.12, packages may interact with each other in
undesirable ways. For example, one package that modifies the same file
as another will install over the other package, removing the first
package's modifications. Uninstalling either package will result in
the stock file being used.

SetupHelper v6.12 adds logic to prevent this from happening. If a
package attempts to modify the same file as another package, the
install will fail and the package will be uninstalled. Beginning with
v8.0, multiple packages may be able to modify the same active file.
See the section on patching files above.

The **packageDependencies** file located in the package directory
defines basic requirements that would prevent the package from being
installed.

Each line of the file includes a package name and whether that package
must be installed or uninstalled in order for the package to be
installed. For example the file for RemoteGPIO might be:

```
RpiGpioSetup uninstalled
GuiMods installed
```

These lines tell SetupHelper to block the install of RemoteGPIO unless
RpiGpioSetup is uninstalled and unless GuiMods is installed.

Note that no changes to other package installations occurs so it would
be acceptable for the dependency file for RpiGpioSetup to also specify
that RemoteGPIO should be uninstalled. This way only one can be
installed but the user has that choice.

This mechanism is simple but has a drawback: **Package authors must
manually check for conflicts and coordinate with other package authors
on how best to address the conflict.**

## endScript

The **endScript** function must be called at the end of the setup
script. It determines the return code used by the caller (like
PackageManager) to provide the necessary user prompting and to control
reboot and service restarts.

**endScript** NEVER RETURNS to the caller !

The actions taken by endScript depend on a number of shell variables set
previously and on parameters passed when calling the function:

- The following parameters are passed from the caller. All optional:

  - **INSTALL_FILES** causes endScript to install/uninstall based on fileList, fileListVersionIndependent and fileListPatched lists.

  - **INSTALL_SERVICE** causes endScript to install/uninstall services located in the package services directory.
  
  - **ADD_DBUS_SETTINGS** causes endSctipt to perform the file addition or update of dBus Settings based on the DbusSettingsList in the package
  directory.

- If **$runningAtBoot** is true the script will exit with **EXIT_REBOOT** if **$rebootNeeded** is true otherwise, the script will exit with **EXIT_SUCCESS** on success.

- If **$runningAtBoot** is false (script was run manually), user
  interaction controls further action If **$rebootNeeded** is true, the
  function asks if the user wishes to reboot now. If they respond yes,
  the system will be rebooted. The user may choose to not reboot now if
  additional installations need to be done first

- If **$rebootNeeded** is false, the function notifies the user of any
 needed actions

- If **$restartGui** is true the gui service will be restarted

Starting with SetupHelper v6.0, other services will be restarted by
endSctipt if related files are changed with updateActiveFile or
restoreActiveFile. Refer to the updateRestartFlags function in
CommonResources for details.

If the setup script is run from the command line (no command line
options), **endScript** will prompt the user for a reboot or GUI restart
if one is needed. The user can choose to trigger the action now or wait
and do it manually later.

However, if the script is running autonomously, the action will be
triggered from within endScript, *unless* the script was run with
**deferReboot** or **deferGuiRestart** on the command line. In this
case, the action is not performed but the script exits with the
appropriate exit code. PackageManager and **renstallMods** use the exit
code to choose a course of action following all automatic operations.
For manual install/uninstall from PackageManger, the user is given the
choice to perform the GUI restart or reboot now or do it later. If
deferred, a message will be displayed indicating the package isn't fully
active ("reboot needed").

For reinstalls following a Venus OS update, **reinstallMods** will
reboot the system or restart the GUI after installing SetupHelper.

When the setup script completes an install operation, **endScript**
writes the package version to a file in / etc/venus. **endScript**
deletes this file during an uninstall. The installed version file
written to /etc/venus tells PackageManger which version of each package
is installed and running. It also tells the reinstall mechanism to skip
SetupHelper reinstall. So reinstall only happens if the installed
version file is NOT present or the installed version differs from the
package version itself. The latter may be the case if a Venus OS
firmware update has occurred.

Some packages may need to reboot in the middle of the installation
process. For example, if an overlay is needed to test for a specific
condition, the setup script should install the overly, but skip the
remaining setup, then set the **runAgain** shell variable before calling
endScript. endScript then removes the installed version file so the next
boot will run the package's setup script again.

If an install operation fails, it sets the shell variable
**installFailed**. **endScript** will then switch from INSTALL to
UNINSTALL to insure that all stock files are restored and the system is
not left in a partially modified state. **installFailed** is set by most
utility functions but should also be set inside any code in the setup
script that detects a failure. Also, any code should test
**installFailed** before proceeding with file modifications.

### endScript exit codes

The following is a list of exit codes returned when endScript exits:

- EXIT_SUCCESS=0 no further action needed

- EXIT_REBOOT=123 system reboot needed

- EXIT_RESTART_GUI=124 GUI restart needed

- EXIT_INCOMPATIBLE_VERSION=254 install failed - version not compatible

- EXIT_INCOMPATIBLE_PLATFORM=253 install failed - platform not compatible

- EXIT_FILE_SET_ERROR=252 install failed - file set problems

- EXIT_OPTIONS_NOT_SET=251 install failed

  - run setup script from command line

- EXIT_RUN_AGAIN=250 partial install

  - run script again after reboot

- EXIT_ROOT_FULL=249 install failed - no room on root

- EXIT_DATA_FULL=248 install failed - no room on /data

- EXIT_NO_GUI_V1=247 install failed - GUI V1 needed

- EXIT_PACKAGE_CONFLICT=246 install of this package blocked by another package

- EXIT_ERROR=255 install failed - unknown error

## PackageManager

Package Manager includes a set of menus on the GX device menu system
that allows the user to view package versions, control automatic package
updates and manually install, uninstall, add and remove packages. This
provides an alternative to the command line interface for package
management.

A PackageManager is a python program that runs as a service to do the
actual work and to interface with the menus.

### Package Manager menu

The first line of this menu provides status for Package Manager,
indicating what it is currently doing

**Automatic GitHub downloads** controls if packages are automatically
downloaded from GitHub. This occurs if a newer version is available.

- **On** checks GitHub for a package that is newer than what is stored on
the system

- **Once** checks GitHub for a package, then downloads are turned off

- **Off** disables GitHub downloads

GitHub versions are refreshed every 10 minutes if auto downloads is
turned on. If auto downloads are off GitHub versions are refreshed once
when entering the Package Versions menu. A specific package's GitHub
version is also refreshed when entering the Package edit menu.

If auto downloads are off, GitHub versions expire after 10 minutes.

**Auto install packages** controls whether new versions of a package are
automatically installed. Some users may wish to have the system
automatically download new updates, but install them manually. In this
case, automatic GitHub downloads may be turned on and Auto install
packages turned off.

Auto install packages also influences whether packages transferred from
SD/USB media are automatically installed or just transferred to local
storage

**Active packages** and **Inactive packages** lead to menus described
below

**action to finish install/uninstall** appears of a system reboot or GUI
restart has been deferred (see the Package editor menu)

**Backup & restore settings** leads to the menu described later

**microSD / USB** indicates if removable media has been detected and
allows it to be ejected prior to removal.

**Restart or initialize ...** leads to the menu described below

### Active packages menu

Displays all active packages, and allows access to editing the package
setup

Tapping on one of the entries leads to the Package editor menu

Version information is displayed for each package:

- GitHub shows the version found on GitHub 
- Stored shows the version stored on the GX device 
- Installed shows the version actually installed and running

> [!NOTE] 
> If the GitHub version is not shown, check the GitHub user and
branch/tag, or check your internet connection.

### Package editor menu

This menu facilitates manual install, uninstall, package removal as well
as changing GitHub access information for the package.

**GitHub user** is the name of the GitHub user authoring the package.
Normally this won't change.

**GitHub branch or tag** allows you to specify a branch or specific tag.
The default (typically **latest**) references the latest released
version of the package. You can change this field to try out a beta
version or revert to a specific version. Once the GitHub branch is
changed, PackageManager will update the GitHub version. If auto
downloads are active the new version will be downloaded automatically.

The status line shows progress of pending operations, conflicts, or
prompts for further actions.

**Previous** and **Next** step through other packages without leaving
this menu.

The remaining buttons along the bottom of the menu allow for
**Download**, **Install**, **Uninstall** or **Remove**. These operations
require a confirmation via **Proceed** or **Cancel** in the status line.

**Remove** will remove the package from the active package list and
return it to the inactive packages list. Packages that are of no
interest can be removed to keep the active list cleaner.

Package manager does not allow removing packages unless they are
uninstalled first.

Package manager DOES permit uninstalling SetupHelper, however this will
remove the Package Manager itself. Once removed, the Blind Install
mechanism will be needed again !!

**Show Conflicts** appears in the status line if package conflicts
exist. Pressing that shows a list of conflicts and if possible asks if
they should be resolved. If they are, **Proceed** and **Cancel** appear.
Pressing **Proceed** will trigger the necessary package installs and
uninstalls needed to resolve the conflicts

If an operation requires a system reboot or GUI restart, a message
appears in the status line. **Now** triggers that operation. **Later**
hides the notification without acting on it. This can be handy if you
are performing multiple operations. The notification will appear when
navigating to other packages.

### Inactive packages menu

Displays all INACTIVE packages, i.e., default packages not yet activated
or manually remove.

The first entry is always \"new\" and allows the operator to enter
package name, GitHub user and branch/tag from scratch

Additional lines (if any) are default packages (from the
defaultPackageList file)

If a package is already added to the version list, it will not appear in
the Add Package list

Tapping on one of the entries leads to the Add package menu

### Add package menu

Allows the package name, **GitHub user** and **GitHub branch or tag** to
be entered or changed and the package added to the active packages list.
These are the same as described above under Package editor menu.

Prompting for required information is provided on the status line.

Pressing **Proceed** initiates the package add. **Cancel** returns to
the Inactive Packages menu.

The package name must be unique or the add operation will fail with a
prompt indicating to choose a different name.

### Backup & Restore settings menu

Saves settings to the settingsBackup file on removable SD/USB media or
to local media (`/data/settingsBackup`). restores from same.

`/data/SetupHelper/settingsList` is a complete list of settings saved to
settingsBackup. Categories are:

- GuiMods
- SetupHelper / PackageManager
- ShutdownManager
- SOME Victron stock settings in the following sections  
  - Alarms
  - Gwacs
  - DigitalInputs 
  - Generators
  - Gui
  - Pump
  - Relay
  - System
  - SystemSetup
  - Vrmlogger

Additionally, backup and restore the following to/from removable media


- Any logo files in `/data/themes/overlay` 
- Setup script options in `/data/setupOptions`

All logs stored in `/data/log` are written to logs.zip on removable media
as part of a backup operation

The parameters must exist to be saved. The parameters will be created
and set to the backed up value during a restore.

> [!NOTE]
> Victron is working on a more comprehensive mechanism but is not
> working reliably yet. The Package manager backup and restore is
> temporary and will be removed when the Victron functionality is
> working

### Package manager restart/initialize menu

This menu provides a quick way to reboot the system (**Restart**),
restart the GUI (**Restart GUI**) or initialize Package manager.
(**Initialize**). The latter can be used to clean up Package manager's
persistent storage. Any custom packages added manually or any GitHub
user or branch/tag information will be lost.

### USB/SD updates

When the GX device is not connected to the internet, a USB flash drive
or microSD card provides an install/upgrade path. To use the USB update
process

1.  Navigate to the GitHub, repo, click on tags and select the
    appropriate branch or specific version.

2.  Choose the .tar.gz download link. (Do not download from the Code tab
    or download the .zip file. These won\'t work.)

3.  Copy the archive file to a USB memory stick or microSD card. Do NOT
    unpack the archive

4.  Repeat this for all packages you wish to install. (These can all be
    placed on the same media along with the SetupHelper blind install
    `venus-data.tgz` file)

5.  Insert the stick in the GX device.

6.  If SetupHelper has not yet been installed, follow the Blind Install
    process from the ReadMe.

Once Package Manager is running, it will transfer and unpack the archive
files and update the package list with the new packages.

If Auto install packages is turned on, the packages will then be
installed

> [!NOTE]
> No version checks are made for packages found on SD/USB media!
> Package Manager is quite content to transfer and install an older
> version so make sure you have the latest version especially if your GX
> device does not have internet access.

### Package manager control via removable media

Besides the menus described above, Package manager can be controlled via
"flag" files on removable media. These flag files trigger behavior if
they are detected. The file contents is not important, only the
existence of the file.

**SETTINGS_AUTO_RESTORE**

An automatic settings restore will be performed when PackageManager if
the file is present.

> [!CAUTION]
> Leaving this removable media in the system will trigger
> settings restore with every boot. You must remove the flash drive
> after auto restore

**AUTO_EJECT**

ALL removable media is ejected after the media is scanned AND if after
all transferrers were performed.

Removable media can be corrupted if removed while the VRM logger is
still writing to it so the drive must be ejected to prevent corruption.
A manual eject button is included in the PackageManager menu.

Unfortunately, the eject mechanism ejects all removable media, not just
a specific one. The VRM logger automatically uses the first removable
media found so there is no control over it, and the presence of
AUTO_EJECT will eject the media for the logger also.

**AUTO_INSTALL_PACKAGES**

All packages will be installed even if the Auto Install menu option is
turned off. This is generally used only for system deployment (see
below).

**AUTO_UNINSTALL_PACKAGES**

As above, but will uninstall all packages found in /data. This is useful
if you do not have command line access and end up with a GUI that is
unresponsive or just to clean up a system, returning it (almost) to
factory defaults. This flag file overrides AUTO_INSTALL_PACKAGES if both
are present

The system is rebooted after the uninstall all just to be sure there\'s
nothing left behind.

**AUTO_INSTALL**

If the file AUTO_INSTALL is present in a **package directory**, the
package will be installed as if the auto install option is set in the
PackageManager menu. Version checks are still performed and
DO_NOT_INSTALL is honored.

**ONE_TIME_INSTALL**

If the file ONE_TIME_INSTALL is present in a **package directory**, the
package is automatically installed even if automatic installs are
disabled and the DO_NOT_INSTALL flag is set

ONE_TIME_INSTALL is removed when the install is performed to prevent
repeated installs. Packages may be deployed with this flag set to insure
it is installed when a new version is transferred from removable media
or downloaded from GitHub

**INITIALZE_PACKAGE_MANAGER**

The PackageManager's persistent storage is rebuilt (see Initialize
above)

## updatePackage

**updatePackage** is a unix shell script that runs on the development
computer, not the GX device. It is included in the SetupHelper package.
The comments at the top of the script provide additional details.

Windows will not run this script natively. However Windows 10 apparently
supports bash:

https://www.howtogeek.com/249966/how-to-install-and-use-the-linux-bash-shell-on-windows-10/

Windows developer options must be enabled. In addition, differences in
end of line between platforms may need to be manually adjusted (cr-lf
for Windows) for the script to run properly.

Another option is to run **updatePackage** on a unix virtual machine or
a Raspberry PI running it's native OS.

In order to identify changed files, the original file for each
replacement must be compared against ALL versions of Venus OS. When
changes are detected, a new file set version directory needs to be
created and a new \...orig file copied from the stock Venus OS file.
This work is done on the computer creating the package, not on the GX
device.

I use the raspberry Pi images from
http://updates.victronenergy.com/feeds/venus/ because these contain the
compete file system. Alternatively, the file system can be copied from a
running GX device ***prior*** to installing any packages. I create a
directory on the managing computer called OriginalFiles, then create a
directory for each Venus OS version: v2.81, v2.90\~12, etc.

Next, I copy the /etc, /opt and /var/www/venus/styling directories from
the Venus OS image to the OriginalFiles/vX.Y\~Z directory.

I limit StockFiles to these directories to minimize storage space on the
system used to generate the package files.

99% of the files likely to be modified by a package are located there.

This is an artificial limit and other parts of the file system may be
included if needed. In order to run the necessary checks, Venus OS
versions need to be available to the managing computer.

Starting with SetupHelper v5.0, it is recommended that a file set exist
for all supported Venus OS versions. This speeds installation time
because it is not necessary to build a file set for a missing Venus OS
version. CommonResources will attempt to create a missing file set,
however it may not be possible to create one if version-dependent
original files don't match a file for other file sets.

**updatePackage** runs through all StockFiles version directories and
all package directories and creates file sets in each package.

Before running this script, you need to edit the FileSets/fileList\*
files to include the files your package will modify. Use full path names
to avoid issues.

File sets created with **updatePackage** will contain ALL replacement
files (or symbolic links to an identical replacement in another file
set) in every file set. This change prevents a problem where a matching
original file could not be found even though a file set does exist for
the current Venus OS version. This resulted in an "incomplete file set"
error and failure to install the package. To clear the error, it was
necessary to reinstall the package and/or the Venus OS firmware. Prior
to v5.0, these symbolic links were missing, and in fact entire file sets
might be missing if they can be created from other Venus OS versions. It
was then necessary for **\_checkFileSets** to fill in the missing files
for the current Venus OS version.

Starting with SetupHelper v6.0, **updatePackage** will relocate all
version-independent files included in the fileListVersionIndependent
list. Prior to v6.0, these files were located in the FileSets directory.
Starting with v6.0, these files are located in the VersionIndependent
file set

**updatePackage** provides an option to relocate alternate original
files (described below) to their new locations: AlternateOriginals. If
AlternateOriginals is already present, the move will be automatic.

**checkFileSets** in CommonResources checks for a COMPLETE flag file
before attempting to fill in a missing file set. This saves time since a
search is not needed for all replacement files. (In previous versions of
SetupHelper, a test was made for all replacement files. This should
succeed but takes time.)

File sets created with **updatePackage** from an older version of
SetupHelper only contain replacement files when the original file
changes between versions. Older file sets will also not contain the
COMPLETE flag file. Also, the package may not contain a file set for the
current Venus OS version. **checkFileSets** will attempt to fill in
missing files or build a missing file set by comparing the original
files in other file sets with the active file installed by Venus OS. If
a match is found, this means the replacement file from the other file
set also applies to the current Venus OS version.

After running this script, you may find file sets populated with
`...NO_REPLACEMENT` files. These indicate where you need to create
replacement files for your packages. You will need to add your changes
to each replacement file in each file set.

Naming:

- the replacement file has the extension of the actual file, e.g.,
PageMain.qml

- the original file adds a .orig extension, e.g, PageMain.qml.orig

- if no original exists, an empty file with the `.NO_ORIG` file will be
created. e.g., `PageMain.qml.NO_ORIG`

Existence of a `.NO_ORG` file after running updateFileSets indicates a
significant problem. What this says is that the replacement file has no
equivalent in a stock system. If the replacement file is the same for
all Venus OS versions, simply remove it from fileList and place the
replacement in the FileSets directory, not in a version directory.

However, if the replacement file differs between Venus OS versions, an
alternate original file needs to be used as a reference. For example, if
you are creating a new file `PageMainEnhanced.qml`, then you can probably
use `PageMain.qml` as the alternate original. Create a file in FileSets
named `PageMainEnhanced.qml.ALT_ORIG` with a single line with the full
path to the alternate original:

`/opt/ victronenergy/qui/qml/PageMain.qml`

Sometimes, a replacement file is needed in SOME versions of Venus OS but
in others. An empty file in the file set will instruct SetupHelper to
use the orig, e.g., `PageMain.qml.USE_ORIGINAL`

**Starting with SetupHelper v6.0**, alternate original files can optionally
be stored in the alternateOriginals directory in the FileSets directory.
This removes clutter from the FileSets directory but the functionality
is the same.

## Blind Install

By far, the easiest way to install SetupHelper is the \"blind install"
which requires no command-line interaction.

1. Download [venus-data.tgz](https://github.com/kwindrem/SetupHelper/raw/main/venus-data.tgz) from the SetupHelper GitHub repo.

    > **Note:** Mac OS and Safari are set by default to unzip packages. The Open
    > "safe" files after downloading (bottom of Safari Preferences
    > General) must be disabled in order to retain the zip file.

2.  copy it to the root of a freshly formatted SD card or USB memory
    stick

3.  place the media in the GX device (Cerbo, CCGX, etc)

4.  reboot the GX device and allow the system to display the GUI

    > If you are running Venus OS v2.90 and beyond you should find the
    > Package Manager menu at the bottom of the Settings menu

5.  you should remove the media at this point. Mechanisms are in place
    to prevent reinstallation, but removal is still a good idea

If you are running Venus OS **prior to v2.90**, perform these *additional
steps*:

6.  Reboot the GX device a second time

7.  WHILE the GX device is booting, **REMOVE THE MEDIA** from the GX device *to prevent the next reboot from starting the process all over again*. Failure to do so could disable reinstalls following a Venus OS firmware update !!!

You should find the Package Manager menu at the bottom of the Settings menu

venus-data.tgz is available here:

https://github.com/kwindrem/SetupHelper/raw/main/venus-data.tgz

> [!CAUTION]
> Prior to v2,90, this mechanism overwrites /data/rcS.local!
>
> If you are using rcS.local to perform boot-time activities,
> /data/rcS.local must be recreated following this \"blind\" install
>
> Note that SetupHelper also uses /data/rcS.local for reinstallation
> following a firmware update so use caution in recreating rcS.local.

## Blind UNINSTALL

A blind uninstall mechanism is provided to recover a system with an
unresponsive GUI (white screen) or no ssh/terminal access. This will run
all package setup scripts to uninstall that package from system files.

The archive for this is named `venus-data.UninstallPackages.tar.gz`.

1.  Copy `venus-data.UninstallPackages.tar.gz` to a USB memory stick or SD
    card

2.  Rename the copy to `venus-data.tar.gz`

3.  Insert the removable media into the GX device

4.  Reboot, wait 2 minutes and reboot a second time

5.  when the system automatically reboots after the second manual one,
    remove the media

You should eventually see the GUI on the local display if there is one
or be able to connect via remote console.

> [!CAUTION]
> Removing media or power cycling the GX device during the
> uninstall, especially if reinstalling firmware could render the system
> unresponsive!
>
> Wait to see the GUI before removing media or power cycling.

In addition to uninstalling all packages, the blind uninstall can
optionally reinstall VenusOS. To do so, include a `.swu` file for the
platform and desired firmware version on the removable media containing
the blind uninstall `venus-data.tar.gz` file.

Note that a firmware update can take several minutes to complete but
will eventually reboot.

When the blind uninstall finishes, `venus-data-tar.gz` file on the
removable media is renamed to `venus-data.UninstallPackages.tar.gz` so
that the blind install will run only once. This renaming is necessary to
prevent a loop where the system uninstalls and reboots.

## System automatic configuration and package installation

It is possible to use SetupHelper to set up a new system based on a
template saved from a working system.

1.  Setup the working system the way you want the new system to behave
    including custom icons,

2.  Perform a Settings backup.

3.  Remove the flash drive from the GX device and plug into a computer
    that has internet access.

4.  Copy venus-data.tgz from the SetupHelper GitHub repo to the same
    flash drive.

5.  If you wish packages to also be installed, copy the package
    -latest.tgz file from those repos as well.

6.  Create SETTINGS_AUTO_RESTORE on the flash drive (contents don\'t
    matter - file may be empty).

7.  Create AUTO_INSTALL_PACKAGES on the flash drive as well.

8.  Place the flash drive into the GX device to be configured and reboot
    (once for v2.90 or twice for prior versions).

9.  REMOVE THE FLASH DRIVE after you have verified that all packages
    have been installed (check Active packages in PackageManager).

## System recovery

It is unlikely, but some users have reported a package install leaving
their system unresponsive or with a nonfuncitonal GUI (white screen). In this case, your options depend on the current state of the system.

Try the following in this order:

- Reboot. This may clear the problem.

- If you have a functioning GUI (either locally or via remote console, see
if you can access the PackageManager menu.

  - If so, you can remove packages one at a time from there.

  - If you find an offending package, post an issue to the GitHub repo for
that package and include:

    - Platform (Cerbo, CCGX, Raspberry PI, etc)
    - Venus OS firmware version
    - Run a Settings backup and post the logs.zip file on the removble media.

  - Remove SetupHelper last since once you do, you loose the PackageManager
menus!

- If you have terminal or ssh access, try running the package setup
scripts to uninstall packages one at a time.

- Try reinstalling Venus OS (firmware):

    - Boot to the previous Venus OS version (in Stored backup firmware),
     then perform a fresh Online firmware update to the latest version or
     use the .swu update via removable media.
    
    - If you have GUI access, use the Settings / Firmware / Stored backup
     firmware menu.
    
    - If you don't have GUI access, you can also switch to the backup
     version from the command line:
    
       `/opt/victronenergy/swupdate-scripts/set-version.sh 2`
    
    - You can also force a firmware update from the command line if you have
      ssh or terminal access:
    
      - For on-line updates:
    
        `/opt/victronenergy/swupdate-scripts/check-swupdate.sh -force -update`
    
      - For updates from removable media:
    
       `/opt/victronenergy/swupdate-scripts/check-swupdate.sh -force -update -offline`

- If PackageManager is still running, it will detect a file named
AUTO_UNINSTALL_PACKAGES on removable media.

  - Create a file of that name (no extension, content unimportant) on a
 USB memory stick or SD card and insert this into the GX device.

  - The system should eventually reboot. In most cases, this should occur
    within 1-2 minutes.

  - After reboot, the system should come up in the stock configuration
    with no packages installed.

  - If the system does not reboot, it is likely PackageManager is no
    longer running, so try other options.

  - Remember to remove the media containing the AUTO_UNINSTALL_PACKAGES
    file to this will be repeated the next time PackageManager runs.

- Perform the Blind uninstall procedure above.

- If you are running on a Raspberry PI, you can reimage the system SD
card.

- If you have a Cerbo, you can reimage it using this procedure:

  <https://community.victronenergy.com/questions/204255/cerbo-gx-bricked-how-to-recover.html>

  > **Note:** this will wipe out all settings and you\'ll need to reconfigure
the GX device from scratch.

The Victron "restore factory default" procedure can be used to will
wipe out all settings. You'll need to reconfigure the GX device from
scratch.

However, it will NOT replace the operating system and Victron
application, nor will it uninstall any packages.

You will most likely be locked out of ssh access since log-in
information and ssh keys are stored in the /data partition which is
completely erased by this procedure.

For this reason, I do not recommend using this as part of your attempt
to recover a system with no GUI.
