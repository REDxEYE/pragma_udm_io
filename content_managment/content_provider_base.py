from collections import deque
from io import BytesIO
from pathlib import Path
from typing import Union, Dict, Type


class ContentProviderBase:
    __cache = deque([], maxlen=16)

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def find_file(self, filepath: Union[str, Path]):
        raise NotImplementedError('Implement me!')

    def find_path(self, filepath: Union[str, Path]):
        raise NotImplementedError('Implement me!')

    def glob(self, pattern: str):
        raise NotImplementedError('Implement me!')

    def cache_file(self, filename, file: BytesIO):
        if (filename, file) not in self.__cache:
            self.__cache.append((filename, file))
        return file

    def get_from_cache(self, filename):
        for name, file in self.__cache:
            if name == filename:
                file.seek(0)
                return file

    def flush_cache(self):
        self.__cache.clear()

    @property
    def root(self):
        if self.filepath.is_file():
            return self.filepath.parent
        else:
            return self.filepath

    def _find_file_generic(self, filepath: Union[str, Path], additional_dir=None, extension=None):
        filepath = Path(str(filepath).strip("\\/"))

        new_filepath = filepath
        if additional_dir:
            new_filepath = Path(additional_dir, new_filepath)
        if extension:
            new_filepath = new_filepath.with_suffix(extension)
        new_filepath = self.root / new_filepath
        if new_filepath.exists():
            return new_filepath.open('rb')
        else:
            return None

    def _find_path_generic(self, filepath: Union[str, Path], additional_dir=None,
                           extension=None):
        filepath = Path(str(filepath).strip("\\/"))

        new_filepath = filepath
        if additional_dir:
            new_filepath = Path(additional_dir, new_filepath)
        if extension:
            new_filepath = new_filepath.with_suffix(extension)
        new_filepath = self.root / new_filepath
        if new_filepath.exists():
            return new_filepath
        else:
            return None

    def _glob_generic(self, pattern: str):
        yield from self.root.rglob(pattern)