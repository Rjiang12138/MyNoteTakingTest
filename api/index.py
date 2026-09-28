"""Vercel serverless entry point."""
import sys
import os

# Ensure the project root is on sys.path so that `src.xxx` imports work.
# __file__ = api/index.py → root = parent of api/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.main import app

# Vercel's Python runtime looks for a top-level `app` WSGI callable.