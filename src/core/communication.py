"""Inter-agent communication protocol for Aether system."""

from typing import Any
from datetime import datetime
from src.schemas.outputs import AgentMessage


class CommunicationBroker:
    """Manages inter-agent communication and message passing."""
    
    def __init__(self):
        """Initialize communication broker."""
        self.message_queue: dict[str, list[AgentMessage]] = {}
        self.message_history: list[AgentMessage] = []
    
    async def send_message(
        self,
        sender: str,
        receiver: str,
        message_type: str,
        content: dict
    ) -> AgentMessage:
        """Send a message from one agent to another.
        
        Args:
            sender: Name of sending agent
            receiver: Name of receiving agent
            message_type: Type of message (task, result, feedback, request)
            content: Message content dictionary
        
        Returns:
            Created AgentMessage object
        """
        message = AgentMessage(
            sender=sender,
            receiver=receiver,
            message_type=message_type,
            content=content,
            timestamp=datetime.utcnow()
        )
        
        # Queue message for receiver
        if receiver not in self.message_queue:
            self.message_queue[receiver] = []
        
        self.message_queue[receiver].append(message)
        self.message_history.append(message)
        
        return message
    
    async def get_messages(
        self,
        agent_name: str,
        message_type: str | None = None
    ) -> list[AgentMessage]:
        """Retrieve messages for an agent.
        
        Args:
            agent_name: Name of agent to get messages for
            message_type: Optional filter by message type
        
        Returns:
            List of AgentMessage objects
        """
        messages = self.message_queue.get(agent_name, [])
        
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]
        
        return messages
    
    async def clear_messages(self, agent_name: str) -> None:
        """Clear processed messages for an agent.
        
        Args:
            agent_name: Name of agent to clear messages for
        """
        if agent_name in self.message_queue:
            self.message_queue[agent_name] = []
    
    def get_communication_log(
        self,
        agent_name: str | None = None
    ) -> list[AgentMessage]:
        """Get communication history.
        
        Args:
            agent_name: Optional filter by agent name
        
        Returns:
            List of AgentMessage objects from history
        """
        if agent_name:
            return [
                msg for msg in self.message_history
                if msg.sender == agent_name or msg.receiver == agent_name
            ]
        return self.message_history
    
    def get_statistics(self) -> dict[str, Any]:
        """Get communication statistics.
        
        Returns:
            Dictionary with communication metrics
        """
        agents = set()
        message_types = {}
        
        for msg in self.message_history:
            agents.add(msg.sender)
            agents.add(msg.receiver)
            
            msg_type = msg.message_type
            message_types[msg_type] = message_types.get(msg_type, 0) + 1
        
        return {
            "total_messages": len(self.message_history),
            "unique_agents": len(agents),
            "message_types": message_types,
            "agents": list(agents),
        }
