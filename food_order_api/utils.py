import uuid
from celery import shared_task
from drf_yasg.generators import OpenAPISchemaGenerator


@shared_task()
def timer():
    import time

    time.sleep(10)


def generate_uuid_with_prefix(prefix):
    _id = str(uuid.uuid4()).replace("-", "")
    return f"{prefix}{_id[len(prefix):]}"


class CustomOpenAPISchemaGenerator(OpenAPISchemaGenerator):
  def get_schema(self, request=None, public=False):
    """Generate a :class:`.Swagger` object with custom tags"""

    swagger = super().get_schema(request, public)
    swagger.tags = [
        {
            "name": "user",
            "description": "Register a user"
        },
        {
            "name": "users",
            "description": "Operations related to users"
        },
        {
            "name": "orders",
            "description": "Operations related to order"
        },
        {
            "name": "products",
            "description": "Operations related to products"
        },
    ]

    return swagger
