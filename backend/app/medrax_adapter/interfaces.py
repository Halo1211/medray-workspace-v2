from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.schemas import AnalysisResult, ModelTrace


class MedRaxTool(ABC):
    name: str
    task_type: str

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class DemoTool(MedRaxTool):
    def __init__(self, name: str, task_type: str):
        self.name = name
        self.task_type = task_type

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "task_type": self.task_type,
            "status": "fallback",
            "message": "Demo fallback aktif; model asli belum dikonfigurasi.",
        }


class AgentOrchestrator:
    def __init__(self, tools: list[MedRaxTool]):
        self.tools = tools

    async def run(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        for tool in self.tools:
            try:
                results.append(await tool.run(context))
            except Exception as exc:
                results.append(
                    {
                        "tool": tool.name,
                        "task_type": tool.task_type,
                        "status": "failed",
                        "message": str(exc),
                    }
                )
        return results


class OutputNormalizer:
    required_keys = {
        "case_id",
        "input",
        "image_quality",
        "findings",
        "annotations",
        "result_cards",
        "differential_diagnosis",
        "anatomy_route",
        "systematic_reading",
        "report",
        "model_trace",
        "warnings",
    }

    def normalize(self, result: AnalysisResult | dict[str, Any]) -> dict[str, Any]:
        payload = result.model_dump(mode="json") if isinstance(result, AnalysisResult) else dict(result)
        missing = self.required_keys.difference(payload)
        if missing:
            raise ValueError(f"Analysis output missing keys: {', '.join(sorted(missing))}")
        warnings = payload.get("warnings")
        payload["warnings"] = list(dict.fromkeys(str(item) for item in warnings)) if isinstance(warnings, list) else []
        return payload


def demo_medrax_tools() -> list[MedRaxTool]:
    return [
        DemoTool("ImageQualityTool", "quality"),
        DemoTool("GeneralXRayClassifierTool", "classification"),
        DemoTool("GroundingTool", "grounding"),
        DemoTool("ReportGeneratorTool", "report generation"),
    ]
