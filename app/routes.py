from flask import render_template, request, abort, url_for, redirect
from app import app # Import the app instance from app/__init__.py
from app.models import (
    get_all_medicaments, get_medicaments_count, get_medicament_by_cis,
    search_medicaments, search_medicaments_count # Import search functions
)
import math

PER_PAGE = 20

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
    return render_template('update_placeholder.html')
