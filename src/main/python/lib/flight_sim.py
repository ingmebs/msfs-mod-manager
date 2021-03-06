import datetime
import functools
import json
import os

from loguru import logger

import lib.config as config
import lib.files as files
import lib.thread as thread


class LayoutError(Exception):
    """Raised when a layout.json file cannot be parsed for a mod."""


class NoLayoutError(Exception):
    """Raised when a layout.json file cannot be found for a mod."""


class ManifestError(Exception):
    """Raised when a manifest.json file cannot be parsed for a mod."""


class NoManifestError(Exception):
    """Raised when a manifest.json file cannot be found for a mod."""


class NoModsError(Exception):
    """Raised when no mods are found in an archive."""


class install_mods_thread(thread.base_thread):
    """Setup a thread to install mods with and not block the main thread."""

    def __init__(self, flight_sim_handle, extracted_archive):
        """Initialize the mod installer thread."""
        logger.debug("Initialzing mod installer thread")
        function = lambda: flight_sim_handle.install_mods(
            extracted_archive,
            update_func=self.activity_update.emit,
        )
        thread.base_thread.__init__(self, function)


class install_mod_archive_thread(thread.base_thread):
    """Setup a thread to install mod archive with and not block the main thread."""

    def __init__(self, flight_sim_handle, mod_archive):
        """Initialize the mod archive installer thread."""
        logger.debug("Initialzing mod archive installer thread")
        function = lambda: flight_sim_handle.install_mod_archive(
            mod_archive,
            update_func=self.activity_update.emit,
            percent_func=self.percent_update.emit,
        )
        thread.base_thread.__init__(self, function)


class uninstall_mod_thread(thread.base_thread):
    """Setup a thread to uninstall mods with and not block the main thread."""

    def __init__(
        self,
        flight_sim_handle,
        folder,
    ):
        """Initialize the mod uninstaller thread."""
        logger.debug("Initialzing mod uninstaller thread")
        function = lambda: flight_sim_handle.uninstall_mod(
            folder,
            update_func=self.activity_update.emit,
        )
        thread.base_thread.__init__(self, function)


class enable_mod_thread(thread.base_thread):
    """Setup a thread to enable mods with and not block the main thread."""

    def __init__(self, flight_sim_handle, folder):
        """Initialize the mod enabler thread."""
        logger.debug("Initialzing mod enabler thread")
        function = lambda: flight_sim_handle.enable_mod(
            folder, update_func=self.activity_update.emit
        )
        thread.base_thread.__init__(self, function)


class disable_mod_thread(thread.base_thread):
    """Setup a thread to disable mods with and not block the main thread."""

    def __init__(self, flight_sim_handle, archive):
        """Initialize the mod disabler thread."""
        logger.debug("Initialzing mod disabler thread")
        function = lambda: flight_sim_handle.disable_mod(
            archive, update_func=self.activity_update.emit
        )
        thread.base_thread.__init__(self, function)


class create_backup_thread(thread.base_thread):
    """Setup a thread to create backup with and not block the main thread."""

    def __init__(self, flight_sim_handle, archive):
        """Initialize the backup creator thread."""
        logger.debug("Initialzing backup creator thread")
        function = lambda: flight_sim_handle.create_backup(
            archive, update_func=self.activity_update.emit
        )
        thread.base_thread.__init__(self, function)


class flight_sim:
    def __init__(self):
        self.sim_packages_folder = ""

    def parse_user_cfg(self, sim_folder=None, filename=None):
        """Parses the given UserCfg.opt file.
        This finds the installed packages path and returns the path as a string."""

        logger.debug("Parsing UserCfg.opt file")

        if sim_folder:
            filename = os.path.join(sim_folder, "UserCfg.opt")

        installed_packages_path = ""

        with open(filename, "r", encoding="utf8") as fp:
            for line in fp:
                if line.startswith("InstalledPackagesPath"):
                    logger.debug("Found InstalledPackagesPath line: {}".format(line))
                    installed_packages_path = line

        # splits the line once, and takes the second instance
        installed_packages_path = installed_packages_path.split(" ", 1)[1].strip()
        # normalize the string
        installed_packages_path = installed_packages_path.strip('"').strip("'")
        # evaluate the path
        installed_packages_path = os.path.realpath(installed_packages_path)

        logger.debug("Path parsed: {}".format(installed_packages_path))

        return installed_packages_path

    def is_sim_folder(self, folder):
        """Returns if FlightSimulator.CFG exists inside the given directory.
        Not a perfect test, but a solid guess."""
        logger.debug("Testing if {} is main MSFS folder".format(folder))
        try:
            status = os.path.isfile(os.path.join(folder, "FlightSimulator.CFG"))
            logger.debug("Folder {} is main MSFS folder: {}".format(folder, status))
            return status
        except Exception:
            logger.exception("Checking sim folder status failed")
            return False

    def is_sim_packages_folder(self, folder):
        """Returns whether the given folder is the FS2020 packages folder.
        Not a perfect test, but a decent guess."""
        # test if the folder above it contains both 'Community' and 'Official'
        logger.debug("Testing if {} is MSFS sim packages folder".format(folder))
        try:
            packages_folders = files.listdir_dirs(folder)
            status = "Official" in packages_folders and "Community" in packages_folders
            logger.debug(
                "Folder {} is MSFS sim packages folder: {}".format(folder, status)
            )
            return status
        except Exception:
            logger.exception("Checking sim packages folder status failed")
            return False

    def find_sim_packages_folder(self):
        """Attempts to automatically locate the install location of FS Packages.
        Returns if reading from config file was successful, and
        returns absolute sim folder path. Otherwise, returns None if it fails."""
        logger.debug("Attempting to automatically locate simulator path")

        # first try to read from the config file
        logger.debug("Trying to find simulator path from config file")
        succeed, value = config.get_key_value(config.SIM_FOLDER_KEY, path=True)
        if succeed and self.is_sim_packages_folder(value):
            logger.debug("Config file sim path found and valid")
            return (True, value)

        # steam detection
        logger.debug("Trying to find simulator path from default Steam install")
        steam_folder = os.path.join(os.getenv("APPDATA"), "Microsoft Flight Simulator")
        if self.is_sim_folder(steam_folder):
            steam_packages_folder = os.path.join(
                self.parse_user_cfg(sim_folder=steam_folder)
            )
            if self.is_sim_packages_folder(steam_packages_folder):
                logger.debug("Steam sim path found and valid")
                return (False, steam_packages_folder)

        # ms store detection
        logger.debug("Trying to find simulator path from default MS Store install")
        ms_store_folder = os.path.join(
            os.getenv("LOCALAPPDATA"),
            "Packages",
            "Microsoft.FlightSimulator_8wekyb3d8bbwe",
            "LocalCache",
        )
        if self.is_sim_folder(ms_store_folder):
            ms_store_packages_folder = os.path.join(
                self.parse_user_cfg(sim_folder=ms_store_folder)
            )
            if self.is_sim_packages_folder(ms_store_packages_folder):
                logger.debug("MS Store sim path found and valid")
                return (False, ms_store_packages_folder)

        # boxed edition detection
        logger.debug("Trying to find simulator path from default boxed edition install")
        boxed_packages_folder = os.path.join(os.getenv("LOCALAPPDATA"), "MSFSPackages")
        if self.is_sim_packages_folder(boxed_packages_folder):
            logger.debug("Boxed edition sim path found and valid")
            return (False, boxed_packages_folder)

        # last ditch steam detection #1
        logger.debug("Trying to find simulator path from last-ditch Steam install #1")
        steam_folder = os.path.join(
            os.getenv("PROGRAMFILES(x86)"),
            "Steam",
            "steamapps",
            "common",
            "MicrosoftFlightSimulator",
        )
        if self.is_sim_folder(steam_folder):
            steam_packages_folder = os.path.join(
                self.parse_user_cfg(sim_folder=steam_folder)
            )
            if self.is_sim_packages_folder(steam_packages_folder):
                logger.debug("Last-ditch #1 Steam sim path found and valid")
                return (False, steam_packages_folder)

        # last ditch steam detection #2
        logger.debug("Trying to find simulator path from last-ditch Steam install #2")
        steam_folder = os.path.join(
            os.getenv("PROGRAMFILES(x86)"),
            "Steam",
            "steamapps",
            "common",
            "Chucky",
        )
        if self.is_sim_folder(steam_folder):
            steam_packages_folder = os.path.join(
                self.parse_user_cfg(sim_folder=steam_folder)
            )
            if self.is_sim_packages_folder(steam_packages_folder):
                logger.debug("Last-ditch #2 Steam sim path found and valid")
                return (False, steam_packages_folder)

        # fail
        logger.warning("Simulator path could not be automatically determined")
        return (False, None)

    def clear_mod_cache(self):
        """Clears the cache of the mod parsing functions."""
        self.parse_mod_layout.cache_clear()
        self.parse_mod_files.cache_clear()
        self.parse_mod_manifest.cache_clear()

    @functools.lru_cache()
    def get_sim_mod_folder(self):
        """Returns the path to the community packages folder inside Flight Simulator.
        Tries to resolve symlinks in every step of the path."""
        # logger.debug("Determining path for sim community packages folder")

        return files.fix_path(
            files.resolve_symlink(os.path.join(self.sim_packages_folder, "Community"))
        )

    @functools.lru_cache()
    def get_sim_official_folder(self):
        """Returns the path to the official packages folder inside Flight Simulator.
        Tries to resolve symlinks in every step of the path."""
        # logger.debug("Determining path for sim official packages folder")

        # path to official packages folder
        official_packages = files.resolve_symlink(
            os.path.join(self.sim_packages_folder, "Official")
        )
        # choose folder inside
        store = files.listdir_dirs(official_packages)[0]

        return files.fix_path(
            files.resolve_symlink(os.path.join(official_packages, store))
        )

    @functools.lru_cache()
    def get_mod_folder(self, folder, enabled):
        """Returns path to mod folder given folder name and enabled status."""
        # logger.debug("Determining path for mod {}, enabled: {}".format(folder, enabled))

        if enabled:
            mod_folder = os.path.join(self.get_sim_mod_folder(), folder)
        else:
            mod_folder = os.path.join(files.get_mod_install_folder(), folder)

        # logger.debug("Final mod path: {}".format(mod_folder))

        return files.fix_path(mod_folder)

    @functools.lru_cache()
    def parse_mod_layout(self, mod_folder):
        """Builds the mod files info as a dictionary. Parsed from the layout.json."""
        logger.debug("Parsing layout for {}".format(mod_folder))

        layout_path = files.resolve_symlink(os.path.join(mod_folder, "layout.json"))

        if not os.path.isfile(layout_path):
            logger.error("No layout.json found")
            raise NoLayoutError(mod_folder)

        try:
            with open(layout_path, "r", encoding="utf8") as f:
                data = json.load(f)
        except Exception as e:
            if hasattr(e, "winerror"):
                logger.exception("WinError: {}".format(e.winerror))
            logger.exception("layout.json could not be parsed")
            raise LayoutError(e)

        return data["content"]

    @functools.lru_cache()
    def parse_mod_files(self, mod_folder):
        """Builds the mod files info as a dictionary. Parsed from the fielsystem."""
        logger.debug("Parsing all mod files for {}".format(mod_folder))

        data = []
        for root, _, files_ in os.walk(mod_folder):
            for file in files_:
                data.append(
                    {
                        "path": os.path.join(os.path.relpath(root, mod_folder), file),
                        "size": os.path.getsize(os.path.join(root, file)),
                    }
                )

        return data

    @functools.lru_cache()
    def parse_mod_manifest(self, mod_folder, enabled=True):
        """Builds the mod metadata as a dictionary. Parsed from the manifest.json."""
        logger.debug("Parsing manifest for {}".format(mod_folder))

        mod_data = {"folder_name": os.path.basename(mod_folder)}
        manifest_path = files.resolve_symlink(os.path.join(mod_folder, "manifest.json"))

        if not os.path.isfile(manifest_path):
            logger.error("No manifest.json found")
            raise NoManifestError(mod_folder)

        try:
            with open(manifest_path, "r", encoding="utf8") as f:
                data = json.load(f)
        except Exception as e:
            if hasattr(e, "winerror"):
                logger.exception("WinError: {}".format(e.winerror))
            logger.exception("manifest.json could not be opened/parsed")
            raise ManifestError(e)

        # manifest data
        mod_data["content_type"] = data.get("content_type", "")
        mod_data["title"] = data.get("title", "")
        mod_data["manufacturer"] = data.get("manufacturer", "")
        mod_data["creator"] = data.get("creator", "")
        mod_data["version"] = data.get("package_version", "")
        mod_data["minimum_game_version"] = data.get("minimum_game_version", "")

        # manifest metadata
        # Windows considering moving/copying a file 'creating' it again,
        # and not modifying contents
        mod_data["time_mod"] = datetime.datetime.fromtimestamp(
            os.path.getctime(manifest_path)
        ).strftime("%Y-%m-%d %H:%M:%S")

        # convience, often helps to just have this included in the returned result
        # and its easier to to do here
        mod_data["enabled"] = enabled
        mod_data["full_path"] = os.path.abspath(mod_folder)

        return mod_data

    def get_game_version(self):
        """Attempts to guess the game's version.
        This is based on the fs-base package and the minimum game version listed."""
        logger.debug("Attempting to determine game version")
        version = "???"
        # build path to fs-base manifest
        fs_base = files.resolve_symlink(
            os.path.join(self.get_sim_official_folder(), "fs-base")
        )
        # parse it if we guessed correct
        if os.path.isdir(fs_base):
            data = self.parse_mod_manifest(fs_base)
            version = data["minimum_game_version"]

        logger.debug("Game version: {}".format(version))
        return version

    def get_mods(self, folders, enabled, progress_func=None, start=0):
        """Returns data a list of mod folders."""

        mods = []
        errors = []

        for i, folder in enumerate(folders):
            if progress_func:
                progress_func(
                    "Loading mods: {}".format(folder),
                    start + i,
                    start + len(folders) - 1,
                )

            try:
                if not os.listdir(folder):
                    # if the mod folder is completely empty, just delete it
                    files.delete_folder(folder)
                    continue
            except FileNotFoundError:
                # in the case of a broken symlink, this will trigger an error
                # unfortuantely, a os.path.exists or isdir will return true
                files.delete_symlink(folder)
                continue

            # parse each mod
            try:
                mods.append(self.parse_mod_manifest(folder, enabled=enabled))
            except (NoManifestError, ManifestError):
                errors.append(folder)

        return mods, errors

    def get_all_mods(self, progress_func=None):
        """Returns data and errors for all mods."""

        enabled_mod_folders = files.listdir_dirs(
            self.get_sim_mod_folder(), full_paths=True
        )
        disabled_mod_folders = files.listdir_dirs(
            files.get_mod_install_folder(), full_paths=True
        )

        for folder in enabled_mod_folders:
            # remove duplicate folders from disabled list if there is a symlink for them
            if files.is_symlink(folder):
                install_folder = os.path.join(
                    files.get_mod_install_folder(), os.path.basename(folder)
                )
                if install_folder in disabled_mod_folders:
                    disabled_mod_folders.remove(install_folder)

        enabled_mod_data, enabled_mod_errors = self.get_mods(
            enabled_mod_folders, enabled=True, progress_func=progress_func
        )
        disabled_mod_data, disabled_mod_errors = self.get_mods(
            disabled_mod_folders,
            enabled=False,
            progress_func=progress_func,
            start=len(enabled_mod_data) - 1,
        )

        return (
            enabled_mod_data + disabled_mod_data,
            enabled_mod_errors + disabled_mod_errors,
        )

    def extract_mod_archive(self, archive, update_func=None):
        """Extracts an archive file into a temp directory and returns the new path."""
        # determine the base name of the archive
        basefilename = os.path.splitext(os.path.basename(archive))[0]

        # build the name of the extracted folder
        extracted_archive = os.path.join(files.TEMP_FOLDER, basefilename)

        # hash the archive
        # archive_hash = files.hash_file(archive, update_func=update_func)

        # check hash of archive versus a possible existing extracted copy
        # if archive_hash == files.read_hash(extracted_archive):
        #    logger.debug("Hashes match, using already extracted copy")
        #    return extracted_archive

        # logger.debug("Hash mismatch, extracting")

        # create a temp directory if it does not exist
        files.create_tmp_folder(update_func=update_func)

        # extract archive
        files.extract_archive(archive, extracted_archive, update_func=update_func)

        # write the hash
        # write_hash(extracted_archive, archive_hash)

        # return
        return extracted_archive

    def determine_mod_folders(self, folder, update_func=None):
        """Walks a directory to find the folder(s) with a manifest.json file in them."""
        logger.debug("Locating mod folders inside {}".format(folder))
        mod_folders = []

        if update_func:
            update_func("Locating mods inside {}".format(folder))

        # check the root folder for a manifest
        if os.path.isfile(os.path.join(folder, "manifest.json")):
            logger.debug("Mod found {}".format(os.path.join(folder)))
            mod_folders.append(os.path.join(folder))

        for root, dirs, _ in os.walk(folder):
            # go through each directory and check for the manifest
            for d in dirs:
                if os.path.isfile(os.path.join(root, d, "manifest.json")):
                    logger.debug("Mod found {}".format(os.path.join(root, d)))
                    mod_folders.append(os.path.join(root, d))

        if not mod_folders:
            logger.error("No mods found")
            raise NoModsError(folder)

        return mod_folders

    def install_mods(self, folder, update_func=None, delete=False, percent_func=None):
        """Extracts and installs a new mod."""
        logger.debug("Installing mod {}".format(folder))

        # determine the mods inside the extracted archive
        mod_folders = self.determine_mod_folders(folder, update_func=update_func)

        installed_mods = []

        for i, mod_folder in enumerate(mod_folders):
            # get the base folder name
            base_mod_folder = os.path.basename(mod_folder)
            install_folder = os.path.join(
                files.get_mod_install_folder(), base_mod_folder
            )
            dest_folder = os.path.join(self.get_sim_mod_folder(), base_mod_folder)

            # copy mod to install dir
            if delete:
                files.move_folder(mod_folder, install_folder, update_func=update_func)
            else:
                files.copy_folder(mod_folder, install_folder, update_func=update_func)

            # create the symlink to the sim
            files.create_symlink(install_folder, dest_folder)

            if percent_func:
                percent_func((i, len(mod_folders)))

            installed_mods.append(base_mod_folder)

        # clear the cache of the mod function
        self.clear_mod_cache()
        # return installed mods list
        return installed_mods

    def install_mod_archive(self, mod_archive, update_func=None, percent_func=None):
        """Extracts and installs a new mod."""
        logger.debug("Installing mod {}".format(mod_archive))
        # extract the archive
        extracted_archive = self.extract_mod_archive(
            mod_archive, update_func=update_func
        )

        return self.install_mods(
            extracted_archive,
            update_func=update_func,
            delete=False,
            percent_func=percent_func,
        )

    def uninstall_mod(self, folder, update_func=None):
        """Uninstalls a mod."""
        logger.debug("Uninstalling mod {}".format(folder))
        # delete folder
        files.delete_folder(folder, update_func=update_func)
        return True

    def enable_mod(self, folder, update_func=None):
        """Creates symlink in flight sim install."""
        logger.debug("Enabling mod {}".format(folder))
        src_folder = self.get_mod_folder(folder, enabled=False)
        dest_folder = self.get_mod_folder(folder, enabled=True)

        # create symlink to sim
        files.create_symlink(src_folder, dest_folder, update_func=update_func)
        return True

    def disable_mod(self, folder, update_func=None):
        """Deletes symlink/dopies mod folder into mod install location."""
        logger.debug("Disabling mod {}".format(folder))
        src_folder = self.get_mod_folder(folder, enabled=True)
        dest_folder = self.get_mod_folder(folder, enabled=False)

        if files.is_symlink(src_folder):
            # delete symlink
            files.delete_symlink(src_folder, update_func=update_func)
        else:
            # move mod to mod install location
            files.move_folder(src_folder, dest_folder, update_func=update_func)

        return True

    def create_backup(self, archive, update_func=None):
        """Creates a backup of all enabled mods."""
        return files.create_archive(
            self.get_sim_mod_folder(), archive, update_func=update_func
        )
