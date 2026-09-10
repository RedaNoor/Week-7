from sqlalchemy.orm import declarative_base

# Shared Base for all ORM models
def get_base():
    """Return a declarative base instance. Using a function avoids import timing issues."""
    return declarative_base()

Base = get_base()
