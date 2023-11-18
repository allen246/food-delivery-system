from celery import shared_task
from celery_progress.backend import ProgressRecorder
from django.db import transaction
from .serializers import ProductSerializer


@shared_task(bind=True)
def bulk_create_task(self, items_to_create):
    with transaction.atomic():
        try:
            progress_recorder = ProgressRecorder(self)
            total_items = len(items_to_create)
            for index, item_data in enumerate(items_to_create):
                print(
                    "**********************" * 20,
                    item_data,
                    index,
                    "---------------------",
                )
                serializer = ProductSerializer(data=item_data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    error_message = (
                        f"Validation error for item {index + 1}: {serializer.errors}"
                    )
                    raise Exception(error_message)

                progress_recorder.set_progress(
                    index + 1,
                    total_items,
                    description=f"Creating item {index + 1}/{total_items}",
                )

            return {"result": "Bulk create completed"}
        except Exception as e:
            # Log the error or handle it as needed
            transaction.set_rollback(True)  # Rollback changes
            return {"result": f"Bulk update failed: {str(e)}"}
