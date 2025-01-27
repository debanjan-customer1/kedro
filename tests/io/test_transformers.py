import re
from typing import Any, Callable, Dict

import pytest

from kedro.io import AbstractDataSet, DataCatalog, DataSetNotFoundError
from kedro.io.transformers import AbstractTransformer


class FakeDataSet(AbstractDataSet):
    def __init__(self, data):
        self.log = []
        self.data = data

    def _load(self) -> Any:
        self.log.append(("load", self.data))
        return self.data

    def _save(self, data: Any) -> None:
        self.log.append(("save", data))
        self.data = data

    def _describe(self) -> Dict[str, Any]:
        return {"data": self.data}


class NoopTransformer(AbstractTransformer):
    pass


class FakeTransformer(AbstractTransformer):
    def __init__(self):
        self.log = []

    def load(self, data_set_name: str, load: Callable[[], Any]) -> Any:
        res = load()
        self.log.append(("load", res))
        return res + 1

    def save(self, data_set_name: str, save: Callable[[Any], None], data: Any) -> None:
        self.log.append(("save", data))
        save(data + 1)


@pytest.fixture
def fake_data_set():
    return FakeDataSet(123)


@pytest.fixture
def fake_transformer():
    return FakeTransformer()


@pytest.fixture
def catalog(fake_data_set):
    return DataCatalog({"test": fake_data_set})


class TestTransformers:
    def test_noop(self, fake_data_set, catalog):
        catalog.add_transformer(NoopTransformer())

        catalog.save("test", 42)
        assert catalog.load("test") == 42
        assert fake_data_set.log == [("save", 42), ("load", 42)]

    def test_basic(self, fake_data_set, catalog, fake_transformer):
        catalog.add_transformer(fake_transformer)

        catalog.save("test", 42)
        assert catalog.load("test") == 44
        assert fake_data_set.log == [("save", 43), ("load", 43)]
        assert fake_transformer.log == [("save", 42), ("load", 43)]

    def test_copy(self, fake_data_set, catalog, fake_transformer):
        catalog.add_transformer(fake_transformer)
        catalog = catalog.shallow_copy()

        catalog.save("test", 42)
        assert catalog.load("test") == 44
        assert fake_data_set.log == [("save", 43), ("load", 43)]
        assert fake_transformer.log == [("save", 42), ("load", 43)]

    def test_specific(self, fake_data_set, catalog, fake_transformer):
        catalog.add_transformer(fake_transformer, "test")

        catalog.save("test", 42)
        assert catalog.load("test") == 44
        assert fake_data_set.log == [("save", 43), ("load", 43)]
        assert fake_transformer.log == [("save", 42), ("load", 43)]

    def test_specific_list(self, fake_data_set, catalog, fake_transformer):
        catalog.add_transformer(fake_transformer, ["test"])

        catalog.save("test", 42)
        assert catalog.load("test") == 44
        assert fake_data_set.log == [("save", 43), ("load", 43)]
        assert fake_transformer.log == [("save", 42), ("load", 43)]

    def test_not_found_error(self, fake_transformer):
        catalog = DataCatalog()

        with pytest.raises(DataSetNotFoundError):
            catalog.add_transformer(fake_transformer, "test")

    def test_not_found_error_in_constructor(self):
        with pytest.raises(DataSetNotFoundError):
            DataCatalog(transformers={"test": []})

    def test_all_before_adding(self, fake_data_set, fake_transformer):
        catalog = DataCatalog()
        catalog.add_transformer(fake_transformer)
        catalog.add("test", fake_data_set)

        catalog.save("test", 42)
        assert catalog.load("test") == 44
        assert fake_data_set.log == [("save", 43), ("load", 43)]
        assert fake_transformer.log == [("save", 42), ("load", 43)]

    def test_all_before_copy_and_add(self, fake_data_set, fake_transformer):
        catalog = DataCatalog()
        catalog.add_transformer(fake_transformer)
        catalog = catalog.shallow_copy()
        catalog.add("test", fake_data_set)

        catalog.save("test", 42)
        assert catalog.load("test") == 44
        assert fake_data_set.log == [("save", 43), ("load", 43)]
        assert fake_transformer.log == [("save", 42), ("load", 43)]

    def test_add_bad_transformer(self, catalog):
        with pytest.raises(TypeError, match="not an instance of AbstractTransformer"):
            catalog.add_transformer(object)

    def test_deprecation_warning(self, catalog, fake_transformer):
        pattern = (
            "The transformer API will be deprecated in Kedro 0.18.0."
            "Please use Dataset Hooks to customise the load and save methods."
            "For more information, please visit"
            "https://kedro.readthedocs.io/en/stable/07_extend_kedro/02_hooks.html"
        )
        with pytest.warns(DeprecationWarning, match=re.escape(pattern)):
            catalog.add_transformer(fake_transformer)
