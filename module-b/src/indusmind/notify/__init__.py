"""旁路通知（不影响 Module C 回调契约）。"""

from .serverchan import notify_diagnostic_complete, push_serverchan

__all__ = ["notify_diagnostic_complete", "push_serverchan"]
