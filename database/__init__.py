"""
Database package for Lyra Clean.

Exports:
- ISpaceDB: Main database engine
- get_db: Singleton accessor
"""
from .engine import ISpaceDB, get_db, close_db

__all__ = ['ISpaceDB', 'get_db', 'close_db']
