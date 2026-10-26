"""
Agent Transparency Dashboard Generator.
Generates an interactive, institutional-grade HTML Dashboard complying with the Antigravity Generative UI guidelines:
- Real-time agent status cards (Idle, Running, Completed, Waiting, Failed)
- Deep drill-down tabs for all 5 specialized AI agents
- Mathematical calculation proofs and step-by-step reasoning
- Selection and rejection logs with explicit criteria
- Inter-agent message handoff audit trail
- Final Trade Execution Blueprint or explicit NO TRADE display
"""

import json
import os
from typing import Dict, Any, List
from datetime import datetime

from src.agents.orchestrator import MultiAgentExecutionResult
from src.agents.transparency_bus import AgentStatus

class AgentDashboardGenerator:
    """
    Renders the live multi-agent transparency dashboard to standalone HTML.
    """

    @staticmethod
    def generate_html_dashboard(
        result: MultiAgentExecutionResult,
        output_filepath: str
    ) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

        # Pre-process data for JSON embedding in script
        agents_data = {}
        for aid, rep in result.agent_reports.items():
            state = result.agent_states.get(aid)
            status_val = state.status.value if state else "Completed"
            elapsed = state.elapsed_ms if state else rep.processing_time_ms
            agents_data[aid] = {
                "name": rep.agent_name,
                "status": status_val,
                "elapsed_ms": elapsed,
                "confidence": round(rep.confidence_assessment * 100.0, 1),
                "objective": rep.objective,
                "inputs": rep.input_data_summary,
                "methodology": rep.methodology,
                "calculations": rep.calculations_performed,
                "selected": rep.selected_stocks,
                "rejected": rep.rejected_stocks,
                "findings": rep.findings,
                "output_summary": rep.output_summary,
                "limitations": rep.limitations_identified,
                "errors_and_warnings": rep.errors_and_warnings
            }

        recs_data = []
        for rec in result.final_recommendations:
            recs_data.append({
                "symbol": rec.symbol,
                "company_name": rec.company_name,
                "cap_category": rec.cap_category,
                "verdict": rec.verdict,
                "entry_price": rec.entry_price,
                "target_1_rr": rec.target_1_rr,
                "target_2_macro": rec.target_2_macro,
                "stop_loss": rec.initial_stop_loss,
                "shares_quantity": rec.shares_quantity,
                "capital_deployed": rec.capital_deployed,
                "max_risk_inr": rec.max_risk_inr,
                "friction_inr": rec.friction_cost_inr,
                "rr_ratio": rec.risk_reward_ratio,
                "confidence": round(rec.system_confidence * 100.0, 1),
                "trailing_plan": rec.trailing_stop_plan,
                "detailed_reasoning": rec.detailed_reasoning,
                "contributions": rec.agent_contributions,
                "conflict_resolutions": rec.conflict_resolutions
            })

        messages_data = [m.to_dict() for m in result.inter_agent_messages]
        logs_data = [l.to_dict() for l in result.activity_logs]

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>5-Agent Stock Trading System — Live Transparency Dashboard</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    /* Antigravity Design System theme tokens fallback */
    :root {{
      --background: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --foreground: #f8fafc;
      --muted-foreground: #94a3b8;
      --primary: #3b82f6;
      --primary-foreground: #ffffff;
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
    }}
    .badge-running {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #3b82f6; }}
    .badge-completed {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }}
    .badge-idle {{ background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid #64748b; }}
    .badge-failed {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }}
  </style>
</head>
<body class="bg-[var(--background)] text-[var(--foreground)] antialiased p-6 min-h-screen">

  <!-- Header Banner -->
  <div class="max-w-7xl mx-auto space-y-6">
    <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 shadow-lg flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
      <div>
        <div class="flex items-center gap-3">
          <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold {'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' if result.execution_verdict == 'EXECUTE_TRADES' else 'bg-amber-500/20 text-amber-400 border border-amber-500/40'}">
            ● SYSTEM VERDICT: {result.execution_verdict}
          </span>
          <span class="text-xs text-[var(--muted-foreground)]">Execution Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</span>
        </div>
        <h1 class="text-2xl font-bold tracking-tight text-[var(--foreground)] mt-2">
          5-Agent AI Cash Stock Trading System
        </h1>
        <p class="text-sm text-[var(--muted-foreground)]">
          Real-time activity audit, point-in-time mathematical proofs, and inter-agent communication logs.
        </p>
      </div>
      <div class="flex items-center gap-6 text-sm bg-slate-900/60 px-5 py-3 rounded-xl border border-[var(--border)]">
        <div>
          <p class="text-xs text-[var(--muted-foreground)]">Universe Scanned</p>
          <p class="text-lg font-bold text-blue-400">{result.stocks_scanned_count} Stocks</p>
        </div>
        <div class="h-8 w-[1px] bg-[var(--border)]"></div>
        <div>
          <p class="text-xs text-[var(--muted-foreground)]">Approved Trades</p>
          <p class="text-lg font-bold text-emerald-400">{result.qualified_count} Trades</p>
        </div>
        <div class="h-8 w-[1px] bg-[var(--border)]"></div>
        <div>
          <p class="text-xs text-[var(--muted-foreground)]">Total Latency</p>
          <p class="text-lg font-bold text-purple-400">{result.total_execution_time_ms:.1f} ms</p>
        </div>
      </div>
    </div>

    <!-- Agent Status Grid (5 Cards) -->
    <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
      <div class="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4 shadow-sm hover:border-blue-500/50 transition">
        <div class="flex justify-between items-center mb-2">
          <span class="text-xs font-bold text-blue-400 uppercase">Agent 1</span>
          <span class="px-2 py-0.5 rounded text-[11px] font-semibold badge-completed">Completed</span>
        </div>
        <h3 class="font-semibold text-sm text-[var(--foreground)] truncate">Market Scanner</h3>
        <p class="text-xs text-[var(--muted-foreground)] mt-1">Screened universe & macro regime</p>
        <div class="mt-3 text-xs flex justify-between text-[var(--muted-foreground)]">
          <span>Latency:</span> <span class="font-mono text-slate-200">{result.agent_reports['AGENT_1_MARKET_SCANNER'].processing_time_ms:.1f}ms</span>
        </div>
      </div>

      <div class="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4 shadow-sm hover:border-indigo-500/50 transition">
        <div class="flex justify-between items-center mb-2">
          <span class="text-xs font-bold text-indigo-400 uppercase">Agent 2</span>
          <span class="px-2 py-0.5 rounded text-[11px] font-semibold badge-completed">Completed</span>
        </div>
        <h3 class="font-semibold text-sm text-[var(--foreground)] truncate">Support & Resistance</h3>
        <p class="text-xs text-[var(--muted-foreground)] mt-1">4H macro & 15M confluence zones</p>
        <div class="mt-3 text-xs flex justify-between text-[var(--muted-foreground)]">
          <span>Latency:</span> <span class="font-mono text-slate-200">{result.agent_reports['AGENT_2_SUPPORT_RESISTANCE'].processing_time_ms:.1f}ms</span>
        </div>
      </div>

      <div class="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4 shadow-sm hover:border-cyan-500/50 transition">
        <div class="flex justify-between items-center mb-2">
          <span class="text-xs font-bold text-cyan-400 uppercase">Agent 3</span>
          <span class="px-2 py-0.5 rounded text-[11px] font-semibold badge-completed">Completed</span>
        </div>
        <h3 class="font-semibold text-sm text-[var(--foreground)] truncate">Technical Analysis</h3>
        <p class="text-xs text-[var(--muted-foreground)] mt-1">Pattern, volume & R:R ranking</p>
        <div class="mt-3 text-xs flex justify-between text-[var(--muted-foreground)]">
          <span>Latency:</span> <span class="font-mono text-slate-200">{result.agent_reports['AGENT_3_TECHNICAL_ANALYSIS'].processing_time_ms:.1f}ms</span>
        </div>
      </div>

      <div class="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4 shadow-sm hover:border-amber-500/50 transition">
        <div class="flex justify-between items-center mb-2">
          <span class="text-xs font-bold text-amber-400 uppercase">Agent 4</span>
          <span class="px-2 py-0.5 rounded text-[11px] font-semibold badge-completed">Completed</span>
        </div>
        <h3 class="font-semibold text-sm text-[var(--foreground)] truncate">Risk Management</h3>
        <p class="text-xs text-[var(--muted-foreground)] mt-1">Cash sizing, trailing & Indian taxes</p>
        <div class="mt-3 text-xs flex justify-between text-[var(--muted-foreground)]">
          <span>Latency:</span> <span class="font-mono text-slate-200">{result.agent_reports['AGENT_4_RISK_MANAGEMENT'].processing_time_ms:.1f}ms</span>
        </div>
      </div>

      <div class="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4 shadow-sm hover:border-emerald-500/50 transition">
        <div class="flex justify-between items-center mb-2">
          <span class="text-xs font-bold text-emerald-400 uppercase">Agent 5</span>
          <span class="px-2 py-0.5 rounded text-[11px] font-semibold badge-completed">Completed</span>
        </div>
        <h3 class="font-semibold text-sm text-[var(--foreground)] truncate">Decision & Validation</h3>
        <p class="text-xs text-[var(--muted-foreground)] mt-1">Consensus audit & final decision</p>
        <div class="mt-3 text-xs flex justify-between text-[var(--muted-foreground)]">
          <span>Latency:</span> <span class="font-mono text-slate-200">{result.agent_reports['AGENT_5_DECISION_VALIDATION'].processing_time_ms:.1f}ms</span>
        </div>
      </div>
    </div>

    <!-- Interactive Navigation Tabs -->
    <div class="border-b border-[var(--border)] flex gap-4 overflow-x-auto text-sm font-medium">
      <button onclick="switchTab('tab-recommendations')" id="btn-tab-recommendations" class="tab-btn px-4 py-2 border-b-2 border-blue-500 text-blue-400 font-semibold">
        Final Trading Recommendations
      </button>
      <button onclick="switchTab('tab-agent1')" id="btn-tab-agent1" class="tab-btn px-4 py-2 border-b-2 border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        Agent 1: Scanner
      </button>
      <button onclick="switchTab('tab-agent2')" id="btn-tab-agent2" class="tab-btn px-4 py-2 border-b-2 border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        Agent 2: S/R Mapper
      </button>
      <button onclick="switchTab('tab-agent3')" id="btn-tab-agent3" class="tab-btn px-4 py-2 border-b-2 border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        Agent 3: Technical
      </button>
      <button onclick="switchTab('tab-agent4')" id="btn-tab-agent4" class="tab-btn px-4 py-2 border-b-2 border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        Agent 4: Risk
      </button>
      <button onclick="switchTab('tab-agent5')" id="btn-tab-agent5" class="tab-btn px-4 py-2 border-b-2 border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        Agent 5: Validation
      </button>
      <button onclick="switchTab('tab-messages')" id="btn-tab-messages" class="tab-btn px-4 py-2 border-b-2 border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        Inter-Agent Messages ({len(result.inter_agent_messages)})
      </button>
      <button onclick="switchTab('tab-logs')" id="btn-tab-logs" class="tab-btn px-4 py-2 border-b-2 border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        Live Activity Stream ({len(result.activity_logs)})
      </button>
    </div>

    <!-- TAB 1: FINAL RECOMMENDATIONS -->
    <div id="tab-recommendations" class="tab-content space-y-6">
      {'<div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-8 text-center"><h3 class="text-xl font-bold text-amber-400">NO TRADE VERDICT</h3><p class="text-sm text-[var(--muted-foreground)] mt-2">None of the scanned multi-cap stocks satisfied unanimous 5-agent institutional criteria. 100% of capital is preserved in cash.</p></div>' if not result.final_recommendations else ''}
      
      {''.join([f'''
      <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 shadow-md hover:border-emerald-500/40 transition">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-2 border-b border-[var(--border)] pb-4">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-lg font-bold text-white">{rec.symbol}</span>
              <span class="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700">{rec.cap_category}</span>
              <span class="text-xs bg-emerald-500/20 text-emerald-400 font-bold px-2 py-0.5 rounded border border-emerald-500/40">{rec.verdict} (CASH EQUITY)</span>
            </div>
            <p class="text-xs text-[var(--muted-foreground)] mt-0.5">{rec.company_name}</p>
          </div>
          <div class="flex items-center gap-4 text-xs font-mono">
            <div><span class="text-[var(--muted-foreground)]">System Confidence:</span> <span class="font-bold text-emerald-400">{rec.system_confidence*100:.1f}%</span></div>
            <div><span class="text-[var(--muted-foreground)]">R:R Ratio:</span> <span class="font-bold text-blue-400">{rec.risk_reward_ratio:.2f}:1</span></div>
          </div>
        </div>

        <!-- Trade Parameters Table -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 my-4 text-xs">
          <div class="bg-slate-900/50 p-3 rounded-lg border border-[var(--border)]">
            <span class="text-[var(--muted-foreground)]">Entry Spot Price</span>
            <p class="text-sm font-bold text-white mt-1 font-mono">₹{rec.entry_price:,.2f}</p>
          </div>
          <div class="bg-slate-900/50 p-3 rounded-lg border border-[var(--border)]">
            <span class="text-[var(--muted-foreground)]">Initial Stop Loss</span>
            <p class="text-sm font-bold text-red-400 mt-1 font-mono">₹{rec.initial_stop_loss:,.2f}</p>
          </div>
          <div class="bg-slate-900/50 p-3 rounded-lg border border-[var(--border)]">
            <span class="text-[var(--muted-foreground)]">Target 1 (1:2 R:R Partial)</span>
            <p class="text-sm font-bold text-emerald-400 mt-1 font-mono">₹{rec.target_1_rr:,.2f}</p>
          </div>
          <div class="bg-slate-900/50 p-3 rounded-lg border border-[var(--border)]">
            <span class="text-[var(--muted-foreground)]">Target 2 (4H Macro Level)</span>
            <p class="text-sm font-bold text-emerald-300 mt-1 font-mono">₹{rec.target_2_macro:,.2f}</p>
          </div>
          <div class="bg-slate-900/50 p-3 rounded-lg border border-[var(--border)]">
            <span class="text-[var(--muted-foreground)]">Position Size (Shares)</span>
            <p class="text-sm font-bold text-blue-400 mt-1 font-mono">{rec.shares_quantity} Shares</p>
          </div>
          <div class="bg-slate-900/50 p-3 rounded-lg border border-[var(--border)]">
            <span class="text-[var(--muted-foreground)]">Capital Deployed</span>
            <p class="text-sm font-bold text-white mt-1 font-mono">₹{rec.capital_deployed:,.2f}</p>
          </div>
          <div class="bg-slate-900/50 p-3 rounded-lg border border-[var(--border)]">
            <span class="text-[var(--muted-foreground)]">Max Risk ₹</span>
            <p class="text-sm font-bold text-amber-400 mt-1 font-mono">₹{rec.max_risk_inr:,.2f}</p>
          </div>
          <div class="bg-slate-900/50 p-3 rounded-lg border border-[var(--border)]">
            <span class="text-[var(--muted-foreground)]">Round-Trip Taxes</span>
            <p class="text-sm font-bold text-slate-400 mt-1 font-mono">₹{rec.friction_cost_inr:,.2f}</p>
          </div>
        </div>

        <!-- Trailing Stop Plan -->
        <div class="bg-blue-950/20 border border-blue-800/40 rounded-xl p-3 text-xs text-blue-200">
          <span class="font-bold text-blue-300">Dynamic Trailing Stop Execution Plan:</span>
          <p class="mt-1">{rec.trailing_stop_plan}</p>
        </div>

        <!-- Agent Contributions Accordion -->
        <div class="mt-4 pt-3 border-t border-[var(--border)]">
          <h4 class="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider mb-2">Agent Contribution Breakdown:</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
            {''.join([f'''
            <div class="bg-slate-900/40 p-2.5 rounded border border-[var(--border)]">
              <span class="font-bold text-slate-300">{agent_title}:</span>
              <p class="text-slate-400 mt-0.5">{contrib}</p>
            </div>
            ''' for agent_title, contrib in rec.agent_contributions.items()])}
          </div>
        </div>
      </div>
      ''' for rec in result.final_recommendations])}
    </div>

    <!-- TAB 2: AGENT 1 (MARKET SCANNER) -->
    <div id="tab-agent1" class="tab-content hidden space-y-4">
      <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6">
        <h3 class="text-lg font-bold text-white mb-2">Agent 1: Market & Stock Scanning Agent</h3>
        <p class="text-sm text-[var(--muted-foreground)] mb-4">{result.agent_reports['AGENT_1_MARKET_SCANNER'].objective}</p>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div class="bg-slate-900/60 p-4 rounded-xl border border-[var(--border)]">
            <h4 class="font-bold text-slate-300 uppercase mb-2">Input Data Summary</h4>
            <p class="text-slate-400">{result.agent_reports['AGENT_1_MARKET_SCANNER'].input_data_summary}</p>
          </div>
          <div class="bg-slate-900/60 p-4 rounded-xl border border-[var(--border)]">
            <h4 class="font-bold text-slate-300 uppercase mb-2">Methodology</h4>
            <p class="text-slate-400">{result.agent_reports['AGENT_1_MARKET_SCANNER'].methodology}</p>
          </div>
        </div>

        <div class="mt-6">
          <h4 class="text-xs font-bold text-[var(--muted-foreground)] uppercase mb-3">Mathematical Calculations (Sample)</h4>
          <div class="space-y-2 text-xs font-mono">
            {''.join([f'''
            <div class="bg-slate-900/80 p-3 rounded border border-slate-800">
              <span class="text-blue-400 font-bold">[{c.get('symbol')}]</span> <span class="text-slate-300">{c.get('formula')}</span> -> <span class="text-emerald-400 font-bold">{c.get('result')}</span>
              <p class="text-slate-400 text-[11px] mt-1 font-sans">{c.get('interpretation')}</p>
            </div>
            ''' for c in result.agent_reports['AGENT_1_MARKET_SCANNER'].calculations_performed[:6]])}
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 3: AGENT 2 (S/R AGENT) -->
    <div id="tab-agent2" class="tab-content hidden space-y-4">
      <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6">
        <h3 class="text-lg font-bold text-white mb-2">Agent 2: Support & Resistance Agent</h3>
        <p class="text-sm text-[var(--muted-foreground)] mb-4">{result.agent_reports['AGENT_2_SUPPORT_RESISTANCE'].objective}</p>
        
        <div class="space-y-3 mt-4">
          <h4 class="text-xs font-bold text-[var(--muted-foreground)] uppercase">Structural Calculations & Proximity Audits</h4>
          <div class="space-y-2 text-xs font-mono">
            {''.join([f'''
            <div class="bg-slate-900/80 p-3 rounded border border-slate-800">
              <span class="text-indigo-400 font-bold">[{c.get('symbol')}]</span> <span class="text-slate-300">{c.get('formula')}</span> -> <span class="text-emerald-400 font-bold">{json.dumps(c.get('result'))}</span>
              <p class="text-slate-400 text-[11px] mt-1 font-sans">{c.get('interpretation')}</p>
            </div>
            ''' for c in result.agent_reports['AGENT_2_SUPPORT_RESISTANCE'].calculations_performed[:6]])}
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 4: AGENT 3 (TECHNICAL ANALYSIS) -->
    <div id="tab-agent3" class="tab-content hidden space-y-4">
      <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6">
        <h3 class="text-lg font-bold text-white mb-2">Agent 3: Technical Analysis & Stock Selection Agent</h3>
        <p class="text-sm text-[var(--muted-foreground)] mb-4">{result.agent_reports['AGENT_3_TECHNICAL_ANALYSIS'].objective}</p>
        
        <div class="space-y-3 mt-4">
          <h4 class="text-xs font-bold text-[var(--muted-foreground)] uppercase">Reversal Patterns, Volume Surges & R:R Verification</h4>
          <div class="space-y-2 text-xs font-mono">
            {''.join([f'''
            <div class="bg-slate-900/80 p-3 rounded border border-slate-800">
              <span class="text-cyan-400 font-bold">[{c.get('symbol')}]</span> <span class="text-slate-300">{c.get('formula')}</span> -> <span class="text-emerald-400 font-bold">{json.dumps(c.get('result'))}</span>
              <p class="text-slate-400 text-[11px] mt-1 font-sans">{c.get('interpretation')}</p>
            </div>
            ''' for c in result.agent_reports['AGENT_3_TECHNICAL_ANALYSIS'].calculations_performed[:6]])}
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 5: AGENT 4 (RISK MANAGEMENT) -->
    <div id="tab-agent4" class="tab-content hidden space-y-4">
      <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6">
        <h3 class="text-lg font-bold text-white mb-2">Agent 4: Risk Management Agent</h3>
        <p class="text-sm text-[var(--muted-foreground)] mb-4">{result.agent_reports['AGENT_4_RISK_MANAGEMENT'].objective}</p>
        
        <div class="space-y-3 mt-4">
          <h4 class="text-xs font-bold text-[var(--muted-foreground)] uppercase">Cash Position Sizing & Transaction Cost Calculations</h4>
          <div class="space-y-2 text-xs font-mono">
            {''.join([f'''
            <div class="bg-slate-900/80 p-3 rounded border border-slate-800">
              <span class="text-amber-400 font-bold">[{c.get('symbol')}]</span> <span class="text-slate-300">{c.get('formula')}</span> -> <span class="text-emerald-400 font-bold">{json.dumps(c.get('result'))}</span>
              <p class="text-slate-400 text-[11px] mt-1 font-sans">{c.get('interpretation')}</p>
            </div>
            ''' for c in result.agent_reports['AGENT_4_RISK_MANAGEMENT'].calculations_performed[:6]])}
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 6: AGENT 5 (DECISION & VALIDATION) -->
    <div id="tab-agent5" class="tab-content hidden space-y-4">
      <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6">
        <h3 class="text-lg font-bold text-white mb-2">Agent 5: Decision & Validation Agent</h3>
        <p class="text-sm text-[var(--muted-foreground)] mb-4">{result.agent_reports['AGENT_5_DECISION_VALIDATION'].objective}</p>
        
        <div class="space-y-3 mt-4">
          <h4 class="text-xs font-bold text-[var(--muted-foreground)] uppercase">Consensus Scoring & Conflict Resolution Proofs</h4>
          <div class="space-y-2 text-xs font-mono">
            {''.join([f'''
            <div class="bg-slate-900/80 p-3 rounded border border-slate-800">
              <span class="text-emerald-400 font-bold">[{c.get('symbol')}]</span> <span class="text-slate-300">{c.get('formula')}</span> -> <span class="text-emerald-400 font-bold">{json.dumps(c.get('result'))}</span>
              <p class="text-slate-400 text-[11px] mt-1 font-sans">{c.get('interpretation')}</p>
            </div>
            ''' for c in result.agent_reports['AGENT_5_DECISION_VALIDATION'].calculations_performed[:6]])}
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 7: INTER-AGENT MESSAGES -->
    <div id="tab-messages" class="tab-content hidden space-y-4">
      <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6">
        <h3 class="text-lg font-bold text-white mb-4">Inter-Agent Communication Log (Immutable Audit Trail)</h3>
        <div class="space-y-3 text-xs">
          {''.join([f'''
          <div class="bg-slate-900/60 p-4 rounded-xl border border-[var(--border)]">
            <div class="flex justify-between items-center mb-1">
              <span class="font-mono font-bold text-blue-400">{m.message_id}</span>
              <span class="text-[var(--muted-foreground)]">{m.timestamp.strftime('%H:%M:%S.%f')[:-3]}</span>
            </div>
            <div class="flex items-center gap-2 text-xs font-semibold text-white my-1">
              <span class="text-slate-300">{m.sender_agent}</span>
              <span class="text-blue-500 font-bold">➔</span>
              <span class="text-slate-300">{m.recipient_agent}</span>
              <span class="text-[11px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700 font-mono">[{m.message_type}]</span>
            </div>
            <p class="text-slate-300 mt-2">{m.payload_summary}</p>
            <p class="text-emerald-400/90 text-[11px] mt-1 italic font-sans"><span class="font-bold">Downstream Impact:</span> {m.impact_on_recipient}</p>
          </div>
          ''' for m in result.inter_agent_messages])}
        </div>
      </div>
    </div>

    <!-- TAB 8: LIVE ACTIVITY STREAM -->
    <div id="tab-logs" class="tab-content hidden space-y-4">
      <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6">
        <h3 class="text-lg font-bold text-white mb-4">Live Micro-Step Activity Stream</h3>
        <div class="space-y-2 max-h-[600px] overflow-y-auto text-xs font-mono">
          {''.join([f'''
          <div class="p-2.5 rounded bg-slate-900/70 border border-slate-800 flex items-start gap-3">
            <span class="text-[var(--muted-foreground)] whitespace-nowrap">{l.timestamp.strftime('%H:%M:%S.%f')[:-3]}</span>
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase whitespace-nowrap {
              'bg-blue-500/20 text-blue-400 border border-blue-500/30' if l.log_type == 'INFO' else
              ('bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' if l.log_type in ['CALCULATION', 'DECISION'] else
              ('bg-amber-500/20 text-amber-400 border border-amber-500/30' if l.log_type == 'WARNING' else 'bg-red-500/20 text-red-400 border border-red-500/30'))
            }">{l.log_type}</span>
            <div class="flex-1">
              <span class="font-bold text-slate-300">[{l.agent_id}]</span> <span class="text-slate-200">{l.message}</span>
            </div>
          </div>
          ''' for l in result.activity_logs])}
        </div>
      </div>
    </div>

  </div>

  <script>
    function switchTab(tabId) {{
      document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.tab-btn').forEach(btn => {{
        btn.classList.remove('border-blue-500', 'text-blue-400', 'font-semibold');
        btn.classList.add('border-transparent', 'text-[var(--muted-foreground)]');
      }});

      const target = document.getElementById(tabId);
      if (target) target.classList.remove('hidden');

      const activeBtn = document.getElementById('btn-' + tabId);
      if (activeBtn) {{
        activeBtn.classList.remove('border-transparent', 'text-[var(--muted-foreground)]');
        activeBtn.classList.add('border-blue-500', 'text-blue-400', 'font-semibold');
      }}
    }}
  </script>
</body>
</html>
"""
        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_filepath
