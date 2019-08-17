import os

import pytest

from db.sf_database import StickfixDB

TEST_KEY = "Test Key"
TEST_TEXT = "This is a test text"


@pytest.fixture
def test_db() -> StickfixDB:
    """
    :return: a test db
    """
    return StickfixDB("TestDB")


@pytest.fixture(autouse=True)
def cleanup():
    """
    Deletes the files created by the tests
    """
    for ext in ("bak", "dat", "dir"):
        try:
            os.remove(f"TestDB.{ext}")
        except FileNotFoundError:
            pass


def test_item_getset(test_db: StickfixDB):
    """
    Checks if elements are added correctly to the database
    :param test_db: the test database
    """
    assert TEST_KEY not in test_db  # Database shouldn't contain the TEST_KEY element
    assert not test_db.get_item(TEST_KEY)

    # (TEST_KEY, TEST_TEXT) is added to the database
    test_db.add_item(TEST_KEY, TEST_TEXT)

    # Checks if the element was added correctly
    assert TEST_KEY in test_db
    assert test_db.get_item(TEST_KEY) == TEST_TEXT  # We assume that get_item works
