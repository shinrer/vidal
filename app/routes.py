from flask import render_template, request, abort, url_for, redirect, Markup
from app import app # Import the app instance from app/__init__.py
from app.models import (
    get_all_medicaments, get_medicaments_count, get_medicament_by_cis,
    search_medicaments, search_medicaments_count
)
from app.ai_models import search_similar_rcp_chunks, answer_question_with_rag # Import for RAG Q&A
from app.ai_processing.llm_interface import get_llm_response # To check if LLM interface is available
from app.update_utils import load_metadata, save_metadata # For update process
import math
import subprocess # For running external scripts
import sys # To get current python interpreter
from pathlib import Path # For script paths
import datetime # For updating metadata timestamps

PER_PAGE = 20

# Define paths to the update scripts (assuming they are in the project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD_SCRIPT_PATH = PROJECT_ROOT / "download_bdpm.py"
IMPORT_SCRIPT_PATH = PROJECT_ROOT / "import_structured_data.py"
CRAWL_SCRIPT_PATH = PROJECT_ROOT / "crawl_rcp.py"
PREPROCESS_SCRIPT_PATH = PROJECT_ROOT / "app" / "ai_processing" / "preprocess_text.py"
EMBEDDING_SCRIPT_PATH = PROJECT_ROOT / "app" / "ai_processing" / "generate_embeddings.py"

# Import for AI resource reloading
from app.ai_models import load_ai_resources

@app.route('/')
@app.route('/medicaments')
def medicament_list():
    """
    Route for displaying a paginated list of medicaments.
    """
    try:
        page = request.args.get('page', 1, type=int)
        if page < 1:
            page = 1 # Ensure page is at least 1
    except ValueError: # If page is not an int
        page = 1
        
    name_filter = request.args.get('name_filter', None)
    substance_filter = request.args.get('substance_filter', None)

    filters = {}
    if name_filter and name_filter.strip(): # Add if not None and not empty/whitespace
        filters['name'] = name_filter.strip()
    if substance_filter and substance_filter.strip():
        filters['substance'] = substance_filter.strip()
        
    offset = (page - 1) * PER_PAGE
    
    try:
        # Pass the filters dictionary to model functions
        medicaments = get_all_medicaments(limit=PER_PAGE, offset=offset, filter_criteria=filters if filters else None)
        total_count = get_medicaments_count(filter_criteria=filters if filters else None)
    except Exception as e: # Catch potential DB connection errors from models
        # Log the error properly in a real application
        print(f"Error fetching medicaments from database: {e}")
        abort(500, description="Database error occurred.") # Internal Server Error
        return # Should not be reached due to abort

    if not medicaments and page > 1:
        # If no medicaments found on a page that is not the first,
        # it could mean the user requested a page beyond the valid range.
        # Redirect to the last valid page or first page.
        # For simplicity, redirect to first page or handle as appropriate.
        # Or, let the template handle "No medicaments found." if total_count is also 0.
        # Here, we'll just let the template show "No medicaments" if the list is empty.
        pass


    total_pages = math.ceil(total_count / PER_PAGE) if total_count > 0 else 1
    if page > total_pages and total_pages > 0 : # if requested page is out of bounds
        # abort(404) # Or redirect to last page:
        return render_template('medicament_list.html', 
                               medicaments=[], 
                               page=page, 
                               total_pages=total_pages,
                               error_message=f"Page {page} is out of range. Last page is {total_pages}.")


    return render_template('medicament_list.html', 
                           medicaments=medicaments, 
                           page=page, 
                           total_pages=total_pages,
                           current_filters=filters) # Pass current filters for pagination links

@app.route('/medicament/<string:code_cis>')
def medicament_detail(code_cis: str):
    """
    Route for displaying the details of a single medicament.
    """
    try:
        medicament_data = get_medicament_by_cis(code_cis)
    except Exception as e: # Catch potential DB connection errors from models
        print(f"Error fetching medicament {code_cis} from database: {e}")
        abort(500, description="Database error occurred.")
        return 

    if medicament_data is None:
        abort(404) # Not Found
    
    return render_template('medicament_detail.html', medicament=medicament_data)


@app.route('/search_results')
def search_results():
    """
    Route for displaying search results for medicaments.
    """
    query = request.args.get('query', '').strip()
    try:
        page = request.args.get('page', 1, type=int)
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    if not query:
        # If query is empty, redirect to the main medicament list or show a specific message/page
        return redirect(url_for('medicament_list'))

    offset = (page - 1) * PER_PAGE

    try:
        medicaments_results = search_medicaments(query, limit=PER_PAGE, offset=offset)
        total_count = search_medicaments_count(query)
    except Exception as e:
        print(f"Error during search for query '{query}': {e}")
        abort(500, description="Database error during search.")
        return

    total_pages = math.ceil(total_count / PER_PAGE) if total_count > 0 else 1
    if page > total_pages and total_pages > 0:
         return render_template('search_results.html',
                               medicaments=[],
                               page=page,
                               total_pages=total_pages,
                               query=query,
                               error_message=f"Page {page} is out of range. Last page is {total_pages}.")


    return render_template('search_results.html',
                           medicaments=medicaments_results,
                           page=page,
                           total_pages=total_pages,
                           query=query)

@app.route('/update-db-placeholder')
def update_database_placeholder():
    """
    Placeholder route for the database update functionality.
    """
    return render_template('update_placeholder.html') # Will be replaced/renamed


@app.route('/admin/update-database', methods=['GET', 'POST'])
def trigger_update():
    """
    Handles the database update process.
    GET: Displays a confirmation page with metadata.
    POST: Triggers the update scripts and shows their output.
    """
    metadata = load_metadata()

    if request.method == 'POST':
        script_outputs = []
        overall_success = True # Track if all scripts run successfully

        def run_script(script_path: Path, script_name: str):
            nonlocal overall_success # Allow modification of outer scope variable
            output_log = f"--- Running {script_name} ---\n"
            try:
                # Ensure script_path is absolute for subprocess
                absolute_script_path = str(script_path.resolve())
                result = subprocess.run(
                    [sys.executable, absolute_script_path],
                    capture_output=True,
                    text=True,
                    check=False, # Do not raise exception on non-zero exit
                    cwd=PROJECT_ROOT # Run script from project root
                )
                output_log += result.stdout
                if result.stderr:
                    output_log += f"\n--- Errors from {script_name} ---\n"
                    output_log += result.stderr
                
                if result.returncode != 0:
                    output_log += f"\n--- {script_name} finished with error (return code: {result.returncode}) ---\n"
                    overall_success = False # Mark overall success as false
                else:
                    output_log += f"\n--- {script_name} finished successfully ---\n"
            except FileNotFoundError:
                output_log += f"ERROR: Script not found at {script_path}\n"
                overall_success = False
            except Exception as e:
                output_log += f"ERROR: An unexpected error occurred while trying to run {script_name}: {e}\n"
                overall_success = False
            
            script_outputs.append(output_log)
            return result.returncode if 'result' in locals() else -1 # Return code or -1 if script not found

        # Run the scripts
        # Note: download_bdpm.py requires manual input if not a new version and not in test mode.
        # This might hang here if not handled (e.g. by running download_bdpm.py with a flag for non-interactive mode if possible)
        # For now, assuming manual step is handled or script is modified for non-interactive updates.
        
        log_info("Starting database update process via web trigger...") # Use app's logger if available

        # 1. Download script
        run_script(DOWNLOAD_SCRIPT_PATH, "download_bdpm.py")
        # Currently, we continue even if download fails, import might still work if files are present.

        # 2. Import script
        # Only run import if download was perceived as successful or if we always want to try
        # For simplicity, we run it. If download failed to get new files, import will use old ones or fail if none.
        run_script(IMPORT_SCRIPT_PATH, "import_structured_data.py")

        # 3. Crawl script
        # Similar logic for crawl script
        crawl_rc_returncode = run_script(CRAWL_SCRIPT_PATH, "crawl_rcp.py")

        # --- AI Processing Scripts ---
        # Only run AI scripts if previous steps were generally successful
        # (e.g., import and crawl didn't critically fail to provide data)
        # For this, we check overall_success.
        # A more granular check might be based on specific return codes or flags.
        
        if overall_success: # Check if download, import, crawl were successful
            log_info("Proceeding to AI data processing steps...")
            
            # 4. Preprocess text for embeddings
            preprocess_returncode = run_script(PREPROCESS_SCRIPT_PATH, "preprocess_text.py")
            if preprocess_returncode != 0:
                log_error("preprocess_text.py failed. Subsequent AI steps might be affected or skipped.")
                # overall_success is already False due to run_script internal logic

            # 5. Generate embeddings
            if overall_success: # Only run if preprocess was successful
                embedding_returncode = run_script(EMBEDDING_SCRIPT_PATH, "generate_embeddings.py")
                if embedding_returncode != 0:
                    log_error("generate_embeddings.py failed.")
                    # overall_success is already False
            else:
                script_outputs.append("Skipping generate_embeddings.py due to previous script failure.")
        else:
            script_outputs.append("Skipping AI data processing scripts due to failures in earlier update stages.")


        # After all scripts (including AI ones)
        if overall_success:
            metadata['last_successful_full_update_date'] = datetime.datetime.now().isoformat()
            log_info("Full database update process (including AI steps) completed successfully via web trigger.")
            
            # Reload AI resources
            log_info("Attempting to reload AI resources...")
            if load_ai_resources(force_reload=True):
                app.config['AI_RESOURCES_LOADED'] = True
                log_info("AI resources reloaded successfully.")
                script_outputs.append("\n--- AI resources reloaded successfully. ---")
            else:
                app.config['AI_RESOURCES_LOADED'] = False
                log_error("Failed to reload AI resources after update.")
                script_outputs.append("\n--- ERROR: Failed to reload AI resources after update. Semantic features might use outdated data. ---")
        else:
            log_error("Full database update process completed with one or more errors via web trigger.")
            # last_successful_full_update_date is NOT updated if any script fails
        
        # `last_download_attempt_date` and other specific dates are updated by individual scripts.
        # `save_metadata` is also called by individual scripts.
        # However, we save again here to capture `last_successful_full_update_date`.
        save_metadata(metadata) 

        # Render status page
        return render_template('update_status.html', 
                               script_output=Markup("<br>".join(script_outputs).replace("\n", "<br>")),
                               overall_success=overall_success)

    # For GET request:
    return render_template('update_confirmation.html', metadata=metadata)


# Helper for logging within routes if needed (can be expanded)
def log_info(message):
    print(f"INFO: {message}", file=sys.stderr)

def log_error(message):
    print(f"ERROR: {message}", file=sys.stderr)


@app.route('/semantic-search', methods=['GET', 'POST'])
def semantic_search_page():
    """
    Route for semantic search of RCP documents.
    """
    query = None
    results = None
    ai_resources_available = app.config.get('AI_RESOURCES_LOADED', False)

    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query and ai_resources_available:
            try:
                results = search_similar_rcp_chunks(query, top_k=5)
            except Exception as e:
                log_error(f"Error during semantic search for query '{query}': {e}")
                # Optionally, pass an error message to the template
                # For now, results will remain None or empty, and template handles "no results"
        elif not ai_resources_available:
            log_warning("Semantic search attempted but AI resources are not loaded.")
            # Message about AI resources not loaded will be shown in template
    
    # For GET request, or POST with no query, just display the page
    # If query was from POST, it will be passed to pre-fill the form
    return render_template('semantic_search.html', 
                           query=query, 
                           results=results,
                           app_config_ai_resources_loaded=ai_resources_available)


# Helper for logging within routes if needed (can be expanded)
# log_info and log_error are already defined below trigger_update.
# Add log_warning if desired.
def log_warning(message):
    print(f"WARNING: {message}", file=sys.stderr)

@app.route('/qa', methods=['GET', 'POST'])
def qa_page():
    """
    Route for the RAG Question/Answering page.
    """
    user_question = None
    qa_result = None
    ai_resources_loaded = app.config.get('AI_RESOURCES_LOADED', False)
    # Check if the get_llm_response function itself is available (i.e., ollama was imported)
    llm_interface_available = get_llm_response is not None 

    if request.method == 'POST':
        user_question = request.form.get('user_question', '').strip()
        if user_question and ai_resources_loaded and llm_interface_available:
            try:
                log_info(f"QA Page: Received question: '{user_question}'")
                qa_result = answer_question_with_rag(user_question)
                log_info(f"QA Page: RAG result: {qa_result.get('answer', 'No answer field')[:100]}...") # Log snippet of answer
            except Exception as e:
                log_error(f"Error during RAG processing for question '{user_question}': {e}")
                # qa_result might remain None or be a default error from answer_question_with_rag
                if qa_result is None: # Ensure qa_result is a dict for the template
                    qa_result = {
                        'answer': "An unexpected error occurred while processing your question.",
                        'retrieved_context': "",
                        'retrieved_chunks': []
                    }
        elif not ai_resources_loaded:
            log_warning("QA attempt but core AI resources are not loaded.")
        elif not llm_interface_available:
            log_warning("QA attempt but LLM interface is not available.")
        elif not user_question:
            log_info("QA attempt with empty question.")


    return render_template('question_answering.html',
                           user_question=user_question,
                           qa_result=qa_result,
                           app_config_ai_resources_loaded=ai_resources_loaded,
                           llm_interface_available=llm_interface_available)
