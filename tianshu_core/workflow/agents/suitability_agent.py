from __future__ import annotations

from tianshu_core.models import BlockInput, SuitabilityResult
from tianshu_core.workflow.rules import calculate_suitability


def evaluate_blocks(blocks: list[BlockInput], config: dict) -> list[SuitabilityResult]:
    return [calculate_suitability(block, config) for block in blocks]
