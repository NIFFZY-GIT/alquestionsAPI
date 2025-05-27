from flask import Flask, jsonify, abort
import csv
import random

app = Flask(__name__)

# --- Configuration ---
CSV_FILE_PATH = 'questions.csv' # Make sure this file exists in the same directory
CSV_LOADED_SUCCESSFULLY = False # Global flag to indicate CSV status

# --- Load and prepare data at startup ---
all_questions_data = []
try:
    encodings_to_try = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
    file_opened_successfully_locally = False
    for enc in encodings_to_try:
        try:
            with open(CSV_FILE_PATH, mode='r', encoding=enc) as infile:
                reader = csv.DictReader(infile)
                # **MODIFIED: Added 'Wrong Answer 4'**
                required_headers = ['Unit No', 'Question', 'Correct Answer', 'Wrong Answer 1', 'Wrong Answer 2', 'Wrong Answer 3', 'Wrong Answer 4']
                
                if not reader.fieldnames or not all(f in reader.fieldnames for f in required_headers):
                    print(f"Warning: CSV file '{CSV_FILE_PATH}' with encoding '{enc}' is missing required headers or has incorrect format. Headers found: {reader.fieldnames}")
                    continue

                all_questions_data_temp = []
                # **MODIFIED: Fields required for a 5-option question (1 correct + 4 wrong)**
                essential_question_fields = ['Question', 'Correct Answer', 'Wrong Answer 1', 'Wrong Answer 2', 'Wrong Answer 3', 'Wrong Answer 4']

                for i, row in enumerate(reader):
                    # Basic validation for 'Unit No'
                    if not row.get('Unit No') or not row.get('Unit No').strip():
                        print(f"Warning: Row {i+2} in CSV (encoding {enc}) has missing or empty 'Unit No'. Skipping row: {row}")
                        continue

                    # **MODIFIED: Validate that all essential fields for a 5-option question are present and non-empty**
                    if not all(row.get(h) and row.get(h).strip() for h in essential_question_fields):
                        print(f"Warning: Row {i+2} in CSV (encoding {enc}) has missing or empty essential question/answer data. Skipping row: {row}")
                        continue
                    
                    # **NEW: Validate for 4 distinct wrong answers different from the correct answer**
                    correct_answer_val = row.get('Correct Answer').strip()
                    raw_wrong_answers = [
                        row.get('Wrong Answer 1', '').strip(),
                        row.get('Wrong Answer 2', '').strip(),
                        row.get('Wrong Answer 3', '').strip(),
                        row.get('Wrong Answer 4', '').strip()
                    ]
                    
                    # Filter out empty strings and ensure wrong answers are not the same as the correct answer, then get unique ones
                    distinct_valid_wrong_answers = {
                        wa for wa in raw_wrong_answers if wa and wa != correct_answer_val
                    }

                    if len(distinct_valid_wrong_answers) < 4:
                        print(f"Warning: Row {i+2} (encoding {enc}) does not provide 4 distinct wrong answers different from the correct answer ('{correct_answer_val}'). Found: {distinct_valid_wrong_answers}. Skipping row: {row}")
                        continue
                        
                    all_questions_data_temp.append(row) # Only add if all validations pass
                
                all_questions_data = all_questions_data_temp

                if not all_questions_data:
                    print(f"Warning: CSV file '{CSV_FILE_PATH}' with encoding '{enc}' is empty or contains no valid 5-option questions after validation.")

                print(f"Successfully loaded CSV '{CSV_FILE_PATH}' with encoding: {enc}")
                file_opened_successfully_locally = True
                CSV_LOADED_SUCCESSFULLY = True
                break
        except UnicodeDecodeError:
            print(f"Failed to decode CSV '{CSV_FILE_PATH}' with encoding: {enc}")
            continue
        except FileNotFoundError:
            print(f"ERROR: The CSV file '{CSV_FILE_PATH}' was not found.")
            break 
        except Exception as e:
            print(f"An unexpected error occurred while processing CSV '{CSV_FILE_PATH}' with encoding {enc}: {e}")
            continue

    if not file_opened_successfully_locally and not CSV_LOADED_SUCCESSFULLY:
        print(f"CRITICAL ERROR during startup: Could not read or parse the CSV file '{CSV_FILE_PATH}' with any attempted encodings.")
    elif not all_questions_data and file_opened_successfully_locally:
        print(f"INFO during startup: CSV file '{CSV_FILE_PATH}' was loaded but found to be empty or contained no valid 5-option questions after row validation. API will return 404/503 for question requests.")

except Exception as e:
    print(f"A critical error occurred during application startup logic: {e}")


# +++ HEALTH CHECK ENDPOINT +++
@app.route('/health', methods=['GET'])
def health_check():
    if CSV_LOADED_SUCCESSFULLY and all_questions_data:
        return jsonify(status="ok", message="Application is healthy and data is loaded."), 200
    elif CSV_LOADED_SUCCESSFULLY and not all_questions_data: # CSV was read but no valid data rows
        return jsonify(status="ok_empty_data", message="Application is running, but question data is effectively empty (no valid 5-option questions)."), 200
    else: # CSV_LOADED_SUCCESSFULLY is False
        return jsonify(status="error", message="Application is running, but failed to load question data correctly."), 503


@app.route('/questions/unit/<int:unit_id>', methods=['GET'])
def get_single_question_for_unit(unit_id):
    if not CSV_LOADED_SUCCESSFULLY:
        abort(503, description="Service is unavailable due to data loading issues (CSV not loaded).")
    if not all_questions_data: # This means no questions passed the 5-option validation
         abort(503, description="Service is unavailable as question data is empty (no valid 5-option questions found).")

    unit_specific_questions_raw = [
        q for q in all_questions_data if q.get('Unit No') == str(unit_id)
    ]

    if not unit_specific_questions_raw:
        abort(404, description=f"No valid 5-option questions found for Unit No: {unit_id}")

    selected_question_data = random.choice(unit_specific_questions_raw)
    
    question_text = selected_question_data.get('Question') # Already validated non-empty
    correct_answer = selected_question_data.get('Correct Answer') # Already validated non-empty
    
    # **MODIFIED: Retrieve the 4 guaranteed wrong answers**
    # These are guaranteed by the startup validation to be non-empty, distinct from each other,
    # and distinct from the correct_answer.
    wrong_answers = [
        selected_question_data.get('Wrong Answer 1'),
        selected_question_data.get('Wrong Answer 2'),
        selected_question_data.get('Wrong Answer 3'),
        selected_question_data.get('Wrong Answer 4')
    ]
    
    all_options = [correct_answer] + wrong_answers # This will create a list of 5 options
    random.shuffle(all_options)

    formatted_question = {
        # Using a combination of Unit No and Question start as a more stable ID
        "question_id": f"U{selected_question_data.get('Unit No')}_{question_text[:20].replace(' ', '_')}",
        "question": question_text,
        "options": all_options, # Should now always be a list of 5 distinct options
        "correct_answer_debug": correct_answer 
    }
    
    return jsonify(formatted_question)

if __name__ == '__main__':
    if not CSV_LOADED_SUCCESSFULLY:
        print("WARNING: Application starting with CSV data load issues. Health check will likely fail or indicate problems.")
    elif not all_questions_data:
        print("WARNING: Application starting, CSV loaded but no valid 5-option data found (or all rows invalid). Endpoints for questions will return issues.")
    else:
        print("Application starting successfully with data loaded.")
    app.run(host='0.0.0.0', port=5001)