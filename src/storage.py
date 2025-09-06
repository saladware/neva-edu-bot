import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TypeVar, Type, Any, cast
from dataclasses import is_dataclass

T = TypeVar('T')
logger = logging.getLogger(__name__)

class StorageError(Exception):
    """Базовый класс для ошибок хранилища"""
    pass

class Storage:
    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.file_path.exists():
                self.save([])
        except Exception as e:
            raise StorageError(f"Failed to initialize storage: {e}")

    def _serialize(self, obj: Any) -> Any:
        """Сериализация объектов для JSON"""
        if isinstance(obj, datetime):
            return {"_type": "datetime", "value": obj.isoformat()}
        return str(obj)

    def _deserialize(self, obj: Any, cls: Type[T]) -> Any:
        """Десериализация объектов из JSON"""
        if isinstance(obj, dict):
            typed_dict = cast(dict[str, Any], obj)
            # Проверяем, является ли это сериализованным datetime
            if typed_dict.get("_type") == "datetime":
                value = typed_dict.get("value")
                if isinstance(value, str):
                    return datetime.fromisoformat(value)
            
            # Рекурсивно обрабатываем все значения в словаре
            result: dict[str, Any] = {}
            for k, v in typed_dict.items():
                key = str(k)
                result[key] = self._deserialize(v, cls)
            return result
            
        if isinstance(obj, list):
            typed_list = cast(list[Any], obj)
            return [self._deserialize(item, cls) for item in typed_list]
            
        return obj

    def load(self, cls: Type[T]) -> list[T]:
        """Загрузка данных из файла с обработкой ошибок"""
        try:
            if not self.file_path.exists():
                return []
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Десериализуем каждый элемент перед созданием объекта
                return [cls(**self._deserialize(item, cls)) for item in data]
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {self.file_path}: {e}")
            # Создаем резервную копию поврежденного файла
            if self.file_path.exists():
                backup_path = self.file_path.with_suffix(f".corrupted_{datetime.now():%Y%m%d_%H%M%S}.json")
                self.file_path.rename(backup_path)
            return []
        except Exception as e:
            logger.error(f"Failed to load data from {self.file_path}: {e}")
            return []

    def save(self, items: list[T]) -> None:
        """Сохранение данных в файл с обработкой ошибок"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                serializable_items: list[dict[str, Any]] = []
                for item in items:
                    if not is_dataclass(item):
                        raise StorageError(f"Item {item} is not a dataclass")
                    # Используем dict для преобразования в словарь, так как мы уже проверили что это dataclass
                    item_dict = {
                        k: v for k, v in item.__dict__.items()
                        if not k.startswith('_')
                    }
                    serializable_items.append(item_dict)
                
                json.dump(
                    serializable_items,
                    f,
                    ensure_ascii=False,
                    default=self._serialize,
                    indent=2
                )
        except Exception as e:
            raise StorageError(f"Failed to save data: {e}")

    def cleanup_old_backups(self, max_age_days: int = 7) -> None:
        """Удаление старых резервных копий"""
        try:
            now = datetime.now()
            backup_pattern = self.file_path.parent.glob(f"{self.file_path.stem}*.backup.json")
            
            for backup in backup_pattern:
                # Пропускаем файлы, которые не соответствуют нашему формату
                if not backup.name.endswith('.backup.json'):
                    continue
                    
                # Проверяем возраст файла
                age = now - datetime.fromtimestamp(backup.stat().st_mtime)
                if age.days > max_age_days:
                    backup.unlink()
                    logger.info(f"Removed old backup: {backup}")
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
