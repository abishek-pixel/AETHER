from datetime import datetime
from typing import Dict, List, Any
import json


class ResearchDashboard:
    """Track and display research metrics."""
    
    def __init__(self):
        """Initialize dashboard."""
        self.active_sessions: Dict[str, Dict] = {}
        self.metrics = {
            "total_queries": 0,
            "total_findings": 0,
            "average_confidence": 0.0,
            "average_execution_time": 0.0,
        }
    
    def start_session(self, session_id: str, query: str):
        """Start tracking a session.
        
        Args:
            session_id: Session identifier
            query: Research query
        """
        self.active_sessions[session_id] = {
            "query": query,
            "start_time": datetime.utcnow(),
            "status": "running",
            "findings": 0,
            "agents_executed": [],
        }
    
    def update_session_status(
        self,
        session_id: str,
        status: str,
        agent: str = None
    ):
        """Update session status.
        
        Args:
            session_id: Session identifier
            status: New status
            agent: Agent name if applicable
        """
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["status"] = status
            
            if agent:
                self.active_sessions[session_id]["agents_executed"].append(agent)
    
    def end_session(
        self,
        session_id: str,
        findings_count: int,
        confidence: float
    ):
        """End a session and record metrics.
        
        Args:
            session_id: Session identifier
            findings_count: Number of findings
            confidence: Confidence score
        """
        if session_id not in self.active_sessions:
            return
        
        session = self.active_sessions[session_id]
        session["status"] = "complete"
        session["end_time"] = datetime.utcnow()
        session["findings"] = findings_count
        session["confidence"] = confidence
        
        # Update global metrics
        self.metrics["total_queries"] += 1
        self.metrics["total_findings"] += findings_count
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get current dashboard data.
        
        Returns:
            Dashboard metrics and status
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "active_sessions": len([
                s for s in self.active_sessions.values()
                if s.get("status") == "running"
            ]),
            "completed_sessions": len([
                s for s in self.active_sessions.values()
                if s.get("status") == "complete"
            ]),
            "metrics": self.metrics,
            "recent_queries": [
                s["query"] for s in list(
                    self.active_sessions.values()
                )[-5:]
            ],
        }
    
    def export_session_report(self, session_id: str) -> Optional[Dict]:
        """Export detailed session report.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session report
        """
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        
        return {
            "session_id": session_id,
            "query": session.get("query"),
            "status": session.get("status"),
            "start_time": session.get("start_time").isoformat(),
            "end_time": session.get("end_time").isoformat() if session.get("end_time") else None,
            "duration_seconds": (
                (session.get("end_time") - session.get("start_time")).total_seconds()
                if session.get("end_time") else None
            ),
            "findings": session.get("findings"),
            "confidence": session.get("confidence"),
            "agents_executed": session.get("agents_executed", []),
        }