import unittest

import pytest

from bot.database.storage import StickfixDB


@pytest.fixture
def database() -> StickfixDB:
    return StickfixDB("user_test")


def test_batch_operations(database: StickfixDB) -> None:
    assert not database
    assert False


if __name__ == '__main__':
    unittest.main()
