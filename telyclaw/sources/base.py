"""取数接口

业务层只依赖这个接口。将来接真实 X API 时，只需新增一个实现并在配置里切换，
上层代码一行都不用改。
"""

from abc import ABC, abstractmethod
from datetime import datetime

from core.models import Post


class PostSource(ABC):
    """取数接口：给定账号与时间区间，返回帖子列表"""

    name = "base"

    @abstractmethod
    def fetch(self, handles: list, since: datetime, until: datetime) -> list:
        raise NotImplementedError

    def available(self) -> tuple:
        """返回 (是否可用, 不可用时的人话提示)"""
        return True, ""

    # ---------------------------------------------------------------- 工具
    @staticmethod
    def within(post_time: datetime, since: datetime, until: datetime) -> bool:
        return since <= post_time <= until
