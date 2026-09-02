"""
LangGraph Agent Orchestrator

Orchestrates the conversation flow using LangGraph.
Integrates with memory, intent detection, property matching, and appointment booking.
Includes tool definitions for external services (calendar, email, CRM, n8n).
"""

from __future__ import annotations

from typing import TypedDict, Any, Optional
import json
from datetime import datetime
import uuid

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END

from app.config import settings
from app.services.call_intent import detect_intent
from app.services.lead_memory import lead_memory
from app.services.session_state import session_state
from app.services import profile_extraction
from app.services.property_matcher import match_properties
from app.services.n8n_webhook import n8n_publisher
from app.services.appointment_service import create_appointment_record
from app.services.calendar_service import create_calendar_event
from app.services.email_service import send_booking_email
from app.services.crm_service import log_call_and_booking, create_crm_contact


class AgentState(TypedDict):
    """State passed through the LangGraph workflow."""
    session_id: str
    transcript: str
    messages: list
    profile: dict
    intent: str
    recommendations: list
    appointment_details: Optional[dict]
    next_step: str
    confidence: float
    lead_id: Optional[str] = None


# ============================================================================
# Tool Definitions for LangGraph
# ============================================================================

@tool("book_property_visit")
def book_property_visit(
    client_name: str,
    client_phone: str,
    property_id: str,
    property_title: str,
    scheduled_at: str,
    employee_email: Optional[str] = None,
) -> dict:
    """Book a property visit appointment.
    
    Args:
        client_name: Name of the client
        client_phone: Phone number of the client
        property_id: ID of the property
        property_title: Title/name of the property
        scheduled_at: ISO format datetime for the visit
        employee_email: Email of the assigned agent/employee
        
    Returns:
        Confirmation with appointment details
    """
    try:
        appointment = create_appointment_record({
            "client_name": client_name,
            "client_phone": client_phone,
            "property_id": property_id,
            "property_title": property_title,
            "scheduled_at": scheduled_at,
            "employee_email": employee_email,
        })
        
        # Create calendar event
        calendar_result = create_calendar_event(
            client_name=client_name,
            property_title=property_title,
            scheduled_at=scheduled_at,
            employee_email=employee_email,
        )
        
        # Send confirmation email
        email_result = send_booking_email(
            client_name=client_name,
            property_title=property_title,
            employee_email=employee_email,
        )
        
        return {
            "status": "booked",
            "appointment_id": appointment.get("appointment_id"),
            "client_name": client_name,
            "property_title": property_title,
            "scheduled_at": scheduled_at,
            "calendar_status": calendar_result.get("status"),
            "email_status": email_result.get("status"),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "client_name": client_name,
            "property_title": property_title,
        }


@tool("match_properties_for_profile")
def match_properties_for_profile(profile: dict) -> list:
    """Match properties based on customer profile.
    
    Args:
        profile: Customer profile with budget, location, property type, etc.
        
    Returns:
        List of matching properties
    """
    return match_properties(profile)


@tool("create_crm_lead")
def create_crm_lead_contact(
    client_name: str,
    phone: str,
    email: Optional[str] = None,
    lead_id: Optional[str] = None,
) -> dict:
    """Create a contact/lead in CRM system.
    
    Args:
        client_name: Name of the client
        phone: Phone number
        email: Email address
        lead_id: Internal lead ID for linking
        
    Returns:
        CRM contact creation response
    """
    return create_crm_contact(
        client_name=client_name,
        email=email,
        phone=phone,
        lead_id=lead_id,
    )


@tool("publish_to_n8n")
def publish_event_to_n8n(event_type: str, payload: dict) -> dict:
    """Publish an event to n8n for workflow automation.
    
    Args:
        event_type: Type of event (lead_created, appointment_scheduled, etc.)
        payload: Event data to publish
        
    Returns:
        Publication status
    """
    return n8n_publisher.publish(event_type, payload)


@tool("get_lead_memory")
def get_lead_memory_context(lead_id: str) -> dict:
    """Retrieve lead memory and context from previous interactions.
    
    Args:
        lead_id: The lead identifier
        
    Returns:
        Lead memory including profile, transcript history, and intent
    """
    return lead_memory.get_lead(lead_id) or {"lead_id": lead_id, "status": "new_lead"}


class VoiceAgentOrchestrator:
    """Orchestrates voice call handling using LangGraph."""

    def __init__(self):
        self.llm = None
        self.llm_with_tools = None

        # Define available tools
        self.tools = [
            book_property_visit,
            match_properties_for_profile,
            create_crm_lead_contact,
            publish_event_to_n8n,
            get_lead_memory_context,
        ]

        if settings.openai_api_key:
            try:
                self.llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=settings.openai_api_key,
                    temperature=0.3,
                )
                self.llm_with_tools = self.llm.bind_tools(self.tools)
            except Exception as e:
                print(f"[orchestrator] Could not initialize the LLM client: {e}")
        else:
            print(
                "[orchestrator] OPENAI_API_KEY is not set, the orchestrator will run the "
                "intent/profile/booking pipeline without generating an LLM reply."
            )

        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("intent_detection", self._intent_detection_node)
        workflow.add_node("profile_extraction", self._profile_extraction_node)
        workflow.add_node("property_recommendation", self._property_recommendation_node)
        workflow.add_node("appointment_handler", self._appointment_handler_node)
        workflow.add_node("response_generation", self._response_generation_node)
        workflow.add_node("session_completion", self._session_completion_node)

        # Add edges
        workflow.add_edge("intent_detection", "profile_extraction")
        workflow.add_edge("profile_extraction", "property_recommendation")
        workflow.add_conditional_edges(
            "property_recommendation",
            self._should_book_appointment,
            {
                True: "appointment_handler",
                False: "response_generation",
            },
        )
        workflow.add_edge("appointment_handler", "response_generation")
        workflow.add_edge("response_generation", "session_completion")
        workflow.add_edge("session_completion", END)

        workflow.set_entry_point("intent_detection")
        return workflow.compile()

    def _intent_detection_node(self, state: AgentState) -> AgentState:
        """Detect user intent from transcript."""
        intent = detect_intent(state["transcript"])
        state["intent"] = intent if isinstance(intent, str) else intent.get("intent", "unknown")
        state["confidence"] = intent.get("confidence", 0.5) if isinstance(intent, dict) else 0.5
        return state

    def _profile_extraction_node(self, state: AgentState) -> AgentState:
        """Extract lead profile from transcript and merge into session state.

        session_state.record_turn() does the extraction and merge in one
        place, so this node just needs to run it and read the result back,
        instead of extracting and merging again with its own rules.
        """
        session_state_data = session_state.record_turn(state["session_id"], state["transcript"])
        state["profile"] = session_state_data.get("profile", profile_extraction.empty_profile())
        return state

    def _property_recommendation_node(self, state: AgentState) -> AgentState:
        """Generate property recommendations."""
        recommendations = match_properties(state["profile"])
        state["recommendations"] = recommendations

        # Publish events for n8n
        for prop in recommendations[:3]:  # Top 3 recommendations
            n8n_publisher.property_recommended(
                session_id=state["session_id"],
                property_id=prop.get("property_id", "unknown"),
                property_name=prop.get("name", prop.get("title", "Unknown")),
                city=prop.get("city", ""),
                area=prop.get("area", ""),
            )

        return state

    def _should_book_appointment(self, state: AgentState) -> bool:
        """Determine if user wants to book an appointment."""
        intent = state["intent"].lower()
        return "book" in intent or "appointment" in intent or "visit" in intent

    def _appointment_handler_node(self, state: AgentState) -> AgentState:
        """Handle appointment booking."""
        if state["recommendations"]:
            top_property = state["recommendations"][0]
            state["appointment_details"] = {
                "property_id": top_property.get("property_id", "unknown"),
                "property_name": top_property.get("name", top_property.get("title", "Property")),
                "client_name": state["profile"].get("customer_name") or "Customer",
                "scheduled_at": "pending_confirmation",
                "status": "awaiting_confirmation",
            }
            state["next_step"] = "confirm_appointment_time"

            # Publish appointment event
            n8n_publisher.appointment_scheduled(
                appointment_id=f"apt_{state['session_id']}",
                lead_id=state["session_id"],
                property_name=state["appointment_details"]["property_name"],
                client_name=state["appointment_details"]["client_name"],
                scheduled_at="pending",
            )
        else:
            state["next_step"] = "no_matching_properties"

        return state

    def _response_generation_node(self, state: AgentState) -> AgentState:
        """Generate LLM response with tool availability."""
        system_prompt = """You are a professional real estate sales assistant. 
        You help customers find properties that match their needs.
        Be concise, helpful, and professional. Respond in Urdu or English as appropriate.
        
        You have access to tools to:
        - Match properties based on customer needs
        - Book property visits
        - Create/update CRM leads
        - Remember customer context from previous interactions
        - Publish events to automation workflows
        
        Use these tools when appropriate to help the customer."""

        context = f"""
        Customer Profile:
        - Budget: {state['profile'].get('budget', 'Not specified')}
        - City: {state['profile'].get('city', 'Not specified')}
        - Area: {state['profile'].get('area', 'Not specified')}
        - Property Type: {state['profile'].get('property_type', 'Not specified')}
        - Purpose: {state['profile'].get('purpose', 'Not specified')}
        
        Detected Intent: {state['intent']}
        Confidence: {state['confidence']:.2%}
        
        Recommendations: {len(state['recommendations'])} properties found
        """

        messages = [
            SystemMessage(content=system_prompt + "\n\n" + context),
            HumanMessage(content=state["transcript"]),
        ]

        if self.llm_with_tools is None:
            state["messages"] = messages
            return state

        try:
            # Use LLM with tools
            response = self.llm_with_tools.invoke(messages)
            state["messages"] = messages + [response]
            
            # Process tool calls if any
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    result = self._execute_tool(tool_call)
                    state["messages"].append({
                        "type": "tool_result",
                        "tool_call_id": tool_call.get("id"),
                        "content": json.dumps(result),
                    })
        except Exception as e:
            state["messages"] = messages
            print(f"LLM error: {e}")

        return state

    def _execute_tool(self, tool_call: dict) -> dict:
        """Execute a tool call."""
        tool_name = tool_call.get("name")
        args = tool_call.get("args", {})
        
        try:
            if tool_name == "book_property_visit":
                return book_property_visit(**args)
            elif tool_name == "match_properties_for_profile":
                return match_properties_for_profile(**args)
            elif tool_name == "create_crm_lead":
                return create_crm_lead_contact(**args)
            elif tool_name == "publish_to_n8n":
                return publish_event_to_n8n(**args)
            elif tool_name == "get_lead_memory":
                return get_lead_memory_context(**args)
            else:
                return {"status": "unknown_tool", "tool_name": tool_name}
        except Exception as e:
            return {"status": "error", "error": str(e), "tool_name": tool_name}

    def _session_completion_node(self, state: AgentState) -> AgentState:
        """Complete session and publish completion event."""
        # Upsert lead into memory
        lead_memory.upsert_lead(
            state["session_id"],
            {
                "transcript": state["transcript"],
                "profile": state["profile"],
                "intent": state["intent"],
            },
        )

        # Publish session completed event
        n8n_publisher.session_completed(
            session_id=state["session_id"],
            lead_id=state["session_id"],
            transcript=state["transcript"],
            intent=state["intent"],
            duration_seconds=0,  # Would be calculated from actual call duration
        )

        return state

    def process_turn(self, session_id: str, transcript: str) -> dict:
        """
        Process a single turn in the conversation.

        Args:
            session_id: Unique session identifier
            transcript: User's spoken input

        Returns:
            Agent response and state update
        """
        initial_state: AgentState = {
            "session_id": session_id,
            "transcript": transcript,
            "messages": [],
            "profile": {},
            "intent": "unknown",
            "recommendations": [],
            "appointment_details": None,
            "next_step": "start",
            "confidence": 0.0,
        }

        result = self.graph.invoke(initial_state)

        return {
            "session_id": result["session_id"],
            "transcript": result["transcript"],
            "profile": result["profile"],
            "intent": result["intent"],
            "confidence": result["confidence"],
            "recommendations": result["recommendations"],
            "appointment_details": result["appointment_details"],
            "next_step": result["next_step"],
            "n8n_event_published": True,
        }


# Global orchestrator instance
orchestrator = VoiceAgentOrchestrator()
