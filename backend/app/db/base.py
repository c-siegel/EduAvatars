"""
Database Model Base Configuration

This module collects all SQLModel metadata for Alembic autogenerate.

What is this for?
This file imports all database models so that Alembic (the database migration tool)
can discover them and automatically generate migration scripts.

How it works:
1. When you run `alembic revision --autogenerate`, Alembic imports this file
2. This file imports all your models, making them available to Alembic
3. Alembic compares the current database state with your model definitions
4. It generates a migration script with the differences

Why import all models here?
- Alembic needs to know about all models to detect schema changes
- Centralizing imports makes it easy to add new models
- The `# noqa: F401` comments tell linters these imports are intentional

How to use:
    # When you create a new model, add it here:
    from app.models.your_new_model import YourNewModel  # noqa: F401
    
    # Then run:
    # alembic revision --autogenerate -m "Add YourNewModel"
    # alembic upgrade head
"""

# Collects all SQLModel metadata for Alembic autogenerate.
from app.models.api_key import UserApiKey  # noqa: F401
from app.models.avatar_model import AvatarModel  # noqa: F401
from app.models.background_image import BackgroundImage  # noqa: F401
from app.models.conversation import Conversation  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.password_reset_token import PasswordResetToken  # noqa: F401
from app.models.project_access import ProjectAccess  # noqa: F401
from app.models.site_settings import SiteSettings  # noqa: F401
from app.models.user import User  # noqa: F401