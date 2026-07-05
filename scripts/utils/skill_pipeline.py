"""Core abstractions for the Skill Pipeline framework."""

__all__ = ["SkillContext", "BaseSkill", "skill", "SkillPipeline"]

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillContext:
    """Context object passed between skills in a pipeline."""

    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from context. Checks output first, then input."""
        if key in self.output:
            return self.output[key]
        return self.input.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Write a value to output."""
        self.output[key] = value


class BaseSkill(ABC):
    """Abstract base class for pipeline skills."""

    name: str = ""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @abstractmethod
    def run(self, ctx: SkillContext) -> SkillContext:
        """Execute the skill with the given context."""
        pass


def skill(name: Optional[str] = None):
    """Decorator to mark a function as a pipeline skill.

    Args:
        name: Optional skill name. Defaults to the function name.

    Returns:
        A wrapper function that records timing and handles errors.
    """

    def decorator(func: Callable) -> Callable:
        skill_name = name or func.__name__

        def wrapper(ctx: SkillContext) -> SkillContext:
            start_time = time.time()
            try:
                result = func(ctx)
                if result is None:
                    result = ctx
                elapsed = time.time() - start_time
                logger.info(f"Skill '{skill_name}' completed in {elapsed:.4f}s")
                if "_skill_times" not in result.metadata:
                    result.metadata["_skill_times"] = {}
                result.metadata["_skill_times"][skill_name] = elapsed
                return result
            except Exception as e:
                logger.error(f"Skill '{skill_name}' failed: {e}")
                raise

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


class SkillPipeline:
    """Pipeline that runs a sequence of skills."""

    def __init__(self, skills: Optional[List] = None):
        self.skills = skills or []

    def add(self, skill) -> "SkillPipeline":
        """Append a skill and return self for chaining."""
        self.skills.append(skill)
        return self

    def run(self, initial_input: Optional[Dict[str, Any]] = None) -> SkillContext:
        """Run all skills in sequence."""
        ctx = SkillContext(input=initial_input or {})
        for skill in self.skills:
            ctx = self._run_single(skill, ctx)
        return ctx

    def _run_single(self, skill, ctx: SkillContext) -> SkillContext:
        """Dispatch to BaseSkill.run() or call function directly."""
        if isinstance(skill, BaseSkill):
            return skill.run(ctx)
        return skill(ctx)
