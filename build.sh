#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Ініціалізація бази даних
python -m flask init-db

# Імпорт реальних даних (якщо є файл)
if [ -f "students.csv" ]; then
    python import_real_students.py students.csv
fi
