#!/usr/bin/env python3
"""Run with: python run.py"""
from app import app, init_db

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
