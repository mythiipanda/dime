import sys
from pathlib import Path
import os
# import csv # No longer directly used in this version
if __name__ == "__main__" and __package__ is None:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

from typing import List, Optional, Union, Type, Any, Tuple
import re
from urllib.parse import urlparse, parse_qs
# import shutil # No longer directly used if temp dirs are handled by routes

from agno.knowledge.combined import CombinedKnowledgeBase
from agno.knowledge.pdf import PDFKnowledgeBase
from agno.knowledge.csv import CSVKnowledgeBase
from agno.knowledge.text import TextKnowledgeBase
# Removed: from agno.knowledge.wikipedia import WikipediaKnowledgeBase
# Removed: from agno.knowledge.youtube import YouTubeKnowledgeBase
from agno.document.chunking.fixed import FixedSizeChunking

import logging
from agno.vectordb.chroma import ChromaDb
from agno.embedder.google import GeminiEmbedder
from config import settings
from agno.document import Document
logger = logging.getLogger(__name__)

class KnowledgeSourceAdditionError(Exception):
    """Custom exception for errors during knowledge source addition."""
    pass

CHROMA_DB_PERSIST_PATH = settings.CHROMA_DB_NBA_AGENT
Path(CHROMA_DB_PERSIST_PATH).mkdir(parents=True, exist_ok=True)

DEFAULT_CHUNKING_STRATEGY = FixedSizeChunking(chunk_size=1000, overlap=200)

def sanitize_for_collection_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    if len(name) > 63:
        name = name[:63]
    if len(name) < 3:
        name = f"{name}___"
    if not name[0].isalnum():
        name = "a" + name[1:]
    if len(name) > 1 and not name[-1].isalnum():
        name = name[:-1] + "a"
    if len(name) < 3:
        name = f"{name:<3}".replace(" ", "_")
    if len(name) > 63:
        name = name[:63]
        if not name[-1].isalnum() and len(name) > 0:
             name = name[:-1] + 'z'
    name = name.lower()
    if ".." in name:
        name = name.replace("..", "_")
    if len(name) < 3:
        name = (name + "pad")[:3]
    if len(name) > 63:
        name = name[:63]
        if not name[-1].isalnum() and len(name) > 0:
             name = name[:-1] + 'z'
    return name

# Removed get_youtube_video_id as it's no longer used for special KB handling

class NBAnalyzerKnowledgeBase:
    def __init__(self, recreate_collections: bool = False):
        self.recreate_collections = recreate_collections
        self.embedder = GeminiEmbedder(
            id="text-embedding-004",
            api_key=settings.GOOGLE_API_KEY,
            dimensions=768
        )
        self.chroma_db_path = settings.CHROMA_DB_NBA_AGENT
        os.makedirs(self.chroma_db_path, exist_ok=True) # Ensures path exists
        self.local_pdf_sources: List[PDFKnowledgeBase] = []
        self.local_csv_sources: List[CSVKnowledgeBase] = []
        self.local_txt_sources: List[TextKnowledgeBase] = []
        
        self.combined_kb: Optional[CombinedKnowledgeBase] = None
        self._initialize_combined_kb()

    def _initialize_combined_kb(self):
        logger.info(f"[KB_DEBUG_COMBINED] Entering _initialize_combined_kb. Current sources: PDF({len(self.local_pdf_sources)}), CSV({len(self.local_csv_sources)}), TXT({len(self.local_txt_sources)})")
        all_sources = (
            self.local_pdf_sources + 
            self.local_csv_sources + 
            self.local_txt_sources
        )
        if not all_sources:
            logger.info("[KB_LOG] No sources to combine yet.")
            self.combined_kb = None
            logger.info(f"[KB_DEBUG_COMBINED] Exiting _initialize_combined_kb early (no sources).")
            return

        logger.info(f"[KB_LOG] Attempting to initialize CombinedKnowledgeBase with {len(all_sources)} sources.")
        try:
            combined_collection_name = self._get_collection_name("combined", "orchestrator")
            combined_vector_db = ChromaDb(
                collection=combined_collection_name,
                path=self.chroma_db_path,
                embedder=self.embedder
            )
            self.combined_kb = CombinedKnowledgeBase(
                sources=all_sources,
                vector_db=combined_vector_db,
                embedder=self.embedder
            )
            logger.info(f"[KB_DEBUG_COMBINED] Loading CombinedKnowledgeBase (recreate={self.recreate_collections}).")
            self.combined_kb.load(recreate=self.recreate_collections)
            logger.info(f"[KB_LOG] CombinedKnowledgeBase initialized and loaded with {len(self.combined_kb.sources)} sources, main collection: {combined_collection_name}")
        except Exception as e:
            logger.error(f"Failed to initialize or load CombinedKnowledgeBase: {e}", exc_info=True)
            self.combined_kb = None

    def _get_collection_name(self, prefix: str, identifier: str) -> str:
        s_prefix = sanitize_for_collection_name(prefix)
        s_identifier = sanitize_for_collection_name(identifier)
        
        max_identifier_len = 63 - len(s_prefix) - 1
        if len(s_identifier) > max_identifier_len:
            s_identifier = s_identifier[:max_identifier_len]
        
        if not s_identifier: # Simplified check for empty
            s_identifier = "default"
        
        if len(s_identifier) > 0 and not s_identifier[-1].isalnum():
            s_identifier = s_identifier[:-1] + 'z'

        full_name = f"{s_prefix}_{s_identifier}"
        return sanitize_for_collection_name(full_name)

    def add_local_pdf_directory(self, dir_path: str):
        logger.info(f"[KB_DEBUG] Attempting to add PDF directory: {dir_path}")
        if not os.path.isdir(dir_path):
            logger.error(f"PDF directory not found: {dir_path}")
            return f"Failed to add PDF directory: Directory not found." # Return message

        dir_name = os.path.basename(dir_path)
        collection_name_str = self._get_collection_name("pdfdir", dir_name)
        
        if any(kb.vector_db.collection_name == collection_name_str for kb in self.local_pdf_sources):
            logger.info(f"PDF directory {dir_path} with collection {collection_name_str} already added. Skipping.")
            return f"PDF directory {dir_path} already added." # Return message

        try:
            pdf_vector_db = ChromaDb(collection=collection_name_str, path=self.chroma_db_path, embedder=self.embedder)
            pdf_kb = PDFKnowledgeBase(
                path=dir_path,
                vector_db=pdf_vector_db,
                embedder=self.embedder,
            )
            logger.info(f"[KB_DEBUG] Loading PDFKnowledgeBase (recreate={self.recreate_collections})")
            pdf_kb.load(recreate=self.recreate_collections)
            logger.info(f"[KB_DEBUG] PDFKnowledgeBase loaded successfully.")
            
            self.local_pdf_sources.append(pdf_kb)
            logger.info(f"[KB_DEBUG] PDFKnowledgeBase object created and appended to local sources.")
            self._initialize_combined_kb()
            logger.info(f"PDF directory {dir_path} processed and loaded into collection: {collection_name_str}.")
            return f"Successfully added PDF directory: {dir_path}."
        except Exception as e:
            logger.error(f"Failed to add PDF directory {dir_path} during KB object lifecycle: {e}", exc_info=True)
            return f"Failed to add PDF directory: {e}"

    def add_local_csv_directory(self, dir_path: str):
        logger.info(f"[KB_DEBUG] Attempting to add CSV directory: {dir_path}")
        if not os.path.isdir(dir_path):
            logger.error(f"CSV directory not found: {dir_path}")
            return f"Failed to add CSV directory: Directory not found."

        dir_name = os.path.basename(dir_path)
        collection_name_str = self._get_collection_name("csvdir", dir_name)

        if any(kb.vector_db.collection_name == collection_name_str for kb in self.local_csv_sources):
            logger.info(f"CSV directory {dir_path} with collection {collection_name_str} already added.")
            return f"CSV directory {dir_path} already added."
        
        try:
            csv_kb = CSVKnowledgeBase(
                path=dir_path,
                vector_db=ChromaDb(collection=collection_name_str, path=self.chroma_db_path, embedder=self.embedder),
                embedder=self.embedder,
            )
            csv_kb.load(recreate=self.recreate_collections)
            logger.info(f"[KB_DEBUG] CSVKnowledgeBase loaded successfully.")
            self.local_csv_sources.append(csv_kb)
            logger.info(f"[KB_DEBUG] CSVKnowledgeBase object created and appended to local sources. Load is currently skipped.")
            self._initialize_combined_kb()
            logger.info(f"CSV directory {dir_path} processed and loaded into collection: {collection_name_str}.")
            return f"Successfully added CSV directory: {dir_path}."
        except Exception as e:
            logger.error(f"Failed to add CSV directory {dir_path}: {e}", exc_info=True)
            return f"Failed to add CSV directory: {e}"

    def add_local_txt_directory(self, dir_path: str):
        logger.info(f"[KB_DEBUG] Attempting to add TXT directory: {dir_path}")
        if not os.path.isdir(dir_path):
            logger.error(f"TXT directory not found: {dir_path}")
            return f"Failed to add TXT directory: Directory not found."

        dir_name = os.path.basename(dir_path)
        collection_name_str = self._get_collection_name("txtdir", dir_name)

        if any(kb.vector_db.collection_name == collection_name_str for kb in self.local_txt_sources):
            logger.info(f"TXT directory {dir_path} with collection {collection_name_str} already added.")
            return f"TXT directory {dir_path} already added."
        
        try:
            txt_kb = TextKnowledgeBase(
                path=dir_path,
                vector_db=ChromaDb(collection=collection_name_str, path=self.chroma_db_path, embedder=self.embedder),
                embedder=self.embedder,
            )
            txt_kb.load(recreate=self.recreate_collections)
            logger.info(f"[KB_DEBUG] TextKnowledgeBase loaded successfully.")
            self.local_txt_sources.append(txt_kb)
            logger.info(f"[KB_DEBUG] TextKnowledgeBase object created and appended to local sources. Load is currently skipped.")
            self._initialize_combined_kb()
            logger.info(f"TXT directory {dir_path} processed and loaded into collection: {collection_name_str}.")
            return f"Successfully added TXT directory: {dir_path}."
        except Exception as e:
            logger.error(f"Failed to add TXT directory {dir_path}: {e}", exc_info=True)
            return f"Failed to add TXT directory: {e}"

    def add_website_url(self, url: str, max_links: int = 5): # max_links is unused currently
        # All URLs are now treated as generic links for the agent to handle with tools.
        # No direct KB ingestion for websites, YouTube, or Wikipedia here.
        logger.info(f"Received website URL: {url}. This URL type is noted but not processed for direct knowledge base ingestion. Agent should use tools like web crawlers or YouTube tools if needed.")
        # No KB object is created, no collection name needed for this.
        # self._initialize_combined_kb() # No new KB source added, so no need to reinitialize combined_kb.
        return f"Website URL {url} noted. Agent will use tools to access content if required."

    def add_website_urls(self, urls: List[str], collection_suffix: str = "websites_batch", chunking_strategy: Optional[Any] = None, max_links_per_url: int = 1, max_depth_per_url: int = 1):
        if not urls:
            logger.warning("[KB_LOG] add_website_urls called with empty URL list.")
            return "No URLs provided."
        
        processed_messages = []
        for i, url_item in enumerate(urls):
            if not url_item or not isinstance(url_item, str):
                logger.warning(f"[KB_LOG] Invalid URL at index {i}: {url_item}. Skipping.")
                processed_messages.append(f"Skipped invalid URL at index {i}: {url_item}")
                continue
            try:
                # Delegate to the simplified add_website_url
                message = self.add_website_url(url_item, max_links=max_links_per_url)
                processed_messages.append(message)
            except Exception as e: # Should be caught by add_website_url, but as a fallback
                logger.error(f"[KB_LOG] Unexpected error adding website URL {url_item} from batch: {e}", exc_info=True)
                processed_messages.append(f"Error adding URL {url_item}: {e}")
        
        logger.info(f"[KB_LOG] Processed {len(urls)} URLs from the batch via add_website_urls.")
        return "Batch URL processing complete. " + " | ".join(processed_messages)


    def query(self, query_text: str, n_results: int = 5) -> List[Tuple[Document, float]]:
        if not self.combined_kb:
            logger.warning("CombinedKnowledgeBase is not initialized. No sources added or loaded yet.")
            return []
        try:
            # Assuming combined_kb.search is robust enough or we add checks
            # The actual .load() calls for individual KBs are currently commented out, 
            # so this query will likely return empty results or results from an empty/stale combined_kb.
            raw_results = self.combined_kb.search(query=query_text, num_documents=n_results) 
            
            processed_results = []
            for res in raw_results:
                if isinstance(res, tuple) and len(res) == 2 and hasattr(res[0], 'content'):
                    processed_results.append(res)
                elif hasattr(res, 'content'):
                    processed_results.append((res, 0.0)) 
                else:
                    logger.warning(f"Query raw_result is an unexpected format, skipping: {type(res)}.")
            
            logger.info(f"Query: '{query_text}', Processed {len(processed_results)} results.")
            return processed_results
        except Exception as e:
            logger.error(f"Error querying CombinedKnowledgeBase: {e}", exc_info=True)
            return []

    def get_underlying_kb_object(self) -> Optional[CombinedKnowledgeBase]:
        return self.combined_kb

    def list_available_collections(self) -> List[str]:
        collections = []
        # Only PDF, CSV, TXT sources remain
        for kb_list in [self.local_pdf_sources, self.local_csv_sources, self.local_txt_sources]:
            for kb in kb_list:
                if hasattr(kb, 'vector_db') and hasattr(kb.vector_db, 'collection_name'):
                    collections.append(kb.vector_db.collection_name)
        return list(set(collections))

    # Removed async_search as it wasn't fully aligned and query can be run in threadpool by FastAPI
    # Removed _get_or_create_kb_for_source as it was not implemented
    # Removed add_youtube_video_urls method (now handled by add_website_urls -> add_website_url)
    # Removed add_wikipedia_topics method

    async def initialize_default_knowledge(self):
        default_pdf_dir = Path(__file__).resolve().parent.parent / "pdfs"
        if default_pdf_dir.is_dir() and any(default_pdf_dir.glob("*.pdf")):
            logger.info(f"[KB_LOG] Initializing with default PDFs from: {default_pdf_dir}")
            try:
                self.add_local_pdf_directory(str(default_pdf_dir)) # Will also have its load skipped
                logger.info(f"[KB_LOG] Successfully initiated loading of default PDFs.")
            except Exception as e:
                logger.error(f"[KB_LOG] Error initiating loading of default PDFs: {e}", exc_info=True)
        else:
            logger.info(f"[KB_LOG] Default PDF directory not found or empty: {default_pdf_dir}")

        default_csv_dir = Path(__file__).resolve().parent.parent / "csvs"
        if default_csv_dir.is_dir() and any(default_csv_dir.glob("*.csv")):
            logger.info(f"[KB_LOG] Initializing with default CSVs from: {default_csv_dir}")
            try:
                self.add_local_csv_directory(str(default_csv_dir)) # Will also have its load skipped
                logger.info(f"[KB_LOG] Successfully initiated loading of default CSVs.")
            except Exception as e:
                logger.error(f"[KB_LOG] Error initiating loading of default CSVs: {e}", exc_info=True)
        else:
            logger.info(f"[KB_LOG] Default CSV directory not found or empty: {default_csv_dir}")

# Main block for testing removed as it's better to use dedicated test scripts.
