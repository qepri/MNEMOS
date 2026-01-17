from app.extensions import db
from app.models.memory import UserMemory
from app.models.user_preferences import UserPreferences
from app.services.llm_client import LLMClient
import logging

logger = logging.getLogger(__name__)

class MemoryService:
    def __init__(self):
        self.db = db
        # self.llm = get_llm_client() # Deprecated: We instantiate per-request or per-service logic now to support dual providers

    def get_preferences(self):
        return UserPreferences.query.first()

    def get_memories(self):
        return UserMemory.query.order_by(UserMemory.created_at.desc()).all()
        
    def delete_memory(self, memory_id):
        mem = UserMemory.query.get(memory_id)
        if mem:
            self.db.session.delete(mem)
            self.db.session.commit()
            return True
        return False

    def extract_and_save_memories(self, messages):
        """
        Analyzes the conversation and extracts new long-term memories.
        Args:
            messages: List of Message objects (or objects with role/content attributes)
        """
        prefs = self.get_preferences()
        if not prefs or not prefs.memory_enabled:
            return []

        # Check Capacity
        current_count = UserMemory.query.count()
        if current_count >= prefs.max_memories:
            logger.warning(f"Memory limit reached ({current_count}/{prefs.max_memories}). Skipping extraction.")
            return []

        # Prepare messages for extraction context. 
        # We use the last N messages to capture immediate context.
        recent_msgs = messages[-6:] if len(messages) > 6 else messages
        
        conversation_text = ""
        for msg in recent_msgs:
            # Handle both dicts and objects
            r = msg.role if hasattr(msg, 'role') else msg.get('role')
            c = msg.content if hasattr(msg, 'content') else msg.get('content')
            
            role_label = "User" if r == 'user' else "Assistant"
            conversation_text += f"{role_label}: {c}\n"

        system_prompt = """You are a Memory Extraction AI.
Your goal is to extract facts about the user that should be remembered for future conversations.
Focus on:
- User's name, profession, hobbies.
- Specific preferences (formatting, language).
- Project details, specific context, or goals mentioned by the user.

Do NOT extract:
- Temporary context (e.g. "write a loop", "fix this error").
- System instructions.
- Facts the Assistant communicated. Focus on the USER.

Output ONLY the extracted facts, one per line.
If no relevant facts are found, output NOTHING.
Do not use bullet points or numbering."""

        try:
            # Use configured memory model or default
            model_to_use = prefs.memory_llm_model 
            
            # Configure dedicated LLMClient for Memory
            mem_provider = getattr(prefs, 'memory_provider', 'ollama')
            api_key = None
            base_url = None
            
            if mem_provider == 'openai':
                api_key = prefs.openai_api_key
            elif mem_provider == 'anthropic':
                api_key = prefs.anthropic_api_key
            elif mem_provider == 'groq':
                api_key = prefs.groq_api_key
            elif mem_provider == 'lm_studio':
                base_url = prefs.local_llm_base_url
            elif mem_provider == 'custom':
                api_key = prefs.custom_api_key
                base_url = prefs.local_llm_base_url
                
            memory_llm = LLMClient(
                provider=mem_provider,
                api_key=api_key,
                base_url=base_url,
                model=model_to_use
            )
            
            response = memory_llm.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": conversation_text}],
                model=model_to_use
            )

            # Check if LLMClient returned an error string
            if response and response.startswith("Error communicating with LLM"):
                logger.error(f"Memory extraction skipped due to LLM error: {response}")
                return []
            
            new_memories = []
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if line and len(line) > 5: # Basic filter to avoid noise
                    # Check duplicates (naive check)
                    # We check if exact content exists
                    exists = UserMemory.query.filter(UserMemory.content == line).first()
                    if not exists:
                        # Check capacity again in loop
                        if UserMemory.query.count() >= prefs.max_memories:
                            break
                            
                        mem = UserMemory(content=line)
                        self.db.session.add(mem)
                        new_memories.append(mem)
            
            self.db.session.commit()
            return [m.content for m in new_memories]

        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")
            return []
