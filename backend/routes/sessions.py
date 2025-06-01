from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime

# This is a placeholder for your actual Supabase client and Clerk user dependency
# You'll need to implement these based on your project setup.
from supabase import create_client, Client

# --- Placeholder for Supabase client initialization ---
# Replace with your actual Supabase URL and Service Role Key (for backend operations)
# Ensure Service Role Key is stored securely (e.g., environment variable)
SUPABASE_URL = "https://qgtxncipmwvesrpsxarg.supabase.co" # From previous step
# IMPORTANT: Use the SERVICE ROLE KEY for backend operations, NOT the anon key.
# This key should be kept secret and configured via environment variables.
SUPABASE_SERVICE_KEY = "YOUR_SUPABASE_SERVICE_ROLE_KEY" 

if not SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_KEY == "YOUR_SUPABASE_SERVICE_ROLE_KEY":
    print("WARNING: SUPABASE_SERVICE_KEY is not set or is using a placeholder. Backend DB operations will fail.")
    # In a real app, you might raise an error or have a more robust config loading
    db: Client = None # type: ignore
else:
    db: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# --- Placeholder for Clerk User Dependency ---
# This function would typically validate the Clerk JWT from the Authorization header
# and return the user ID or raise an HTTPException if invalid.
async def get_current_clerk_user_id(token: Optional[str] = Depends(lambda: None)) -> str:
    # In a real app, you'd get the token from `Authorization: Bearer <token>` header
    # and use Clerk's backend SDK to verify it.
    # For this placeholder, we'll simulate it.
    # Replace this with your actual Clerk authentication logic.
    if not token: # Simulate no token or invalid token
        # This part of the example assumes you have a way to inject the Clerk user_id
        # For now, we'll use a placeholder. In a real app, this would come from Clerk auth.
        print("Warning: No Clerk token found, using placeholder user_id. Implement actual Clerk auth.")
        return "placeholder_clerk_user_id_sessions_route" 
    
    # Example: user_id = await verify_clerk_token(token)
    # return user_id
    # For now, returning the token itself as a mock user_id if one was passed (hypothetically)
    return token # This is NOT how it would actually work.

router = APIRouter(
    prefix="/api/v1/sessions",
    tags=["Conversation Sessions"],
)

class ConversationSessionBase(BaseModel):
    session_name: Optional[str] = None
    conversation_history: List[Dict[str, Any]] # Stores Langgraph messages

class ConversationSessionCreate(ConversationSessionBase):
    pass

class ConversationSession(ConversationSessionBase):
    id: str # UUID, but represented as str here
    user_id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

class ConversationSessionBrief(BaseModel):
    id: str
    session_name: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

@router.post("/", response_model=ConversationSession, status_code=status.HTTP_201_CREATED)
async def create_conversation_session(
    session_data: ConversationSessionCreate,
    clerk_user_id: str = Depends(get_current_clerk_user_id)
):
    if not db:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database client not configured")
    try:
        data, error = db.table("user_conversation_sessions").insert({
            "user_id": clerk_user_id,
            "session_name": session_data.session_name,
            "conversation_history": session_data.conversation_history
        }).execute()
        
        if error or not data or not data.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save session: {error.message if error else 'Unknown error'}")
        return data.data[0]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/", response_model=List[ConversationSessionBrief])
async def get_conversation_sessions(clerk_user_id: str = Depends(get_current_clerk_user_id)):
    if not db:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database client not configured")
    try:
        data, error = db.table("user_conversation_sessions").select("id, session_name, created_at, updated_at").eq("user_id", clerk_user_id).order("updated_at", desc=True).execute()
        if error:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch sessions: {error.message}")
        return data.data if data else []
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{session_id}", response_model=ConversationSession)
async def get_conversation_session(
    session_id: str,
    clerk_user_id: str = Depends(get_current_clerk_user_id)
):
    if not db:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database client not configured")
    try:
        data, error = db.table("user_conversation_sessions").select("*").eq("id", session_id).eq("user_id", clerk_user_id).single().execute()
        if error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session not found or access denied: {error.message}")
        if not data or not data.data:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or access denied")
        return data.data
    except Exception as e:
        # Check if it's a PostgREST "PGRST116" (single() found no rows) which supabase-py might not parse into a specific error type
        if "PGRST116" in str(e): # A bit simplistic, ideally supabase-py would offer a typed error
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or access denied")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_session(
    session_id: str,
    clerk_user_id: str = Depends(get_current_clerk_user_id)
):
    if not db:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database client not configured")
    try:
        # First, verify the session belongs to the user to prevent accidental deletion errors from being vague
        _, verify_error = db.table("user_conversation_sessions").select("id").eq("id", session_id).eq("user_id", clerk_user_id).single().execute()
        if verify_error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or access denied for deletion.")

        _, error = db.table("user_conversation_sessions").delete().eq("id", session_id).eq("user_id", clerk_user_id).execute()
        if error:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete session: {error.message}")
        return
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        if "PGRST116" in str(e): # From the verification step
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or access denied for deletion.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) 