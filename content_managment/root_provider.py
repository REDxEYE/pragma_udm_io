from pathlib import Path
from typing import Union

from .content_provider_base import ContentProviderBase


class RootDirectoryProvider(ContentProviderBase):
    def find_file(self, filepath: Union[str, Path]):
        return self._find_file_generic(filepath)

    def find_path(self, filepath: Union[str, Path]):
        return self._find_path_generic(filepath)

    def glob(self, pattern: str):
        return self._glob_generic(pattern)
