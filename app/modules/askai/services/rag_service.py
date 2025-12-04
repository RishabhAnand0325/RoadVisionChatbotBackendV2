from uuid import UUID
from typing import Dict, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.services import get_llm_client, get_vector_store, GEMINI_MODEL_NAME
from app.modules.askai.db.repository import ChatRepository
from app.config import settings

def send_message_to_chat(db: Session, chat_id: UUID, user_message: str) -> Dict:
    """Handles the RAG pipeline using PostgreSQL and Weaviate."""
    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(chat_id)
    if not chat:
        raise ValueError("Chat not found")

    # 1. Retrieve context
    chat_docs = chat.documents
    context_text = ""
    sources = []
    
    if chat_docs:
        vector_store = get_vector_store()
        collection = vector_store.get_or_create_collection(str(chat_id))
        results = vector_store.query(collection, user_message, n_results=settings.RAG_TOP_K)
        
        if results:
            context_parts = []
            for idx, (doc, meta, score) in enumerate(results, 1):
                doc_type = meta.get('doc_type', 'unknown')
                source = meta.get('source', 'Unknown')
                
                if doc_type == 'pdf':
                    page = meta.get('page', 'unknown')
                    content_type = meta.get('type', 'text')
                    location = f"Page {page}"
                    if content_type == 'table': location += ", Table"
                else:
                    location = "Unknown location"
                    content_type = meta.get('type', 'unknown')
                
                context_parts.append(f"[Source {idx}: {source} - {location}]\n{doc}\n")
                
                sources.append({
                    "id": idx, "source": source, "location": location, "doc_type": doc_type,
                    "content_type": content_type, "content": doc[:800], "full_content": doc,
                    "page": meta.get('page', 'unknown')
                })
            
            context_text = "\n\n".join(context_parts)
            print(f"🔍 Retrieved {len(sources)} relevant sources")

    # 2. Build prompt
    if context_text:
        prompt = f"""You are a helpful AI assistant that answers questions based on provided document context.

CONTEXT:
{context_text}

USER QUESTION: {user_message}

INSTRUCTIONS:
1. Answer using the information in the context above
2. Be specific and cite which sources support your answer
3. If the context doesn't contain the answer, feel free to add information from other sources, but be sure to cite them and clearly state
that you are using information from other sources and not the context
4. Be concise but thorough
5. Use github markdown formatting for everything"""
    else:
        prompt = f"""You are a helpful AI assistant. Please answer: {user_message}"""
        
    # 3. Call LLM
    is_first_message = len(chat.messages) == 0
    recent_history = sorted(chat.messages, key=lambda m: m.timestamp, reverse=True)[:10]
    gemini_history = [{"role": "model" if msg.sender == "bot" else "user", "parts": [{"text": msg.text}]} for msg in recent_history]
    gemini_history.append({"role": "user", "parts": [{"text": prompt}]})
    
    try:
        client = get_llm_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=gemini_history
        )
        bot_response = response.text if hasattr(response, "text") else "I couldn't generate a response."
    except Exception as api_error:
        print(f"❌ Gemini API error: {api_error}")
        bot_response = f"I encountered an error: {str(api_error)}"

    # 4. Save conversation to DB
    chat_repo.add_message(chat, sender="user", text=user_message)
    chat_repo.add_message(chat, sender="bot", text=bot_response)
    db.commit() # Commit transaction for both messages
    db.refresh(chat)
    
    # Auto-generate a title if this is the first user message
    if is_first_message:
        try:
            title_prompt = f"Generate ONE short, concise title (4-5 words, NO extra text, straight to the title) for the following conversation: \n\nUser: {user_message}\n\nAssistant: {bot_response}"
            title_response = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=title_prompt
            )
            new_title = title_response.text.strip().replace('"', '')
            if new_title:
                chat_repo.rename(chat, new_title)
                print(f"✅ Updated title to: {new_title}")
        except Exception as api_error:
            print(f"❌ Could not Auto-generate title for chat {chat_id}: {api_error}")
            
    # 5. Return response
    message_count = len(chat.messages)
    return {"reply": bot_response, "sources": sources, "message_count": message_count}
