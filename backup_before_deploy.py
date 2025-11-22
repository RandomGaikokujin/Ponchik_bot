#!/usr/bin/env python3
"""
Вспомогательный скрипт для автоматического экспорта БД перед деплоем на Railway.

Использование:
  python backup_before_deploy.py

Это создаст migration_data.sql с текущими данными из локальной БД,
который затем можно закоммитить и запустить /importdb на Railway.
"""

import os
import sys
import subprocess
from datetime import datetime

def main():
    """Экспортирует БД и создает коммит для сохранения состояния перед деплоем."""
    print("🔄 Запуск экспорта БД перед деплоем...")
    
    # Шаг 1: Экспортируем данные
    try:
        result = subprocess.run([sys.executable, 'export_data.py'], capture_output=True, text=True, timeout=30)
        print(result.stdout)
        if result.stderr:
            print("⚠️  Warnings:", result.stderr)
        if result.returncode != 0:
            print("❌ Ошибка при экспорте данных!")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Экспорт занял слишком долго (>30s)")
        return False
    except Exception as e:
        print(f"❌ Ошибка при запуске экспорта: {e}")
        return False
    
    # Шаг 2: Проверяем, что файл был создан
    if not os.path.exists('migration_data.sql'):
        print("❌ Файл migration_data.sql не был создан!")
        return False
    
    # Шаг 3: Проверяем размер файла
    file_size = os.path.getsize('migration_data.sql')
    print(f"✅ Файл migration_data.sql создан ({file_size} bytes)")
    
    if file_size == 0:
        print("⚠️  Файл пуст! Возможно, БД пуста или произошла ошибка.")
    
    # Шаг 4: Добавляем в git и создаем коммит
    try:
        subprocess.run(['git', 'add', 'migration_data.sql'], check=True, capture_output=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subprocess.run(['git', 'commit', '-m', f'backup: database snapshot before deploy [{timestamp}]'], 
                      capture_output=True, text=True)
        print("✅ Файл добавлен в git")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Git ошибка (возможно, нет изменений): {e}")
        # Не критично - файл все равно есть
    
    print("\n✅ Готово к деплою!")
    print("\n📋 Следующие шаги на Railway:")
    print("  1. После деплоя открыть Railway console (или отправить команду боту)")
    print("  2. Выполнить команду: /importdb")
    print("  3. Бот восстановит данные из migration_data.sql")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
