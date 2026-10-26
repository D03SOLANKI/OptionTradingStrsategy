"""
Base AI Agent Class for the 5-Agent Stock Trading System.
Provides standard interfaces for lifecycle management, real-time logging,
transparent mathematical proof recording, inter-agent messaging, and structured reporting.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
import time

from src.agents.transparency_bus import TransparencyBus, AgentStatus, ActivityLogEntry, InterAgentMessage

@dataclass
class AgentReport:
    agent_id: str
    agent_name: str
    objective: str
    timestamp: datetime
    input_data_summary: str
    methodology: str
    calculations_performed: List[Dict[str, Any]]
    findings: List[Dict[str, Any]]
    selected_stocks: List[str]
    rejected_stocks: Dict[str, str] # symbol -> reason
    output_summary: str
    output_payload: Dict[str, Any]
    confidence_assessment: float    # 0.0 to 1.0
    limitations_identified: List[str]
    execution_status: str
    processing_time_ms: float
    errors_and_warnings: List[str]

    def to_markdown(self) -> str:
        lines = [
            f"# Agent Report: {self.agent_name} (`{self.agent_id}`)",
            f"**Execution Timestamp**: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | **Status**: {self.execution_status} | **Processing Latency**: {self.processing_time_ms:.2f} ms",
            f"**Confidence Assessment**: {self.confidence_assessment * 100:.1f}%\n",
            "---",
            "### 1. Objective and Task Scope",
            f"{self.objective}\n",
            "### 2. Input Data Analyzed",
            f"{self.input_data_summary}\n",
            "### 3. Analysis Methodology and Formulas",
            f"{self.methodology}\n",
            "### 4. Mathematical Calculations & Evidence",
        ]
        if self.calculations_performed:
            for calc in self.calculations_performed[:10]: # Top 10 calculations
                lines.append(f"- **{calc.get('symbol', 'Global')}**: `{calc.get('formula')}` -> **{calc.get('result')}** (Inputs: {calc.get('inputs')})")
        else:
            lines.append("- No explicit standalone calculations recorded.")

        lines.extend([
            "\n### 5. Selection and Rejection Breakdown",
            f"- **Selected Candidates ({len(self.selected_stocks)})**: {', '.join(self.selected_stocks) if self.selected_stocks else 'None'}",
            f"- **Rejected Stocks ({len(self.rejected_stocks)})**:"
        ])
        for sym, reason in list(self.rejected_stocks.items())[:10]:
            lines.append(f"  - `{sym}`: {reason}")
        if len(self.rejected_stocks) > 10:
            lines.append(f"  - *(and {len(self.rejected_stocks) - 10} additional stocks rejected)*")

        lines.extend([
            "\n### 6. Output Passed to Downstream Agents",
            f"{self.output_summary}\n",
            "### 7. Limitations & Edge Cases Identified"
        ])
        for lim in self.limitations_identified:
            lines.append(f"- {lim}")

        if self.errors_and_warnings:
            lines.append("\n### 8. Warnings and Diagnostics")
            for w in self.errors_and_warnings:
                lines.append(f"- ⚠️ {w}")

        return "\n".join(lines)

class BaseAgent(ABC):
    """
    Abstract Base Class for all 5 specialized AI Agents.
    Guarantees strict auditability, point-in-time calculation tracking, and verifiable reporting.
    """

    def __init__(self, agent_id: str, agent_name: str, bus: TransparencyBus):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.bus = bus
        self.bus.register_agent(agent_id, agent_name)

        # Internal audit registers
        self.calculations: List[Dict[str, Any]] = []
        self.findings: List[Dict[str, Any]] = []
        self.selected_stocks: List[str] = []
        self.rejected_stocks: Dict[str, str] = {}
        self.warnings_and_errors: List[str] = []
        self.limitations: List[str] = []
        self.start_perf_time: Optional[float] = None
        self.end_perf_time: Optional[float] = None

    def start_execution(self, task: str, stage: str = "Initiation"):
        self.start_perf_time = time.perf_counter()
        self.bus.set_agent_status(self.agent_id, AgentStatus.RUNNING, task=task, stage=stage, progress_pct=0.0)
        self.bus.log(
            agent_id=self.agent_id, task=task, stage=stage, progress_pct=0.0,
            log_type="INFO", message=f"{self.agent_name} started execution: {task}."
        )

    def complete_execution(self, task: str, summary: str):
        self.end_perf_time = time.perf_counter()
        self.bus.set_agent_status(self.agent_id, AgentStatus.COMPLETED, task=task, stage="Finished", progress_pct=100.0)
        self.bus.log(
            agent_id=self.agent_id, task=task, stage="Finished", progress_pct=100.0,
            log_type="INFO", message=f"{self.agent_name} completed task successfully: {summary}."
        )

    def fail_execution(self, task: str, error_msg: str):
        self.end_perf_time = time.perf_counter()
        self.bus.set_agent_status(self.agent_id, AgentStatus.FAILED, task=task, stage="Error", progress_pct=100.0)
        self.warnings_and_errors.append(f"FATAL: {error_msg}")
        self.bus.log(
            agent_id=self.agent_id, task=task, stage="Error", progress_pct=100.0,
            log_type="ERROR", message=f"{self.agent_name} failed: {error_msg}."
        )

    def update_progress(self, task: str, stage: str, progress_pct: float, message: str, symbol: Optional[str] = None):
        self.bus.set_agent_status(self.agent_id, AgentStatus.RUNNING, task=task, stage=stage, progress_pct=progress_pct)
        self.bus.log(
            agent_id=self.agent_id, task=task, stage=stage, progress_pct=progress_pct,
            log_type="INFO", message=message, symbol=symbol
        )

    def record_calculation(
        self,
        symbol: str,
        task: str,
        stage: str,
        progress_pct: float,
        formula: str,
        inputs: Dict[str, Any],
        result: Any,
        interpretation: str
    ):
        calc_entry = {
            "symbol": symbol,
            "formula": formula,
            "inputs": inputs,
            "result": result,
            "interpretation": interpretation,
            "timestamp": datetime.now().isoformat()
        }
        self.calculations.append(calc_entry)
        self.bus.log(
            agent_id=self.agent_id, task=task, stage=stage, progress_pct=progress_pct,
            log_type="CALCULATION", message=f"[{symbol}] {formula} -> {result} ({interpretation})",
            symbol=symbol, details=calc_entry
        )

    def record_decision(
        self,
        symbol: str,
        task: str,
        stage: str,
        progress_pct: float,
        verdict: Literal["SELECTED", "REJECTED", "RANKED", "PASSED"],
        rationale: str,
        criteria: Dict[str, Any]
    ):
        if verdict in ["SELECTED", "RANKED"]:
            if symbol not in self.selected_stocks:
                self.selected_stocks.append(symbol)
                if self.agent_id in self.bus.agent_states:
                    self.bus.agent_states[self.agent_id].shortlisted_count += 1
        elif verdict in ["REJECTED", "PASSED"]:
            self.rejected_stocks[symbol] = rationale
            if self.agent_id in self.bus.agent_states:
                self.bus.agent_states[self.agent_id].rejected_count += 1

        self.bus.log(
            agent_id=self.agent_id, task=task, stage=stage, progress_pct=progress_pct,
            log_type="DECISION", message=f"[{symbol}] Verdict: {verdict}. Reason: {rationale}",
            symbol=symbol, details={"verdict": verdict, "rationale": rationale, "criteria": criteria}
        )

    def record_warning(self, message: str, symbol: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.warnings_and_errors.append(f"WARNING: {message}")
        self.bus.log(
            agent_id=self.agent_id, task="Validation Diagnostic", stage="Warning",
            progress_pct=self.bus.agent_states[self.agent_id].progress_pct if self.agent_id in self.bus.agent_states else 0.0,
            log_type="WARNING", message=message, symbol=symbol, details=details
        )

    def record_error(self, message: str, symbol: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.warnings_and_errors.append(f"ERROR: {message}")
        self.bus.log(
            agent_id=self.agent_id, task="Execution Exception", stage="Error",
            progress_pct=self.bus.agent_states[self.agent_id].progress_pct if self.agent_id in self.bus.agent_states else 0.0,
            log_type="ERROR", message=message, symbol=symbol, details=details
        )

    def send_message(
        self,
        recipient_agent: str,
        message_type: str,
        payload_summary: str,
        payload: Dict[str, Any],
        impact_on_recipient: str
    ) -> InterAgentMessage:
        return self.bus.record_message(
            sender_agent=self.agent_id,
            recipient_agent=recipient_agent,
            message_type=message_type,
            payload_summary=payload_summary,
            payload=payload,
            impact_on_recipient=impact_on_recipient
        )

    @abstractmethod
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Core execution logic must be implemented by each specialized agent."""
        pass

    @abstractmethod
    def generate_report(self) -> AgentReport:
        """Produces verified, structured agent report."""
        pass
