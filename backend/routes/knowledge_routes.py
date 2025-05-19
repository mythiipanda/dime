from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Body
from fastapi.concurrency import run_in_threadpool # Import run_in_threadpool
from pydantic import BaseModel, HttpUrl, Field
import shutil
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional
import uuid # For creating unique temp dirs for text uploads
import os

from backend.core.knowledge_base import NBAnalyzerKnowledgeBase, KnowledgeSourceAdditionError
from config import settings
from backend.core.models import QueryRequest, QueryResponse, AddKnowledgeSourceRequest, GenericResponse, AddWikipediaRequest, AddTextFileRequest, AddUrlRequest, AddYouTubeVideosRequest

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define a temporary directory for uploads within the backend structure
TEMP_UPLOAD_DIR = Path(settings.CHROMA_DB_NBA_AGENT) / "temp_uploads_kb"
TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Temporary upload directory ensured at: {TEMP_UPLOAD_DIR}")


# Initialize the global knowledge base instance
# GLOBAL_KB_RECREATE_COLLECTIONS = os.getenv("GLOBAL_KB_RECREATE_COLLECTIONS", "False").lower() == "true"
GLOBAL_KB_RECREATE_COLLECTIONS = False # Set to False for standard operation
logger.info(f"Initializing Global NBAnalyzerKnowledgeBase with recreate_collections={GLOBAL_KB_RECREATE_COLLECTIONS}")

global_knowledge_base_instance: Optional[NBAnalyzerKnowledgeBase] = None
try:
    global_knowledge_base_instance = NBAnalyzerKnowledgeBase(
        recreate_collections=GLOBAL_KB_RECREATE_COLLECTIONS
    )
    logger.info(f"Global KnowledgeBase initialized. recreate_collections={GLOBAL_KB_RECREATE_COLLECTIONS}")
except Exception as e:
    logger.error(f"Failed to initialize Global KnowledgeBase: {e}", exc_info=True)
    # global_knowledge_base_instance remains None, endpoints should check

@router.post("/add_pdf_file/", summary="Upload a PDF file to the Knowledge Base")
async def add_pdf_file(file: UploadFile = File(...)):
    if not global_knowledge_base_instance:
        raise HTTPException(status_code=500, detail="KnowledgeBase not initialized.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file name provided.")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are accepted.")

    unique_dir_name = str(uuid.uuid4())
    temp_pdf_upload_dir = TEMP_UPLOAD_DIR / "pdfs" / unique_dir_name
    temp_pdf_upload_dir.mkdir(parents=True, exist_ok=True)
    
    safe_filename = Path(file.filename).name
    temp_file_path = temp_pdf_upload_dir / safe_filename

    try:
        logger.info(f"Receiving PDF file: {safe_filename} into {temp_pdf_upload_dir}")
        with temp_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"PDF file {safe_filename} saved to {temp_file_path}")
        
        await run_in_threadpool(global_knowledge_base_instance.add_local_pdf_directory, str(temp_pdf_upload_dir))
        logger.info(f"PDF processing for {safe_filename} initiated.")
        
        return {"message": f"PDF file '{safe_filename}' received and processing initiated."}
    except KnowledgeSourceAdditionError as e:
        logger.error(f"KnowledgeSourceAdditionError preparing PDF file {safe_filename} for processing: {e}", exc_info=True)
        if temp_pdf_upload_dir.exists():
            shutil.rmtree(temp_pdf_upload_dir)
            logger.info(f"Cleaned up temporary PDF directory due to processing error: {temp_pdf_upload_dir}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing PDF file {safe_filename}: {e}", exc_info=True)
        if temp_file_path.exists():
            temp_file_path.unlink(missing_ok=True)
        if temp_pdf_upload_dir.exists() and not any(temp_pdf_upload_dir.iterdir()):
            shutil.rmtree(temp_pdf_upload_dir)
        raise HTTPException(status_code=500, detail=f"Error processing PDF file: {str(e)}")
    finally:
        if hasattr(file, 'file') and hasattr(file.file, 'close'): 
            file.file.close()

@router.post("/add_csv_file/", summary="Upload a CSV file to the Knowledge Base")
async def add_csv_file(file: UploadFile = File(...)):
    if not global_knowledge_base_instance:
        raise HTTPException(status_code=500, detail="KnowledgeBase not initialized.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file name provided.")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only CSV files are accepted.")

    unique_dir_name = str(uuid.uuid4())
    temp_csv_upload_dir = TEMP_UPLOAD_DIR / "csvs" / unique_dir_name
    temp_csv_upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = Path(file.filename).name
    temp_file_path = temp_csv_upload_dir / safe_filename

    try:
        logger.info(f"Receiving CSV file: {safe_filename} into {temp_csv_upload_dir}")
        with temp_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"CSV file {safe_filename} saved to {temp_file_path}")

        await run_in_threadpool(global_knowledge_base_instance.add_local_csv_directory, str(temp_csv_upload_dir))
        logger.info(f"CSV processing for {safe_filename} initiated.")
        
        return {"message": f"CSV file '{safe_filename}' received and processing initiated."}
    except KnowledgeSourceAdditionError as e:
        logger.error(f"KnowledgeSourceAdditionError preparing CSV file {safe_filename} for processing: {e}", exc_info=True)
        if temp_csv_upload_dir.exists(): 
            shutil.rmtree(temp_csv_upload_dir)
            logger.info(f"Cleaned up temporary CSV directory due to processing error: {temp_csv_upload_dir}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing CSV file {safe_filename}: {e}", exc_info=True)
        if temp_file_path.exists(): temp_file_path.unlink(missing_ok=True)
        if temp_csv_upload_dir.exists() and not any(temp_csv_upload_dir.iterdir()): shutil.rmtree(temp_csv_upload_dir)
        raise HTTPException(status_code=500, detail=f"Error processing CSV file: {str(e)}")
    finally:
        if hasattr(file, 'file') and hasattr(file.file, 'close'): file.file.close()

@router.post("/add_txt_file/", summary="Upload a TXT file to the Knowledge Base")
async def add_txt_file(file: UploadFile = File(...)):
    if not global_knowledge_base_instance:
        raise HTTPException(status_code=500, detail="KnowledgeBase not initialized.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file name provided.")

    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only TXT files are accepted.")

    unique_dir_name = str(uuid.uuid4())
    temp_text_upload_dir = TEMP_UPLOAD_DIR / "texts" / unique_dir_name
    temp_text_upload_dir.mkdir(parents=True, exist_ok=True)
    
    safe_filename = Path(file.filename).name
    temp_file_path = temp_text_upload_dir / safe_filename

    try:
        logger.info(f"Receiving TXT file: {safe_filename} into {temp_text_upload_dir}")
        with temp_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"TXT file {safe_filename} saved to {temp_file_path}")
        
        await run_in_threadpool(global_knowledge_base_instance.add_local_txt_directory, str(temp_text_upload_dir))
        logger.info(f"TXT file {safe_filename} processing initiated.")
        
        return {"message": f"TXT file '{safe_filename}' received and processing initiated."}
    except KnowledgeSourceAdditionError as e:
        logger.error(f"KnowledgeSourceAdditionError preparing TXT file {safe_filename} for processing: {e}", exc_info=True)
        if temp_text_upload_dir.exists(): 
            shutil.rmtree(temp_text_upload_dir)
            logger.info(f"Cleaned up temporary TXT directory due to processing error: {temp_text_upload_dir}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing TXT file {safe_filename}: {e}", exc_info=True)
        if temp_file_path.exists(): temp_file_path.unlink(missing_ok=True)
        if temp_text_upload_dir.exists() and not any(temp_text_upload_dir.iterdir()): shutil.rmtree(temp_text_upload_dir)
        raise HTTPException(status_code=500, detail=f"Error processing TXT file: {str(e)}")
    finally:
        if hasattr(file, 'file') and hasattr(file.file, 'close'): file.file.close()

@router.post("/add_website_url/", response_model=GenericResponse, summary="Add website URLs to the Knowledge Base")
async def add_website_url_route(request: AddUrlRequest):
    if not global_knowledge_base_instance:
        raise HTTPException(status_code=500, detail="KnowledgeBase not initialized.")
    try:
        str_urls = [str(url) for url in request.urls]
        logger.info(f"Received request to add website URLs: {str_urls}")
        
        await run_in_threadpool(global_knowledge_base_instance.add_website_urls, str_urls, collection_suffix="uploaded_website_batch")
        logger.info(f"Website URLs {str_urls} submitted for processing in background.")
        return GenericResponse(status="success", message=f"Website URLs {str_urls} submitted for background processing.")
    except KnowledgeSourceAdditionError as e:
        logger.error(f"KnowledgeSourceAdditionError preparing website URLs {request.urls} for processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing website URLs {request.urls}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing website URLs: {str(e)}")

@router.post("/add_wikipedia_topics/", response_model=GenericResponse, summary="Add Wikipedia topics to the Knowledge Base")
async def add_wikipedia_topics_route(request: AddWikipediaRequest):
    if not global_knowledge_base_instance:
        raise HTTPException(status_code=500, detail="KnowledgeBase not initialized.")
    try:
        logger.info(f"Received request to add Wikipedia topics: {request.topics}")
        await run_in_threadpool(global_knowledge_base_instance.add_wikipedia_topics, request.topics, collection_suffix="uploaded_wiki_topics")
        logger.info(f"Wikipedia topics {request.topics} submitted for background processing.")
        return GenericResponse(status="success", message=f"Wikipedia topics {request.topics} submitted for background processing.")
    except KnowledgeSourceAdditionError as e:
        logger.error(f"KnowledgeSourceAdditionError preparing Wikipedia topics {request.topics} for processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing Wikipedia topics {request.topics}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing Wikipedia topics: {str(e)}")

@router.get("/status/", summary="Get the status of the Knowledge Base")
async def get_kb_status():
    if not global_knowledge_base_instance:
        return {"status": "KnowledgeBase not initialized", "sources_count": 0, "main_collection_prefix": "N/A"}
    
    # The get_underlying_kb_object might not be needed if NBAnalyzerKnowledgeBase directly exposes source counts
    # combined_kb = global_knowledge_base_instance.get_underlying_kb_object() 
    # source_count = 0
    # if combined_kb and hasattr(combined_kb, 'sources'):
    #     source_count = len(combined_kb.sources)
        
    return {
        "status": "KnowledgeBase Initialized",
        "main_collection_prefix": global_knowledge_base_instance.main_collection_prefix,
        "persist_path": str(global_knowledge_base_instance.vector_db_path), # Assuming vector_db_path exists
        # "combined_sources_count": source_count, # Re-evaluate how to get total sources
        "pdf_source_collections_count": len(global_knowledge_base_instance.get_collections_by_type("pdf")),
        "csv_source_collections_count": len(global_knowledge_base_instance.get_collections_by_type("csv")),
        "website_source_collections_count": len(global_knowledge_base_instance.get_collections_by_type("website")),
        "text_source_collections_count": len(global_knowledge_base_instance.get_collections_by_type("text")),
        "youtube_source_collections_count": len(global_knowledge_base_instance.get_collections_by_type("youtube")),
        "wikipedia_source_collections_count": len(global_knowledge_base_instance.get_collections_by_type("wikipedia")),
        "all_managed_collections": global_knowledge_base_instance.list_all_managed_collections()
    }

@router.post("/query/", response_model=QueryResponse, summary="Query the Knowledge Base")
async def query_kb(request: QueryRequest):
    if not global_knowledge_base_instance:
        raise HTTPException(status_code=500, detail="KnowledgeBase not initialized.")
    try:
        logger.info(f"Received query: {request.query} with num_documents: {request.num_documents}")
        results = await run_in_threadpool(global_knowledge_base_instance.query, request.query, n_results=request.num_documents)
        
        processed_results = []
        if results: 
            for doc_tuple in results: 
                processed_results.append({
                    "content": doc_tuple.get("content", ""), 
                    "metadata": doc_tuple.get("metadata", {}),
                    "score": doc_tuple.get("score") 
                })

        return QueryResponse(documents=processed_results)

    except Exception as e:
        logger.error(f"Error querying KnowledgeBase: {e}", exc_info=True)
        # Construct a more informative error detail
        error_detail = f"Error querying KnowledgeBase: {type(e).__name__} - {str(e)}"
        # Check if it's a TypeError from the query method itself
        if isinstance(e, TypeError) and "query() got an unexpected keyword argument" in str(e):
            error_detail = f"Error processing query: Mismatch in query parameters. {str(e)}"
        elif isinstance(e, TypeError):
             error_detail = f"Error processing query: Type error in query processing. {str(e)}"

        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/initialize_default_pdfs/", summary="Initialize KB with PDFs from a default directory")
async def initialize_default_pdfs():
    if not global_knowledge_base_instance:
        raise HTTPException(status_code=500, detail="KnowledgeBase not initialized.")
    
    default_pdf_path_str = settings.DEFAULT_PDFS_PATH
    if not default_pdf_path_str:
        logger.warning("DEFAULT_PDFS_PATH not set in settings. Skipping default PDF initialization.")
        return {"message": "DEFAULT_PDFS_PATH not set. No default PDFs initialized."}

    default_pdf_path = Path(default_pdf_path_str)
    
    if not default_pdf_path.exists() or not default_pdf_path.is_dir():
        logger.warning(f"Default PDF path {default_pdf_path} does not exist or is not a directory.")
        raise HTTPException(status_code=404, detail=f"Default PDF directory not found at {default_pdf_path}")

    try:
        logger.info(f"Initializing default PDFs from: {default_pdf_path}")
        # Assuming add_local_pdf_directory is thread-safe or called appropriately
        await run_in_threadpool(global_knowledge_base_instance.add_local_pdf_directory, str(default_pdf_path))
        logger.info(f"Default PDF initialization initiated from {default_pdf_path}.")
        return {"message": f"Default PDF initialization from '{default_pdf_path}' initiated."}
    except KnowledgeSourceAdditionError as e: # Catch specific KB error
        logger.error(f"Failed to load PDF source from {default_pdf_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error during default PDF initialization from {default_pdf_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error initializing default PDFs: {str(e)}")

@router.post("/add_youtube_videos/", response_model=GenericResponse, summary="Add YouTube video URLs to the Knowledge Base")
async def add_youtube_videos_route(request: AddYouTubeVideosRequest): # Model expects `urls`
    if not global_knowledge_base_instance:
        raise HTTPException(status_code=500, detail="KnowledgeBase not initialized.")
    try:
        # Ensure access is request.urls as per AddYouTubeVideosRequest model
        str_video_urls = [str(url) for url in request.urls] 
        logger.info(f"Received request to add YouTube videos: {str_video_urls}")
        
        await run_in_threadpool(global_knowledge_base_instance.add_website_urls, str_video_urls, collection_suffix="uploaded_youtube_batch")
        logger.info(f"YouTube videos {str_video_urls} submitted for processing in background.")
        return GenericResponse(status="success", message=f"YouTube videos {str_video_urls} submitted for background processing.")
    except KnowledgeSourceAdditionError as e:
        # Ensure logging uses request.urls
        logger.error(f"KnowledgeSourceAdditionError preparing YouTube videos {request.urls} for processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # Ensure logging uses request.urls
        logger.error(f"Error processing YouTube videos {request.urls}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing YouTube videos: {str(e)}")

@router.get("/list_collections/", summary="List all active KB collections")
async def list_collections() -> List[str]: 
    if not global_knowledge_base_instance:
        raise HTTPException(status_code=500, detail="KnowledgeBase not initialized.")
    try:
        collection_names = await run_in_threadpool(global_knowledge_base_instance.list_all_managed_collections)
        return collection_names
    except Exception as e:
        logger.error(f"Error listing collections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing collections: {str(e)}")

# To make these routes available, they need to be included in the main FastAPI app (e.g., in backend/main.py) 