import logging
from pathlib import Path
from typing import Union, Dict, List, TypeVar, Optional

from .content_provider_base import ContentProviderBase
from .root_provider import RootDirectoryProvider
from .addon_provider import AddonProvider
from ..singleton import SingletonMeta

logger = logging.getLogger('ContentManager')

AnyContentDetector = TypeVar('AnyContentDetector', bound='ContentDetectorBase')
AnyContentProvider = TypeVar('AnyContentProvider', bound='ContentProviderBase')


class ContentManager(metaclass=SingletonMeta):
    def __init__(self):
        self.content_providers: Dict[str, AnyContentProvider] = {}
        self.root_provider: Optional[AnyContentProvider] = None
        self.root_path: Optional[Path] = None

        self._path_cache = {}

    def set_root(self, root: Path):
        self.root_path = Path(root)
        self.root_provider = RootDirectoryProvider(self.root_path)
        for addon in (self.root_path / 'addons').iterdir():
            self.content_providers[addon.stem] = AddonProvider(addon)

    def register_content_provider(self, name: str, content_provider: AnyContentProvider):
        if name in self.content_providers:
            return
        self.content_providers[name] = content_provider
        logger.info(f'Registered "{name}" provider for {content_provider.root.stem}')

    def get_relative_path(self, filepath: Path):
        for _, content_provider in self.content_providers.items():
            content_provider: ContentProviderBase
            if filepath.is_absolute() and filepath.is_relative_to(content_provider.root):
                return filepath.relative_to(content_provider.root)
            elif not filepath.is_absolute() and content_provider.find_file(filepath):
                return filepath
        return None

    def glob(self, pattern: str):
        for content_provider in self.content_providers.values():
            yield from content_provider.glob(pattern)
        yield from self.root_provider.glob(pattern)

    def find_file(self, filepath: Union[str, Path], additional_dir=None, extension=None, *, silent=False):

        new_filepath = Path(str(filepath).strip('/\\').rstrip('/\\'))
        if additional_dir:
            new_filepath = Path(additional_dir, new_filepath)
        if extension:
            new_filepath = new_filepath.with_suffix(extension)
        if not silent:
            logger.info(f'Requesting {new_filepath} file')
        for mod, submanager in self.content_providers.items():
            file = (submanager.find_file(new_filepath) or
                    submanager.find_file(new_filepath.with_suffix(new_filepath.suffix + '_b')))
            if file is not None:
                if not silent:
                    logger.debug(f'Found in {mod}!')
                return file
        return (self.root_provider.find_file(new_filepath) or
                self.root_provider.find_file(new_filepath.with_suffix(new_filepath.suffix + '_b')))

    def find_path(self, filepath: Union[str, Path], additional_dir=None, extension=None, *, silent=False):
        new_filepath = Path(str(filepath).strip('/\\').rstrip('/\\'))
        if additional_dir:
            new_filepath = Path(additional_dir, new_filepath)
        if extension:
            new_filepath = new_filepath.with_suffix(extension)
        if not silent:
            logger.info(f'Requesting {new_filepath} file')

        path = self._path_cache.get(new_filepath, -1)
        if path != -1:
            return path
        for mod, submanager in self.content_providers.items():
            file = (submanager.find_path(new_filepath) or
                    submanager.find_path(new_filepath.with_suffix(new_filepath.suffix + '_b')))
            if file is not None:
                if not silent:
                    logger.debug(f'Found in {mod}!')
                self._path_cache[new_filepath] = file
                return file
        file = (self.root_provider.find_path(new_filepath) or
                self.root_provider.find_path(new_filepath.with_suffix(new_filepath.suffix + '_b')))
        self._path_cache[new_filepath] = file
        return file

    def flush_cache(self):
        for cp in self.content_providers.values():
            cp.flush_cache()

    def clean(self):
        self.content_providers.clear()
