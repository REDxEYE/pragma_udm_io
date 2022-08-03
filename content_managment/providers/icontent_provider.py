import abc
from abc import ABC
from collections import deque
from io import BytesIO
from pathlib import Path
from typing import Union, Optional, io, Deque, Tuple, TextIO

from pragma_udm_io.utils.file_utils import IBuffer


class IContentProvider(abc.ABC):

    def __init__(self, filepath: Path):
        self.filepath = filepath
        if self.filepath.is_file():
            self.root = self.filepath.parent
        else:
            self.root = self.filepath

    def find_file(self, filepath: Union[str, Path]):
        raise NotImplementedError('Implement me!')

    def find_path(self, filepath: Union[str, Path]):
        raise NotImplementedError('Implement me!')

    def glob(self, pattern: str):
        raise NotImplementedError('Implement me!')

    def _find_file_generic(self, filepath: Union[str, Path], binary_mode=True) -> BytesIO | TextIO:
        if file_path := self._find_path_generic(filepath):
            return file_path.open('r' + ('b' if binary_mode else ''))

    def _find_path_generic(self, filepath: Union[str, Path]) -> Optional[Path]:
        filepath = self.root / Path(str(filepath).strip("\\/"))
        if filepath.exists():
            return filepath
        else:
            return None

    def _glob_generic(self, pattern: str):
        yield from self.root.rglob(pattern)


class ICachebleContentProvider(IContentProvider, ABC):
    __cache: Deque[Tuple[str, BytesIO]] = deque([], maxlen=16)

    def cache_file(self, filename, file: BytesIO):
        if (filename, file) not in self.__cache:
            self.__cache.append((filename, file))
        return file

    def get_from_cache(self, filename) -> BytesIO:
        for name, file in self.__cache:
            if name == filename:
                file.seek(0)
                return file

    def flush_cache(self):
        self.__cache.clear()
