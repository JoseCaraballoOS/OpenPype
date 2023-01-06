import pyblish.api

from openpype.pipeline import publish
from openpype.lib import (

    is_oiio_supported,
)

from openpype.lib.transcoding import (
    convert_colorspace_for_input_paths,
    get_transcode_temp_directory,
)

from openpype.lib.profiles_filtering import filter_profiles


class ExtractColorTranscode(publish.Extractor):
    """
    Extractor to convert colors from one colorspace to different.
    """

    label = "Transcode color spaces"
    order = pyblish.api.ExtractorOrder + 0.01

    optional = True

    # Configurable by Settings
    profiles = None
    options = None

    def process(self, instance):
        if not self.profiles:
            self.log.warning("No profiles present for create burnin")
            return

        if "representations" not in instance.data:
            self.log.warning("No representations, skipping.")
            return

        if not is_oiio_supported():
            self.log.warning("OIIO not supported, no transcoding possible.")
            return

        colorspace_data = instance.data.get("colorspaceData")
        if not colorspace_data:
            # TODO get_colorspace ??
            self.log.warning("Instance has not colorspace data, skipping")
            return
        source_color_space = colorspace_data["colorspace"]

        host_name = instance.context.data["hostName"]
        family = instance.data["family"]
        task_data = instance.data["anatomyData"].get("task", {})
        task_name = task_data.get("name")
        task_type = task_data.get("type")
        subset = instance.data["subset"]

        filtering_criteria = {
            "hosts": host_name,
            "families": family,
            "task_names": task_name,
            "task_types": task_type,
            "subset": subset
        }
        profile = filter_profiles(self.profiles, filtering_criteria,
                                  logger=self.log)

        if not profile:
            self.log.info((
                "Skipped instance. None of profiles in presets are for"
                " Host: \"{}\" | Families: \"{}\" | Task \"{}\""
                " | Task type \"{}\" | Subset \"{}\" "
            ).format(host_name, family, task_name, task_type, subset))
            return

        self.log.debug("profile: {}".format(profile))

        target_colorspace = profile["output_colorspace"]
        if not target_colorspace:
            raise RuntimeError("Target colorspace must be set")

        repres = instance.data.get("representations") or []
        for idx, repre in enumerate(repres):
            self.log.debug("repre ({}): `{}`".format(idx + 1, repre["name"]))
            if not self.repre_is_valid(repre):
                continue

            new_staging_dir = get_transcode_temp_directory()
            repre["stagingDir"] = new_staging_dir
            files_to_remove = repre["files"]
            if not isinstance(files_to_remove, list):
                files_to_remove = [files_to_remove]
            instance.context.data["cleanupFullPaths"].extend(files_to_remove)

            convert_colorspace_for_input_paths(
                repre["files"],
                new_staging_dir,
                source_color_space,
                target_colorspace,
                self.log
            )

    def repre_is_valid(self, repre):
        """Validation if representation should be processed.

        Args:
            repre (dict): Representation which should be checked.

        Returns:
            bool: False if can't be processed else True.
        """

        if "review" not in (repre.get("tags") or []):
            self.log.info((
                "Representation \"{}\" don't have \"review\" tag. Skipped."
            ).format(repre["name"]))
            return False

        if not repre.get("files"):
            self.log.warning((
                "Representation \"{}\" have empty files. Skipped."
            ).format(repre["name"]))
            return False
        return True
