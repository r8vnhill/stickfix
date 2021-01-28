import os

import pytest

from db.sf_database import StickfixDB

__author__ = "Ignacio Slater Muñoz <ignacio.slater@ug.uchile.cl>"
__version__ = "3.0.0002"

TEST_KEY = "Test Key"
TEST_ELEMENT = {"test": "This is a test text"}


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
    try:
        os.remove(f"TestDB.json")
    except FileNotFoundError:
        pass


def test_item_getset(test_db: StickfixDB):
    """
    Checks if elements are added correctly to the database
    :param test_db: the test database
    """
    assert TEST_KEY not in test_db  # Database shouldn't contain the TEST_KEY element
    assert not test_db[TEST_KEY]

    # (TEST_KEY, TEST_TEXT) is added to the database
    test_db[TEST_KEY] = TEST_ELEMENT
    # Checks if the element was added correctly
    assert TEST_KEY in test_db
    assert TEST_ELEMENT == test_db[TEST_KEY]
