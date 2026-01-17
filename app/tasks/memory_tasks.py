from app.extensions import celery_app
from app.services.memory_service import MemoryService
import logging

logger = logging.getLogger(__name__)

@celery_app.task
def extract_memories_task(messages_dict_list):
    """
    Background task to extract memories.
    messages_dict_list: list of dicts (Celery needs primitives)
    """
    logger.info("Starting memory extraction task")
    from app import create_app
    app = create_app()
    
    with app.app_context():
        try:
            # Re-init service within context to ensure it gets DB session bound to this thread/context
            service = MemoryService()
            extracted = service.extract_and_save_memories(messages_dict_list)
            if extracted:
                logger.info(f"Extracted {len(extracted)} new memories.")
            else:
                logger.info("No new memories extracted.")
        except Exception as e:
            logger.error(f"Error in extract_memories_task: {e}", exc_info=True)
