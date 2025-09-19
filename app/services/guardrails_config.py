"""
GuardRails AI configuration for preventing model hallucination in ECS Ehsan Chappal Store
"""

import os
from typing import Dict, Any, List
import json
import logging

try:
    import guardrails as gd
    from guardrails import Guard
    GUARDRAILS_AVAILABLE = True

    # Try to import hub validators, but don't fail if they're not available
    try:
        from guardrails.hub import CompetitorCheck, Hallucination, DetectPII, ToxicLanguage
        HUB_VALIDATORS_AVAILABLE = True
    except ImportError:
        HUB_VALIDATORS_AVAILABLE = False
        logging.warning("GuardRails hub validators not available, using basic validation only")

except ImportError as e:
    logging.warning(f"GuardRails not available: {e}")
    GUARDRAILS_AVAILABLE = False
    HUB_VALIDATORS_AVAILABLE = False
    # Create dummy classes to prevent import errors
    class Guard:
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, *args, **kwargs):
            return args[0] if args else None

    class CompetitorCheck:
        def __init__(self, *args, **kwargs):
            pass

    class Hallucination:
        def __init__(self, *args, **kwargs):
            pass

    class DetectPII:
        def __init__(self, *args, **kwargs):
            pass

    class ToxicLanguage:
        def __init__(self, *args, **kwargs):
            pass

logger = logging.getLogger(__name__)

class GuardRailsManager:
    """Manages GuardRails AI validation for LLM responses"""

    def __init__(self):
        self.guards = self._initialize_guards()

    def _initialize_guards(self) -> Dict[str, Guard]:
        """Initialize different guards for different contexts"""
        guards = {}

        if not GUARDRAILS_AVAILABLE:
            logger.warning("GuardRails not available, using fallback validation")
            return guards

        try:
            if HUB_VALIDATORS_AVAILABLE:
                # Guard for product information responses with hub validators
                guards['product_info'] = Guard().use_many(
                    Hallucination(threshold=0.8),
                    CompetitorCheck(competitors=["Nike", "Adidas", "Bata", "Service", "Hush Puppies"]),
                    DetectPII(),
                )

                # Guard for general conversation
                guards['general'] = Guard().use_many(
                    Hallucination(threshold=0.7),
                    ToxicLanguage(threshold=0.8),
                    DetectPII(),
                )

                # Guard for inventory/product search responses
                guards['inventory'] = Guard().use_many(
                    Hallucination(threshold=0.9),  # Strictest for product data
                    CompetitorCheck(competitors=["Nike", "Adidas", "Bata", "Service", "Hush Puppies"]),
                )

                logger.info("✅ GuardRails initialized with hub validators")
            else:
                # Basic guards without hub validators
                guards['product_info'] = Guard()
                guards['general'] = Guard()
                guards['inventory'] = Guard()

                logger.info("✅ GuardRails initialized with basic validation (no hub validators)")

        except Exception as e:
            logger.error(f"❌ Failed to initialize GuardRails: {e}")

        return guards

    def validate_response(self, response: str, context: str = "general", metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate LLM response using appropriate GuardRails

        Args:
            response: The LLM response to validate
            context: Type of response (product_info, general, inventory)
            metadata: Additional context for validation

        Returns:
            Dict with validation results and potentially modified response
        """
        try:
            # If GuardRails not available, just do basic validation
            if not GUARDRAILS_AVAILABLE or not self.guards:
                logger.info("Using fallback validation without GuardRails")
                # Additional context-specific validation
                if context == "product_info":
                    response = self._validate_product_accuracy(response, metadata)
                elif context == "inventory":
                    response = self._validate_inventory_consistency(response, metadata)

                return {
                    "status": "success",
                    "passed_validations": True,
                    "validated_response": response,
                    "fallback_used": True
                }

            if context not in self.guards:
                logger.warning(f"No guard configured for context: {context}, using general")
                context = "general"

            guard = self.guards[context]

            # Additional context-specific validation
            if context == "product_info":
                response = self._validate_product_accuracy(response, metadata)
            elif context == "inventory":
                response = self._validate_inventory_consistency(response, metadata)

            # Run GuardRails validation
            validation_result = guard.validate(response)

            return {
                "status": "success",
                "validated_response": validation_result.validated_output,
                "passed_validations": True,
                "warnings": validation_result.validation_passed,
                "original_response": response
            }

        except Exception as e:
            logger.error(f"GuardRails validation failed: {e}")
            return {
                "status": "error",
                "validated_response": self._create_safe_fallback_response(context),
                "passed_validations": False,
                "error": str(e),
                "original_response": response
            }

    def _validate_product_accuracy(self, response: str, metadata: Dict[str, Any] = None) -> str:
        """Additional validation for product information accuracy"""
        try:
            # Parse response if it's JSON
            if response.strip().startswith('{'):
                data = json.loads(response)

                # Validate product IDs exist in provided inventory
                if metadata and 'inventory' in metadata:
                    inventory = metadata['inventory']
                    if isinstance(inventory, str):
                        inventory = json.loads(inventory)

                    valid_product_ids = set()
                    if isinstance(inventory, dict) and 'products' in inventory:
                        valid_product_ids = {p.get('id') or p.get('product_id') for p in inventory['products']}
                    elif isinstance(inventory, list):
                        valid_product_ids = {p.get('id') or p.get('product_id') for p in inventory}

                    # Check recommended products
                    if 'products' in data:
                        recommended_products = data['products']
                        if isinstance(recommended_products, str):
                            recommended_products = [recommended_products]

                        # Filter out invalid product IDs
                        valid_recommendations = [pid for pid in recommended_products if pid in valid_product_ids]

                        if len(valid_recommendations) < len(recommended_products):
                            logger.warning("Some recommended products not found in inventory")
                            data['products'] = valid_recommendations

                            # Update reply if no valid products remain
                            if not valid_recommendations:
                                data['reply'] = "Sorry, I couldn't find the specific products you're looking for in our current inventory. Please try browsing our categories or contact us for assistance."
                                data['show_images'] = False

                return json.dumps(data, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Product accuracy validation failed: {e}")

        return response

    def _validate_inventory_consistency(self, response: str, metadata: Dict[str, Any] = None) -> str:
        """Additional validation for inventory browsing responses"""
        try:
            if response.strip().startswith('{'):
                data = json.loads(response)

                # Ensure product recommendations are consistent with chappal store context
                if 'reply' in data:
                    reply = data['reply'].lower()

                    # Check for inappropriate product mentions
                    inappropriate_terms = ['kurta', 'shalwar', 'kameez', 'sherwani', 'dupatta', 'lawn', 'cotton suit', 'clothing']
                    for term in inappropriate_terms:
                        if term in reply:
                            # Replace with appropriate chappal store terms
                            data['reply'] = data['reply'].replace(term, 'footwear')
                            logger.warning(f"Replaced inappropriate term '{term}' in response")

                return json.dumps(data, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Inventory consistency validation failed: {e}")

        return response

    def _create_safe_fallback_response(self, context: str) -> str:
        """Create a safe fallback response when validation fails"""
        fallback_responses = {
            "product_info": json.dumps({
                "products": [],
                "attribute_query": "clarification",
                "NEED": None,
                "reply": "I apologize, but I'm having trouble processing your request right now. Please try again or contact our customer service for assistance.",
                "similar_products": [],
                "show_images": False
            }),
            "inventory": json.dumps({
                "products": [],
                "categories": [],
                "reply": "I'm currently unable to process your inventory request. Please try again later or browse our website directly.",
                "show_images": False
            }),
            "general": json.dumps({
                "intent": "smalltalk",
                "reply": "I apologize, but I'm having difficulty processing your message. Please rephrase your question or contact our support team.",
                "need_clarification": True
            })
        }

        return fallback_responses.get(context, fallback_responses["general"])

# Global instance
guardrails_manager = GuardRailsManager()

def validate_llm_response(response: str, context: str = "general", metadata: Dict[str, Any] = None) -> str:
    """
    Convenience function to validate LLM responses

    Args:
        response: The LLM response to validate
        context: Type of response (product_info, general, inventory)
        metadata: Additional context for validation

    Returns:
        Validated and potentially corrected response
    """
    result = guardrails_manager.validate_response(response, context, metadata)

    if result["status"] == "success" and result["passed_validations"]:
        return result["validated_response"]
    else:
        logger.warning(f"GuardRails validation issues: {result.get('error', 'Unknown error')}")
        return result["validated_response"]  # This will be the fallback response