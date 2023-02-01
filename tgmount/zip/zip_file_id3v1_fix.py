import logging
import zipfile

from .zip_file import FileContentZip, ZipFileAsyncThunk, FileContentZipHandle

from .logger import logger as _logger


class FileContentZipFixingId3v1(FileContentZip):
    logger = _logger.getChild("FileContentZipFixingId3v1")
    """ If reader suddenly after opening decides to read from the end """

    max_total_read = 1024 * 128
    distance_to_file_end = 16 * 1024
    read_size = 4096

    def __init__(
        self,
        z_factory: ZipFileAsyncThunk,
        zinfo: zipfile.ZipInfo,
    ):
        super().__init__(z_factory, zinfo)

        self.logger = FileContentZipFixingId3v1.logger.getChild(
            f"{zinfo.filename}", suffix_as_tag=True
        )

    async def read_func(self, handle: FileContentZipHandle, offset, size):
        self.logger.debug(
            f"total_read={self.total_read}, distance_to_end={self.zinfo.file_size - offset}"
        )
        if (
            self.total_read < self.max_total_read
            and (self.zinfo.file_size - offset) < self.distance_to_file_end
            and size == self.read_size
        ):
            self.logger.warning(
                f"FileContentZipFixingId3v1.read_func(offset={offset}, size={size})!!!"
            )
            return b"\x00" * size
        else:
            return await super().read_func(handle, offset, size)
