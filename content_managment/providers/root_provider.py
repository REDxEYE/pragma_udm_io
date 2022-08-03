from pathlib import Path
from typing import Union

from pragma_udm_io.content_managment.providers.icontent_provider import ICachebleContentProvider


class RootDirectoryProvider(ICachebleContentProvider):
    def find_file(self, filepath: Union[str, Path]):
        return self._find_file_generic(filepath)

    def find_path(self, filepath: Union[str, Path]):
        return self._find_path_generic(filepath)

    def glob(self, pattern: str):
        return self._glob_generic(pattern)
