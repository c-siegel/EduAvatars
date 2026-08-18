"""
Base Schema Classes for Pydantic Models

This module provides base classes for Pydantic models used throughout the application.
These base classes handle common configuration like field naming conventions.

What is this for?
This module solves the naming convention mismatch between:
- Python/Backend: Uses snake_case (e.g., llm_model, user_id)
- JavaScript/Frontend: Uses camelCase (e.g., llmModel, userId)

By inheriting from CamelModel, all your schemas automatically handle this conversion.

How to use:
    from app.core.schema import CamelModel
    
    class ProjectCreate(CamelModel):
        llm_model: str  # Python uses snake_case
        user_id: str    # Python uses snake_case
    
    # Frontend can send: { "llmModel": "gpt-4", "userId": "123" }
    # Backend receives: llm_model="gpt-4", user_id="123"
    # Frontend receives: { "llmModel": "gpt-4", "userId": "123" }
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """
    Base class for Pydantic models that automatically handle camelCase/snake_case conversion.
    
    This class configures Pydantic to:
    1. Accept both snake_case and camelCase in request bodies
    2. Serialize responses using camelCase (JavaScript convention)
    3. Keep Python code using snake_case (PEP 8 convention)
    
    Example:
        class UserSchema(CamelModel):
            user_name: str  # Python field name (snake_case)
            email_address: str
        
        # Frontend sends: { "userName": "John", "emailAddress": "john@example.com" }
        # Backend receives: user_name="John", email_address="john@example.com"
        # Backend returns: { "userName": "John", "emailAddress": "john@example.com" }
    """
    # populate_by_name=True: Accepts both snake_case (Python field name) and
    # camelCase (alias) in request body. FastAPI serializes responses by default
    # with aliases (response_model_by_alias=True is FastAPI default), so requests
    # can send `llmModel` and responses also come back as `llmModel` — solves the
    # camelCase/snake_case mismatch between Frontend (camelCase) and Backend
    # (snake_case).
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)