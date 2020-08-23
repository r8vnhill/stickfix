import unittest

import pytest
from _pytest.tmpdir import TempdirFactory

from bot.database.storage import StickfixDB


@pytest.fixture(scope="session")
def database(tmpdir_factory: TempdirFactory) -> StickfixDB:
    tmpdir_factory.mktemp()
    return StickfixDB("user_test")


def test_batch_operations(database: StickfixDB) -> None:
    assert not database
    assert False


if __name__ == '__main__':
    unittest.main()
