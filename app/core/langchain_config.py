"""
LangChain Configuration and Setup

Phase 1: Foundation setup for LangChain integration
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from app.config import settings

print("🔗 Initializing LangChain configuration...")


# ==================== LLM Configuration ====================

def get_langchain_llm() -> ChatGoogleGenerativeAI:
    """Initialize and return the LangChain ChatGoogleGenerativeAI model."""
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not configured")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.7,
        top_p=0.95,
        max_tokens=2048,
        convert_system_message_to_human=True,
    )

    print("✅ LangChain LLM initialized (Gemini 2.0 Flash)")
    return llm


# ==================== Embeddings Configuration ====================

def get_langchain_embeddings() -> HuggingFaceEmbeddings:
    """Initialize HuggingFace embeddings model (all-MiniLM-L6-v2)."""
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={
            "show_progress_bar": True,
            "batch_size": 32,
        },
    )

    print("✅ LangChain Embeddings initialized (HuggingFace all-MiniLM-L6-v2)")
    return embeddings


# ==================== Prompt Templates ====================

RAG_SYSTEM_PROMPT = """You are a helpful AI assistant that answers questions based on provided document context.

INSTRUCTIONS:
1. Answer using the information in the context above
2. Be specific and cite which sources support your answer
3. If the context doesn't contain the answer, feel free to add information from other sources, but clearly state that
4. Be concise but thorough
5. Use GitHub markdown formatting for everything"""

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", RAG_SYSTEM_PROMPT),
    ("human", """CONTEXT:
{context}

USER QUESTION: {question}"""),
])

TITLE_GENERATION_PROMPT = PromptTemplate(
    input_variables=["user_message", "assistant_response"],
    template="""Generate ONE short, concise title (4-5 words) for this conversation:

User: {user_message}
Assistant: {assistant_response}""",
)

print("✅ LangChain configuration loaded successfully")
