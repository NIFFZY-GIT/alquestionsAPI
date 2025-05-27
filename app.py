from flask import Flask, jsonify, abort
import csv
import random

app = Flask(__name__)

# --- Configuration ---
CSV_FILE_PATH = 'questions.csv'
CSV_LOADED_SUCCESSFULLY = False # Global flag to indicate CSV status

# --- Load and prepare data at startup ---
all_questions_data = []
try:
    encodings_to_try = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
    file_opened_successfully_locally = False # Use a local var for the loop
    for enc in encodings_to_try:
        try:
            with open(CSV_FILE_PATH, mode='r', encoding=enc) as infile:
                reader = csv.DictReader(infile)
                required_headers = ['Unit No', 'Question', 'Correct Answer', 'Wrong Answer 1', 'Wrong Answer 2', 'Wrong Answer 3', 'Wrong Answer 4']
                if not reader.fieldnames or not all(f in reader.fieldnames for f in required_headers):
                    print(f"Warning: CSV file '{CSV_FILE_PATH}' with encoding '{enc}' is missing required headers or has incorrect format. Headers found: {reader.fieldnames}")
                    continue

                all_questions_data = list(reader)

                if not all_questions_data:
                    print(f"Warning: CSV file '{CSV_FILE_PATH}' with encoding '{enc}' is empty or contains only headers.")
                elif 'Unit No' not in all_questions_data[0]: # Check if first data row has 'Unit No'
                    print(f"Warning: 'Unit No' column not found in the first data row of '{CSV_FILE_PATH}' with encoding '{enc}'. Data might be malformed.")
                    all_questions_data = [] # Invalidate data if essential column missing in content
                    continue

                print(f"Successfully loaded CSV '{CSV_FILE_PATH}' with encoding: {enc}")
                file_opened_successfully_locally = True
                CSV_LOADED_SUCCESSFULLY = True # Set global flag on success
                break
        except UnicodeDecodeError:
            print(f"Failed to decode CSV '{CSV_FILE_PATH}' with encoding: {enc}")
            continue
        except FileNotFoundError:
            print(f"ERROR: The CSV file '{CSV_FILE_PATH}' was not found.")
            # Don't exit immediately, let health check report issue
            break # Break from encoding loop, CSV_LOADED_SUCCESSFULLY will be False
        except Exception as e:
            print(f"An unexpected error occurred while processing CSV '{CSV_FILE_PATH}' with encoding {enc}: {e}")
            continue

    if not file_opened_successfully_locally and not CSV_LOADED_SUCCESSFULLY: # Check if we never managed to open/parse
        print(f"CRITICAL ERROR during startup: Could not read or parse the CSV file '{CSV_FILE_PATH}' with any attempted encodings.")
        # CSV_LOADED_SUCCESSFULLY remains False
    elif not all_questions_data and file_opened_successfully_locally:
        print(f"INFO during startup: CSV file '{CSV_FILE_PATH}' was loaded but found to be empty or malformed after header checks. API will return 404 for all unit requests if data is truly empty.")
        # CSV_LOADED_SUCCESSFULLY is True (file opened), but data is empty

except Exception as e:
    print(f"A critical error occurred during application startup logic: {e}")
    # CSV_LOADED_SUCCESSFULLY remains False


# +++ HEALTH CHECK ENDPOINT +++
@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    Returns 200 if the app is running and the CSV was loaded and contains data.
    Returns 200 with a specific message if CSV was loaded but is empty.
    Returns 503 if the CSV failed to load, as the app is not fully functional.
    """
    if CSV_LOADED_SUCCESSFULLY and all_questions_data: # Check if CSV loaded AND has data
        return jsonify(status="ok", message="Application is healthy and data is loaded."), 200
    elif CSV_LOADED_SUCCESSFULLY and not all_questions_data:
        return jsonify(status="ok_empty_data", message="Application is running, but question data is empty (CSV might be empty or malformed after headers)."), 200 # Still OK for app running
    else:
        return jsonify(status="error", message="Application is running, but failed to load question data correctly."), 503 # Service Unavailable


@app.route('/questions/unit/<int:unit_id>', methods=['GET'])
def get_single_question_for_unit(unit_id):
    if not CSV_LOADED_SUCCESSFULLY: # Primary check for CSV load status
        abort(503, description="Service is unavailable due to data loading issues. Please check logs.")
    if not all_questions_data: # Check if data is empty even if CSV was "loaded"
         abort(404, description="No question data available. The source CSV might be empty or improperly formatted.")

    unit_specific_questions_raw = [
        q for q in all_questions_data if q.get('Unit No') == str(unit_id)
    ]

    if not unit_specific_questions_raw:
        abort(404, description=f"No questions found for Unit No: {unit_id}")

    selected_question_data = random.choice(unit_specific_questions_raw)
    question_text = selected_question_data.get('Question', 'Unknown Question')
    correct_answer = selected_question_data.get('Correct Answer', 'Unknown Correct Answer')
    
    # Get all four wrong answers directly from the CSV columns
    # Use .get(key, '') to default to an empty string if a column is missing for a row or is empty
    wrong_answer_1 = selected_question_data.get('Wrong Answer 1', '')
    wrong_answer_2 = selected_question_data.get('Wrong Answer 2', '')
    wrong_answer_3 = selected_question_data.get('Wrong Answer 3', '')
    wrong_answer_4 = selected_question_data.get('Wrong Answer 4', '')

    # Combine correct answer and all four wrong answers
    all_options = [
        correct_answer,
        wrong_answer_1,
        wrong_answer_2,
        wrong_answer_3,
        wrong_answer_4
    ]
    
    # Shuffle the combined list of 5 options
    random.shuffle(all_options)

    formatted_question = {
        "question": question_text,
        "options": all_options, # This will now be a list of 5 options
        "correct_answer_debug": correct_answer
    }
    
    return jsonify(formatted_question)

if __name__ == '__main__':
    if not CSV_LOADED_SUCCESSFULLY:
        print("WARNING: Application starting with CSV data load issues. Health check will likely fail or indicate problems.")
    elif not all_questions_data:
        print("WARNING: Application starting, CSV loaded but no data found. Endpoints for questions will return 404 or 503.")

    app.run(debug=True, port=5001)