from typing import Optional, Type

from ktem.db.models import engine
from sqlmodel import Session, select
from theflow.settings import settings
from theflow.utils.modules import import_dotted_string

from .base import BaseIndex
from .models import Index


class IndexManager:
    """Manage the application indices

    The index manager is responsible for:
        - Managing the range of possible indices and their extensions
        - Each actual index built by user

    Attributes:
        - indices: list of indices built by user
    """

    def __init__(self, app):
        self._app = app
        self._indices = []
        self._index_types: dict[str, Type[BaseIndex]] = {}


    @property
    def index_types(self) -> dict:
        """List the index_type of the index"""
        return self._index_types

    def build_index(self, name: str, config: dict, index_type: str):
        """Build the index

        Building the index simply means recording the index information into the
        database and returning the index object.

        Args:
            name (str): the name of the index
            config (dict): the config of the index
            index_type (str): the type of the index
            id (int, optional): the id of the index. If None, the id will be
                generated automatically. Defaults to None.

        Returns:
            BaseIndex: the index object
        """

        with Session(engine) as sess:
            entry = Index(name=name, config=config, index_type=index_type)
            sess.add(entry)
            sess.commit()
            sess.refresh(entry)

            try:
                # build the index
                index_cls = import_dotted_string(index_type, safe=False)
                index = index_cls(app=self._app, id=entry.id, name=name, config=config)
                index.on_create()

                # update the entry
                entry.config = index.config
                sess.commit()
            except Exception as e:
                sess.delete(entry)
                sess.commit()
                raise ValueError(f'Cannot create index "{name}": {e}')

        return index

    def update_index(self, id: int, name: str, config: dict):
        """Update the index information

        Args:
            id: the id of the index
            name: the new name of the index
            config: the new config of the index
        """
        with Session(engine) as sess:
            entry = sess.get(Index, id)
            if entry is None:
                raise ValueError(f"Index with id {id} does not exist")

            entry.name = name
            entry.config = config
            sess.commit()

        for index in self._indices:
            if index.id == id:
                index.name = name
                index.config = config
                break

    def start_index(self, id: int, name: str, config: dict, index_type: str):
        """Start the index

        Args:
            id (int): the id of the index
            name (str): the name of the index
            config (dict): the config of the index
            index_type (str): the type of the index
        """
        index_cls = import_dotted_string(index_type, safe=False)
        index = index_cls(app=self._app, id=id, name=name, config=config)
        index.on_start()

        self._indices.append(index)
        return index

    def delete_index(self, id: int):
        """Delete the index from the database"""
        index: Optional[BaseIndex] = None
        for _ in self._indices:
            if _.id == id:
                index = _
                break

        if index is None:
            raise ValueError(
                "Index does not exist. If you have already removed the index, "
                "please restart to reflect the changes."
            )

        try:
            try:
                # clean up
                index.on_delete()
            except Exception as e:
                print(f"Error while deleting index {index.name}: {e}")

            # remove from database
            with Session(engine) as sess:
                item = sess.query(Index).filter_by(id=id).first()
                sess.delete(item)
                sess.commit()

            new_indices = [_ for _ in self._indices if _.id != id]
            self._indices = new_indices
        except Exception as e:
            raise ValueError(f"Cannot delete index {index.name}: {e}")

    def load_index_types(self):
        """Load the supported index types"""
        self._index_types = {}

        # built-in index types
        from .file.index import FileIndex

        for index in [FileIndex]:
            self._index_types[f"{index.__module__}.{index.__qualname__}"] = index

        # developer-defined custom index types
        for index_str in settings.KH_INDEX_TYPES:
            cls: Type[BaseIndex] = import_dotted_string(index_str, safe=False)
            self._index_types[f"{cls.__module__}.{cls.__qualname__}"] = cls

    def exists(self, id: Optional[int] = None, name: Optional[str] = None) -> bool:
        """Check if the index exists

        Args:
            id (int): the id of the index

        Returns:
            bool: True if the index exists, False otherwise
        """
        if id:
            with Session(engine) as sess:
                index = sess.get(Index, id)
                return index is not None

        if name:
            with Session(engine) as sess:
                index = sess.exec(select(Index).where(Index.name == name)).one_or_none()
                return index is not None

        return False

    def on_application_startup(self):
        """This method is called by the base application when the application starts

        Load the index from database
        """
        self.load_index_types()

        # ✅ NEW: Clean up old indices that are no longer in configuration
        self._cleanup_obsolete_indices()

        # Build new indices from configuration
        for index in settings.KH_INDICES:
            if not self.exists(name=index["name"]):
                print(f"🔨 Building new index: {index['name']}")
                self.build_index(**index)

        # Start indices from database
        with Session(engine) as sess:
            index_defs = sess.exec(select(Index))
            for index_def in index_defs:
                print(f"🚀 Starting index: {index_def.name} (ID: {index_def.id})")
                self.start_index(**index_def.model_dump())


    def _cleanup_obsolete_indices(self):
        """Clean up indices that exist in database but not in current configuration"""

        # Get list of current configured index names
        configured_names = [idx["name"] for idx in settings.KH_INDICES]

        # Check database for indices not in current configuration
        with Session(engine) as sess:
            all_db_indices = sess.exec(select(Index)).all()
            obsolete_indices = []

            for db_index in all_db_indices:
                if db_index.name not in configured_names:
                    obsolete_indices.append(db_index)
                    print(f"🗑️ Found obsolete index: {db_index.name} (ID: {db_index.id})")

            # Delete obsolete indices
            if obsolete_indices:
                print(f"🗑️ Deleting {len(obsolete_indices)} obsolete indices...")
                for obsolete_index in obsolete_indices:
                    print(f"   - Deleting: {obsolete_index.name}")
                    sess.delete(obsolete_index)
                sess.commit()
                print("✅ Obsolete indices cleaned up")
            else:
                print("✅ No obsolete indices found")

    @property
    def indices(self):
        return self._indices

    def info(self):
        return {index.id: index for index in self._indices}
