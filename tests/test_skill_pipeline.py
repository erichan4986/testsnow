import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "utils"))

import pytest
import time
from skill_pipeline import SkillContext, BaseSkill, skill, SkillPipeline
from unittest.mock import patch


class TestSkillContext:
    def test_skill_context_get_set(self):
        ctx = SkillContext()
        ctx.set("key", "value")
        assert ctx.get("key") == "value"

    def test_skill_context_get_fallback(self):
        ctx = SkillContext(input={"in_key": "in_value"}, output={"out_key": "out_value"})
        assert ctx.get("out_key") == "out_value"
        assert ctx.get("in_key") == "in_value"
        assert ctx.get("missing") is None
        assert ctx.get("missing", "default") == "default"


class TestBaseSkill:
    def test_base_skill_subclass(self):
        class DummySkill(BaseSkill):
            name = "dummy"

            def run(self, ctx):
                ctx.set("result", 42)
                return ctx

        skill = DummySkill()
        ctx = SkillContext()
        result = skill.run(ctx)
        assert result.get("result") == 42


class TestSkillDecorator:
    def test_skill_decorator_runs_and_logs_time(self):
        call_times = [0.0, 0.05]  # start, end

        with patch("skill_pipeline.time.time", side_effect=call_times):
            @skill(name="test_skill")
            def my_skill(ctx):
                ctx.set("decorated", True)
                return ctx

            ctx = SkillContext()
            result = my_skill(ctx)
            assert result.get("decorated") is True
            assert "_skill_times" in result.metadata
            assert "test_skill" in result.metadata["_skill_times"]
            assert result.metadata["_skill_times"]["test_skill"] == 0.05


class TestSkillPipeline:
    def test_pipeline_runs_in_order(self):
        @skill()
        def add_ten(ctx):
            val = ctx.get("value", 0)
            ctx.set("value", val + 10)
            return ctx

        @skill()
        def multiply_by_two(ctx):
            val = ctx.get("value", 0)
            ctx.set("value", val * 2)
            return ctx

        pipeline = SkillPipeline([add_ten, multiply_by_two])
        result = pipeline.run(initial_input={"value": 5})
        # (5 + 10) * 2 = 30
        assert result.get("value") == 30

    def test_pipeline_with_base_skill(self):
        class AddSkill(BaseSkill):
            name = "add_skill"

            def __init__(self, amount):
                super().__init__(amount=amount)

            def run(self, ctx):
                val = ctx.get("value", 0)
                ctx.set("value", val + self.amount)
                return ctx

        pipeline = SkillPipeline([AddSkill(5)])
        result = pipeline.run(initial_input={"value": 10})
        assert result.get("value") == 15

    def test_pipeline_add_method(self):
        @skill()
        def step1(ctx):
            return ctx

        @skill()
        def step2(ctx):
            return ctx

        pipeline = SkillPipeline()
        returned = pipeline.add(step1)
        assert returned is pipeline
        pipeline.add(step2)
        assert len(pipeline.skills) == 2

    def test_empty_pipeline(self):
        pipeline = SkillPipeline([])
        result = pipeline.run()
        assert isinstance(result, SkillContext)
        assert result.output == {}
        assert result.input == {}

    def test_skill_raises_exception(self):
        @skill()
        def failing_skill(ctx):
            ctx.set("partial", True)
            raise ValueError("boom")

        ctx = SkillContext()
        with pytest.raises(ValueError, match="boom"):
            failing_skill(ctx)
        assert ctx.get("partial") is True

    def test_context_set_overwrites(self):
        ctx = SkillContext()
        ctx.set("key", "first")
        assert ctx.get("key") == "first"
        ctx.set("key", "second")
        assert ctx.get("key") == "second"

    def test_pipeline_exception_propagates(self):
        @skill()
        def failing_skill(ctx):
            raise ValueError("boom")

        pipeline = SkillPipeline([failing_skill])
        with pytest.raises(ValueError, match="boom"):
            pipeline.run()
