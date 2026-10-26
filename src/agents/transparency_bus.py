"""
Central Transparency and Inter-Agent Communication Bus.
Maintains a complete, non-fabricated, timestamped activity audit trail across all 5 AI Agents:
- Live Agent Lifecycle States (Idle, Running, Completed, Waiting, Failed)
- Progress tracking and current task descriptions
- Real-time data ingestion records and mathematical calculations
- Full rationale for selection, rejection, and ranking
- Verified Inter-Agent Message passing records
- Performance metrics (latency, stocks analyzed, pass rates)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Literal, Callable
import time
import json

class AgentStatus(str, Enum):
    IDLE = "Idle"
    RUNNING = "Running"
    COMPLETED = "Completed"
    WAITING = "Waiting"
    FAILED = "Failed"

@dataclass
class ActivityLogEntry:
    timestamp: datetime
    agent_id: str
    task: str
    stage: str
    progress_pct: float
    log_type: Literal["INFO", "CALCULATION", "DECISION", "COMMUNICATION", "WARNING", "ERROR"]
    symbol: Optional[str]
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "task": self.task,
            "stage": self.stage,
            "progress_pct": self.progress_pct,
            "log_type": self.log_type,
            "symbol": self.symbol,
            "message": self.message,
            "details": self.details
        }

@dataclass
class InterAgentMessage:
    message_id: str
    timestamp: datetime
    sender_agent: str
    recipient_agent: str
    message_type: str
    payload_summary: str
    payload: Dict[str, Any]
    impact_on_recipient: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
            "sender_agent": self.sender_agent,
            "recipient_agent": self.recipient_agent,
            "message_type": self.message_type,
            "payload_summary": self.payload_summary,
            "payload": self.payload,
            "impact_on_recipient": self.impact_on_recipient
        }

@dataclass
class AgentStateSnapshot:
    agent_id: str
    agent_name: str
    status: AgentStatus
    current_task: str
    current_stage: str
    progress_pct: float
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    elapsed_ms: float = 0.0
    stocks_analyzed: int = 0
    shortlisted_count: int = 0
    rejected_count: int = 0
    warnings_count: int = 0
    errors_count: int = 0

class TransparencyBus:
    """
    Central event and transparency dispatcher for the 5-Agent Stock Trading System.
    Zero black-box behavior: every calculation, step, rejection, and message is recorded point-in-time.
    """

    def __init__(self):
        self.logs: List[ActivityLogEntry] = []
        self.messages: List[InterAgentMessage] = []
        self.agent_states: Dict[str, AgentStateSnapshot] = {}
        self.listeners: List[Callable[[ActivityLogEntry], None]] = []
        self._message_counter = 0

    def register_agent(self, agent_id: str, agent_name: str):
        self.agent_states[agent_id] = AgentStateSnapshot(
            agent_id=agent_id,
            agent_name=agent_name,
            status=AgentStatus.IDLE,
            current_task="Initialized",
            current_stage="Awaiting Dispatch",
            progress_pct=0.0
        )

    def subscribe(self, callback: Callable[[ActivityLogEntry], None]):
        """Attach a listener (e.g. for live terminal streaming or web sockets)."""
        self.listeners.append(callback)

    def set_agent_status(
        self,
        agent_id: str,
        status: AgentStatus,
        task: Optional[str] = None,
        stage: Optional[str] = None,
        progress_pct: Optional[float] = None
    ):
        if agent_id in self.agent_states:
            state = self.agent_states[agent_id]
            state.status = status
            if task is not None:
                state.current_task = task
            if stage is not None:
                state.current_stage = stage
            if progress_pct is not None:
                state.progress_pct = progress_pct

            if status == AgentStatus.RUNNING and state.start_time is None:
                state.start_time = time.perf_counter()
            elif status in [AgentStatus.COMPLETED, AgentStatus.FAILED] and state.start_time is not None:
                state.end_time = time.perf_counter()
                state.elapsed_ms = round((state.end_time - state.start_time) * 1000.0, 2)

    def log(
        self,
        agent_id: str,
        task: str,
        stage: str,
        progress_pct: float,
        log_type: Literal["INFO", "CALCULATION", "DECISION", "COMMUNICATION", "WARNING", "ERROR"],
        message: str,
        symbol: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> ActivityLogEntry:
        """
        Appends an immutable, timestamped transparency entry.
        """
        entry = ActivityLogEntry(
            timestamp=datetime.now(),
            agent_id=agent_id,
            task=task,
            stage=stage,
            progress_pct=progress_pct,
            log_type=log_type,
            symbol=symbol,
            message=message,
            details=details or {}
        )
        self.logs.append(entry)

        # Update snapshot stats
        if agent_id in self.agent_states:
            state = self.agent_states[agent_id]
            state.current_task = task
            state.current_stage = stage
            state.progress_pct = progress_pct
            if log_type == "WARNING":
                state.warnings_count += 1
            elif log_type == "ERROR":
                state.errors_count += 1

        # Dispatch to listeners
        for listener in self.listeners:
            try:
                listener(entry)
            except Exception:
                pass

        return entry

    def record_message(
        self,
        sender_agent: str,
        recipient_agent: str,
        message_type: str,
        payload_summary: str,
        payload: Dict[str, Any],
        impact_on_recipient: str = ""
    ) -> InterAgentMessage:
        """
        Records inter-agent communication, payload, and the verified impact on downstream decisions.
        """
        self._message_counter += 1
        msg = InterAgentMessage(
            message_id=f"MSG_{self._message_counter:04d}",
            timestamp=datetime.now(),
            sender_agent=sender_agent,
            recipient_agent=recipient_agent,
            message_type=message_type,
            payload_summary=payload_summary,
            payload=payload,
            impact_on_recipient=impact_on_recipient
        )
        self.messages.append(msg)

        # Log as transparency event
        self.log(
            agent_id=sender_agent,
            task=f"Communicating with {recipient_agent}",
            stage="Inter-Agent Handoff",
            progress_pct=100.0,
            log_type="COMMUNICATION",
            message=f"Sent {message_type} to {recipient_agent}: {payload_summary}",
            details={"recipient": recipient_agent, "impact": impact_on_recipient, "payload_keys": list(payload.keys())}
        )
        return msg

    def get_agent_logs(self, agent_id: str) -> List[ActivityLogEntry]:
        return [entry for entry in self.logs if entry.agent_id == agent_id]

    def get_symbol_logs(self, symbol: str) -> List[ActivityLogEntry]:
        return [entry for entry in self.logs if entry.symbol == symbol]

    def export_telemetry_json(self) -> str:
        data = {
            "generated_at": datetime.now().isoformat(),
            "agent_states": {aid: {
                "name": s.agent_name,
                "status": s.status.value,
                "current_task": s.current_task,
                "current_stage": s.current_stage,
                "progress_pct": s.progress_pct,
                "elapsed_ms": s.elapsed_ms,
                "stocks_analyzed": s.stocks_analyzed,
                "shortlisted_count": s.shortlisted_count,
                "rejected_count": s.rejected_count,
                "warnings": s.warnings_count,
                "errors": s.errors_count
            } for aid, s in self.agent_states.items()},
            "messages_count": len(self.messages),
            "messages": [m.to_dict() for m in self.messages],
            "total_logs": len(self.logs),
            "logs": [l.to_dict() for l in self.logs]
        }
        return json.dumps(data, indent=2)
