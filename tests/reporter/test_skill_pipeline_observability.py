"""Tests for SkillPipeline error isolation and observability."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import pytest

pytestmark = pytest.mark.skip(reason="SkillPipeline observability features not yet implemented")

from skill_pipeline import BaseSkill, SkillContext, SkillPipeline, skill


class FailingSkill(BaseSkill):
    name = "failing_skill"
    input_keys = ["trigger"]
    output_keys = []

    def run(self, ctx: SkillContext) -> SkillContext:
        raise RuntimeError("intentional failure")


class OutputSkill(BaseSkill):
    name = "output_skill"
    input_keys = []
    output_keys = ["value"]

    def run(self, ctx: SkillContext) -> SkillContext:
        ctx.set("value", 42)
        return ctx


@skill(name="func_skill")
def func_skill(ctx: SkillContext) -> SkillContext:
    ctx.set("func_value", 100)
    return ctx


@skill(name="func_fail")
def func_fail(ctx: SkillContext) -> SkillContext:
    raise ValueError("func failure")


def test_strict_mode_raises_on_failure():
    pipeline = SkillPipeline([
        OutputSkill(),
        FailingSkill(),
    ], strict=True)

    with pytest.raises(RuntimeError):
        pipeline.run({})


def test_non_strict_mode_continues_after_failure():
    pipeline = SkillPipeline([
        OutputSkill(),
        FailingSkill(),
        func_skill,
    ], strict=False)

    ctx = pipeline.run({})

    # OutputSkill succeeded
    assert ctx.get("value") == 42

    # FailingSkill failed but pipeline continued
    assert ctx.get("func_value") == 100

    # Check execution log
    log = pipeline.get_execution_log()
    assert len(log) == 3

    assert log[0]["status"] == "success"
    assert log[0]["name"] == "output_skill"
    assert "value" in log[0]["output_keys"]

    assert log[1]["status"] == "failure"
    assert log[1]["name"] == "failing_skill"
    assert "intentional failure" in log[1]["error"]

    assert log[2]["status"] == "success"
    assert log[2]["name"] == "func_skill"


def test_execution_report_format():
    pipeline = SkillPipeline([
        OutputSkill(),
        FailingSkill(),
    ], strict=False)

    pipeline.run({})
    report = pipeline.get_execution_report()

    assert "Pipeline 执行时间线" in report
    assert "output_skill" in report
    assert "failing_skill" in report
    assert "✅" in report
    assert "❌" in report
    assert "intentional failure" in report
    assert "总计:" in report


def test_func_skill_error_isolation():
    pipeline = SkillPipeline([
        OutputSkill(),
        func_fail,
        func_skill,
    ], strict=False)

    ctx = pipeline.run({})
    assert ctx.get("value") == 42
    assert ctx.get("func_value") == 100

    log = pipeline.get_execution_log()
    assert log[1]["status"] == "failure"
    assert log[1]["name"] == "func_fail"
    assert log[2]["status"] == "success"
    assert log[2]["name"] == "func_skill"


def test_empty_pipeline():
    pipeline = SkillPipeline([], strict=False)
    ctx = pipeline.run({"x": 1})
    assert ctx.get("x") == 1
    assert pipeline.get_execution_log() == []


def test_skill_pre_check_skips():
    class SkipSkill(BaseSkill):
        name = "skip_skill"
        input_keys = ["required_key"]
        output_keys = []

        def _pre_check(self, ctx: SkillContext) -> bool:
            return ctx.get("required_key") is not None

        def run(self, ctx: SkillContext) -> SkillContext:
            ctx.set("should_not_appear", True)
            return ctx

    pipeline = SkillPipeline([
        OutputSkill(),
        SkipSkill(),
    ], strict=False)

    ctx = pipeline.run({})
    assert ctx.get("value") == 42
    assert ctx.get("should_not_appear") is None

    log = pipeline.get_execution_log()
    assert log[1]["status"] == "skipped"
    assert log[1]["name"] == "skip_skill"
