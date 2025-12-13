"""
Enums для системы контроля доступа.
"""
from enum import Enum


class UserRole(str, Enum):
    """
    Роли пользователей в системе.
    
    Порядок ролей от высшей к низшей:
    - PROJECT_LEAD: Project Lead - высший уровень управления
    - OPERATIONS_MANAGER: Operations Manager - управление операциями
    - MANAGER: Manager - менеджер
    - SUPERVISOR: Supervisor - супервайзер
    - CLEANER: Cleaner - уборщик
    """
    PROJECT_LEAD = "project_lead"
    OPERATIONS_MANAGER = "operations_manager"
    MANAGER = "manager"
    SUPERVISOR = "supervisor"
    CLEANER = "cleaner"
    
    @classmethod
    def get_display_name(cls, role: "UserRole") -> str:
        """Возвращает отображаемое имя роли."""
        display_names = {
            cls.PROJECT_LEAD: "Project Lead",
            cls.OPERATIONS_MANAGER: "Operations Manager",
            cls.MANAGER: "Manager",
            cls.SUPERVISOR: "Supervisor",
            cls.CLEANER: "Cleaner",
        }
        return display_names.get(role, role.value)
    
    @classmethod
    def get_all_roles(cls) -> list[tuple[str, str]]:
        """Возвращает список всех ролей в формате (value, display_name)."""
        return [
            (cls.PROJECT_LEAD.value, cls.get_display_name(cls.PROJECT_LEAD)),
            (cls.OPERATIONS_MANAGER.value, cls.get_display_name(cls.OPERATIONS_MANAGER)),
            (cls.MANAGER.value, cls.get_display_name(cls.MANAGER)),
            (cls.SUPERVISOR.value, cls.get_display_name(cls.SUPERVISOR)),
            (cls.CLEANER.value, cls.get_display_name(cls.CLEANER)),
        ]

