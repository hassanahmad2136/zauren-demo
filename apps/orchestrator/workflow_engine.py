# apps/orchestrator/workflow_engine.py
"""
LangGraph Workflow Engine for Retail AI
Manages the conversation flow and agent coordination
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime
import httpx

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from core.models.message import CanonicalMessage, UserContext
from core.llm.groq_client import groq_client
from config.settings import settings
import logging
import json

logger = logging.getLogger(__name__)

# Define the state for our workflow
class ConversationState(TypedDict):
    """State that flows through the workflow"""
    message: CanonicalMessage
    context: UserContext
    language: str
    intent: Optional[str]
    intent_confidence: Optional[float]
    entities: Optional[Dict[str, Any]]
    search_entity: Optional[Dict[str, Any]]  # Accumulated search context
    products: Optional[List[Dict]]
    referenced_product: Optional[Dict]  # For handling "that one" references
    cart_action: Optional[str]
    response: Optional[str]
    agents_used: List[str]
    error: Optional[str]
    execution_times: Dict[str, float]

class RetailWorkflow:
    """
    LangGraph workflow for retail conversations
    Coordinates intent classification, product search, cart management, and response generation
    """
    
    def __init__(self):
        self.graph = None
        self.memory = MemorySaver()
        self.agent_clients = {}
        self.stats = {
            "total_processed": 0,
            "avg_execution_time": 0,
            "intents_distribution": {},
            "languages_processed": {}
        }
        
    async def initialize(self):
        """Initialize the workflow graph"""
        # Build the workflow graph
        self.graph = self._build_workflow()
        
        # Initialize HTTP clients for agents
        self.agent_clients = {
            "intent": httpx.AsyncClient(base_url="http://localhost:8002"),
            "rag": httpx.AsyncClient(base_url="http://localhost:8003"),
            "cart": httpx.AsyncClient(base_url="http://localhost:8004"),
            "sales": httpx.AsyncClient(base_url="http://localhost:8005"),
            "support": httpx.AsyncClient(base_url="http://localhost:8006")
        }
        
        logger.info("✅ Workflow engine initialized")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(ConversationState)
        
        # Add nodes for each step
        workflow.add_node("classify_intent", self.classify_intent)
        workflow.add_node("extract_entities", self.extract_entities)
        workflow.add_node("search_products", self.search_products)
        workflow.add_node("manage_cart", self.manage_cart)
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("handle_support", self.handle_support)
        
        # Set entry point
        workflow.set_entry_point("classify_intent")
        
        # Add conditional edges based on intent
        workflow.add_conditional_edges(
            "classify_intent",
            self.route_by_intent,
            {
                "product_search": "extract_entities",
                "cart_action": "manage_cart",
                "support": "handle_support",
                "general": "generate_response",
                "greeting": "generate_response"
            }
        )
        
        # Add edges from entity extraction to product search
        workflow.add_edge("extract_entities", "search_products")
        
        # All paths lead to response generation
        workflow.add_edge("search_products", "generate_response")
        workflow.add_edge("manage_cart", "generate_response")
        workflow.add_edge("handle_support", "generate_response")
        
        # End after generating response
        workflow.add_edge("generate_response", END)
        
        return workflow.compile(checkpointer=self.memory)
    
    async def classify_intent(self, state: ConversationState) -> ConversationState:
        """Classify the intent using few-shot learning with conversation history"""
        start_time = time.time()
        state["agents_used"].append("intent")
        
        try:
            # Get context manager instance
            from apps.orchestrator.context_manager import ContextManager
            context_manager = ContextManager()
            
            # Get intent history for few-shot learning
            intent_history = await context_manager.get_intent_history(
                state['message'].user_id, 
                state['message'].tenant_id,
                limit=3  # Get last 3 examples
            )
            
            # Build few-shot examples from history
            history_examples = ""
            if intent_history:
                history_examples = "\nRecent conversation examples from this user:\n"
                for hist in intent_history:
                    history_examples += f'User: "{hist["message"]}"\n'
                    history_examples += f'Classification: {json.dumps(hist["intent_json"], indent=2)}\n\n'
            
            # Get current search entity for context
            search_entity = await context_manager.get_search_entity(
                state['message'].user_id,
                state['message'].tenant_id
            )
            
            classification_prompt = f"""You are an intent classification system for a retail chatbot. Classify the user's intent and extract entities.

## Intent Categories:
- product_search: User wants to find, browse, or get information about products
- cart_action: User wants to add, remove, view cart, or checkout
- support: User needs help, has complaints, or asks about policies
- greeting: Simple greeting or conversation starter
- general: Chitchat or unclear intent

## Examples:
User: "show me red nike shoes under $100"
Classification: {{
    "intent": "product_search",
    "confidence": 0.95,
    "sub_intent": "find_product",
    "entities": {{
        "query": "red nike shoes under $100",
        "brand": "nike",
        "color": "red",
        "category": "shoes",
        "max_price": 100
    }}
}}

User: "add 2 of those to my cart"
Classification: {{
    "intent": "cart_action",
    "confidence": 0.9,
    "sub_intent": "add_to_cart",
    "entities": {{
        "action": "add",
        "quantity": 2,
        "referenced_item_id": "previous_item"
    }}
}}

User: "what's your return policy?"
Classification: {{
    "intent": "support",
    "confidence": 0.95,
    "sub_intent": "policy_inquiry",
    "entities": {{
        "topic": "return_policy"
    }}
}}

{history_examples}

## Current Context:
Previous conversation context: {state['context'].conversation_context}
Current search entity: {json.dumps(search_entity, indent=2)}

## Current User Message:
User: "{state['message'].content}"

Provide the classification as a JSON object with intent, confidence, sub_intent, and entities.
The entities should include updates to the search entity fields (query, category, brand, color, size, style, material, min_price, max_price, referenced_item_id, custom_attributes)."""

            response = await groq_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a precise intent classification system. Always respond with valid JSON."},
                    {"role": "user", "content": classification_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=300,
                target_language="en"  # Always classify in English for consistency
            )
            
            result = json.loads(response)
            state["intent"] = result.get("intent", "general")
            state["intent_confidence"] = result.get("confidence", 0.5)
            state["entities"] = result.get("entities", {})
            
            # Update search entity with new information
            if state["entities"]:
                updated_entity = await context_manager.update_search_entity(
                    state['message'].user_id,
                    state['message'].tenant_id,
                    state["entities"]
                )
                state["search_entity"] = updated_entity
            
            # Add to intent history for future few-shot learning
            await context_manager.add_intent_to_history(
                state['message'].user_id,
                state['message'].tenant_id,
                state['message'].content,
                result
            )
            
            # Update stats
            self.stats["intents_distribution"][state["intent"]] = \
                self.stats["intents_distribution"].get(state["intent"], 0) + 1
            
            logger.info(f"Intent classified: {state['intent']} (confidence: {state['intent_confidence']})")
            
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            state["intent"] = "general"
            state["intent_confidence"] = 0.3
            state["error"] = f"Intent classification failed: {str(e)}"
        
        state["execution_times"]["intent"] = time.time() - start_time
        return state
    
    def route_by_intent(self, state: ConversationState) -> str:
        """Route to the appropriate node based on intent"""
        intent = state.get("intent", "general")
        
        # Route based on intent
        if intent == "product_search":
            return "product_search"
        elif intent in ["add_to_cart", "remove_from_cart", "view_cart", "cart_action"]:
            return "cart_action"
        elif intent == "support":
            return "support"
        elif intent == "greeting":
            return "greeting"
        else:
            return "general"
    
    async def extract_entities(self, state: ConversationState) -> ConversationState:
        """Extract entities for product search"""
        start_time = time.time()
        
        try:
            # Entity extraction is already done in intent classification
            # This step can be used for more detailed extraction if needed
            
            if not state.get("entities"):
                extraction_prompt = f"""Extract product search entities from this message:
                
Message: "{state['message'].content}"

Extract: product_name, category, brand, color, size, price_range, features

Return as JSON object."""

                response = await groq_client.chat_completion(
                    messages=[
                        {"role": "user", "content": extraction_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=150
                )
                
                state["entities"] = json.loads(response)
                
        except Exception as e:
            logger.error(f"Entity extraction error: {e}")
            
        state["execution_times"]["entity_extraction"] = time.time() - start_time
        return state
    
    async def search_products(self, state: ConversationState) -> ConversationState:
        """Search for products using the accumulated search entity"""
        start_time = time.time()
        state["agents_used"].append("rag")
        
        try:
            # Get context manager instance
            from apps.orchestrator.context_manager import ContextManager
            context_manager = ContextManager()
            
            # Get the current search entity
            search_entity = await context_manager.get_search_entity(
                state['message'].user_id,
                state['message'].tenant_id
            )
            
            # In production, this would call the RAG agent with:
            # 1. Embedding search using search_entity["query"]
            # 2. Filters for category, brand, color, size, etc.
            # 3. Price range filtering
            
            # For now, simulate product search with the search entity
            logger.info(f"Searching products with entity: {json.dumps(search_entity, indent=2)}")
            
            # Simulate filtered product search
            all_products = [
                {
                    "id": "PROD001",
                    "name": "Nike Air Max 270",
                    "category": "shoes",
                    "brand": "nike",
                    "price": 150.00,
                    "colors": ["black", "white", "red"],
                    "sizes": ["7", "8", "9", "10", "11"],
                    "description": "Comfortable running shoes with Air Max cushioning",
                    "in_stock": True
                },
                {
                    "id": "PROD002",
                    "name": "Adidas Ultraboost 22",
                    "category": "shoes",
                    "brand": "adidas",
                    "price": 180.00,
                    "colors": ["black", "blue"],
                    "sizes": ["8", "9", "10"],
                    "description": "Premium running shoes with Boost technology",
                    "in_stock": True
                },
                {
                    "id": "PROD003",
                    "name": "Nike Pro T-Shirt",
                    "category": "clothing",
                    "brand": "nike",
                    "price": 35.00,
                    "colors": ["black", "white", "gray"],
                    "sizes": ["S", "M", "L", "XL"],
                    "description": "Moisture-wicking athletic t-shirt",
                    "in_stock": True
                }
            ]
            
            # Apply filters based on search entity
            filtered_products = []
            for product in all_products:
                # Category filter
                if search_entity.get("category") and product["category"] != search_entity["category"]:
                    continue
                
                # Brand filter
                if search_entity.get("brand") and product["brand"].lower() != search_entity["brand"].lower():
                    continue
                
                # Color filter
                if search_entity.get("color") and search_entity["color"] not in product.get("colors", []):
                    continue
                
                # Price range filter
                if search_entity.get("min_price") and product["price"] < search_entity["min_price"]:
                    continue
                if search_entity.get("max_price") and product["price"] > search_entity["max_price"]:
                    continue
                
                # Size filter
                if search_entity.get("size") and search_entity["size"] not in product.get("sizes", []):
                    continue
                
                filtered_products.append(product)
            
            state["products"] = filtered_products
            state["search_entity"] = search_entity
            
            logger.info(f"Found {len(filtered_products)} products matching filters")
            
            # If referenced_item_id is present, handle "those" or "that" references
            if search_entity.get("referenced_item_id") == "previous_item" and len(filtered_products) > 0:
                # Get the most recently shown product
                state["referenced_product"] = filtered_products[0]
            
        except Exception as e:
            logger.error(f"Product search error: {e}")
            state["products"] = []
            
        state["execution_times"]["product_search"] = time.time() - start_time
        return state
    
    async def manage_cart(self, state: ConversationState) -> ConversationState:
        """Manage shopping cart actions"""
        start_time = time.time()
        state["agents_used"].append("cart")
        
        try:
            # Get cart action from entities or intent
            action = state.get("entities", {}).get("action", "view")
            
            # In production, this would call the cart agent
            # For now, simulate cart management
            
            if action == "add":
                state["cart_action"] = "added_to_cart"
                logger.info("Item added to cart")
            elif action == "remove":
                state["cart_action"] = "removed_from_cart"
                logger.info("Item removed from cart")
            else:
                state["cart_action"] = "viewed_cart"
                logger.info("Cart viewed")
                
        except Exception as e:
            logger.error(f"Cart management error: {e}")
            state["cart_action"] = "error"
            
        state["execution_times"]["cart_management"] = time.time() - start_time
        return state
    
    async def handle_support(self, state: ConversationState) -> ConversationState:
        """Handle customer support queries"""
        start_time = time.time()
        state["agents_used"].append("support")
        
        try:
            # In production, this would search the knowledge base
            # For now, provide a support response
            
            support_prompt = f"""Provide customer support for this query:
            
Query: "{state['message'].content}"
Context: {state['context'].conversation_context}

Provide a helpful, empathetic response."""

            response = await groq_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful customer support agent for an online retail store."},
                    {"role": "user", "content": support_prompt}
                ],
                temperature=0.7,
                max_tokens=300,
                target_language=state['language']
            )
            
            state["response"] = response
            
        except Exception as e:
            logger.error(f"Support handling error: {e}")
            state["response"] = "I apologize for the inconvenience. Let me connect you with our support team."
            
        state["execution_times"]["support"] = time.time() - start_time
        return state
    
    async def generate_response(self, state: ConversationState) -> ConversationState:
        """Generate the final response to the user"""
        start_time = time.time()
        state["agents_used"].append("sales")
        
        try:
            # If response already generated (from support), return it
            if state.get("response"):
                state["execution_times"]["response_generation"] = time.time() - start_time
                return state
            
            # Build context for response generation
            response_context = {
                "intent": state.get("intent"),
                "products": state.get("products", []),
                "cart_action": state.get("cart_action"),
                "entities": state.get("entities", {}),
                "conversation_history": state["context"].recent_messages[-5:] if state["context"].recent_messages else []
            }
            
            # Generate response based on intent and results
            generation_prompt = f"""Generate a response for this retail conversation:
            
User message: "{state['message'].content}"
Intent: {state.get('intent')}
Context: {json.dumps(response_context, indent=2)}
User preferences: {state['context'].preferences}

Instructions:
1. Be helpful, friendly, and conversational
2. If products were found, present them attractively
3. Include relevant details like price, colors, sizes
4. Suggest next actions (view more, add to cart, etc.)
5. Keep response concise but complete
6. Use the user's language naturally

Generate a natural response:"""

            response = await groq_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a friendly retail assistant helping customers shop online."},
                    {"role": "user", "content": generation_prompt}
                ],
                temperature=0.7,
                max_tokens=400,
                target_language=state['language']
            )
            
            state["response"] = response
            
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            state["response"] = "I apologize, but I'm having trouble processing your request. Please try again."
            
        state["execution_times"]["response_generation"] = time.time() - start_time
        return state
    
    async def execute(self, message: CanonicalMessage, context: UserContext, language: str = "en") -> Dict[str, Any]:
        """Execute the workflow for a message"""
        start_time = time.time()
        
        # Initialize state
        initial_state: ConversationState = {
            "message": message,
            "context": context,
            "language": language or "en",
            "intent": None,
            "intent_confidence": None,
            "entities": None,
            "products": None,
            "cart_action": None,
            "response": None,
            "agents_used": [],
            "error": None,
            "execution_times": {}
        }
        
        # Run the workflow
        try:
            config = {"configurable": {"thread_id": f"{message.user_id}:{message.tenant_id}"}}
            final_state = await self.graph.ainvoke(initial_state, config)
            
            # Update stats
            self.stats["total_processed"] += 1
            self.stats["languages_processed"][language] = \
                self.stats["languages_processed"].get(language, 0) + 1
            
            total_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Update average execution time
            prev_avg = self.stats["avg_execution_time"]
            self.stats["avg_execution_time"] = \
                (prev_avg * (self.stats["total_processed"] - 1) + total_time) / self.stats["total_processed"]
            
            return {
                "response": final_state.get("response", "I couldn't process your request."),
                "intent": final_state.get("intent"),
                "confidence": final_state.get("intent_confidence"),
                "agents_used": final_state.get("agents_used", []),
                "execution_time_ms": int(total_time),
                "execution_breakdown": final_state.get("execution_times", {}),
                "products": final_state.get("products"),
                "error": final_state.get("error")
            }
            
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            return {
                "response": "I apologize, but I encountered an error. Please try again.",
                "error": str(e),
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get workflow statistics"""
        return self.stats