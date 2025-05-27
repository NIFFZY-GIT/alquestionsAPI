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
                required_headers = ['Unit No', 'Question', 'Correct Answer', 'Wrong Answer 1', 'Wrong Answer 2', 'Wrong Answer 3'] # Adjusted for 4 options total
                # If you want 5 options total, add 'Wrong Answer 4' back and adjust client
                
                if not reader.fieldnames or not all(f in reader.fieldnames for f in required_headers):
                    print(f"Warning: CSV file '{CSV_FILE_PATH}' with encoding '{enc}' is missing required headers or has incorrect format. Headers found: {reader.fieldnames}")
                    continue

                all_questions_data_temp = []
                for i, row in enumerate(reader):
                    # Basic validation for 'Unit No'
                    if not row.get('Unit No') or not row.get('Unit No').strip():
                        print(f"Warning: Row {i+2} in CSV (encoding {enc}) has missing or empty 'Unit No'. Skipping row: {row}")
                        continue
                    # Validate that essential fields for a question are present
                    if not all(row.get(h) and row.get(h).strip() for h in ['Question', 'Correct Answer', 'Wrong Answer 1']):
                        print(f"Warning: Row {i+2} in CSV (encoding {enc}) has missing essential question data. Skipping row: {row}")
                        continue
                    all_questions_data_temp.append(row)
                
                all_questions_data = all_questions_data_temp

                if not all_questions_data:
                    print(f"Warning: CSV file '{CSV_FILE_PATH}' with encoding '{enc}' is empty or contains only headers after validation.")

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
        print(f"INFO during startup: CSV file '{CSV_FILE_PATH}' was loaded but found to be empty or malformed after row validation. API will return 404/503 for question requests.")

except Exception as e:
    print(f"A critical error occurred during application startup logic: {e}")


# +++ HEALTH CHECK ENDPOINT +++
@app.route('/health', methods=['GET'])
def health_check():
    if CSV_LOADED_SUCCESSFULLY and all_questions_data:
        return jsonify(status="ok", message="Application is healthy and data is loaded."), 200
    elif CSV_LOADED_SUCCESSFULLY and not all_questions_data:
        return jsonify(status="ok_empty_data", message="Application is running, but question data is effectively empty."), 200
    else:
        return jsonify(status="error", message="Application is running, but failed to load question data correctly."), 503


@app.route('/questions/unit/<int:unit_id>', methods=['GET'])
def get_single_question_for_unit(unit_id):
    if not CSV_LOADED_SUCCESSFULLY:
        abort(503, description="Service is unavailable due to data loading issues (CSV not loaded).")
    if not all_questions_data:
         abort(503, description="Service is unavailable as question data is empty (CSV loaded but no data).")

    unit_specific_questions_raw = [
        q for q in all_questions_data if q.get('Unit No') == str(unit_id)
    ]

    if not unit_specific_questions_raw:
        abort(404, description=f"No questions found for Unit No: {unit_id}")

    selected_question_data = random.choice(unit_specific_questions_raw)
    question_text = selected_question_data.get('Question', 'Unknown Question')
    correct_answer = selected_question_data.get('Correct Answer', 'Unknown Correct Answer')
    
    # We'll aim for 3 wrong answers to make 4 total options
    wrong_answers_keys = ['Wrong Answer 1', 'Wrong Answer 2', 'Wrong Answer 3'] 
    wrong_answers_raw = [selected_question_data.get(key) for key in wrong_answers_keys]
    
    # Filter out any None or empty string wrong answers
    wrong_answers_filtered = [ans.strip() for ans in wrong_answers_raw if ans and ans.strip()]

    # Ensure we have enough wrong answers, if not, use placeholders (less ideal, better to have good CSV data)
    # For simplicity, we'll assume the CSV provides enough. If not, the options list will be shorter.
    # The client should be prepared for a varying number of options or you should enforce this in CSV.
    # For now, we just take what's available.

    all_options = [correct_answer] + wrong_answers_filtered
    random.shuffle(all_options) # Shuffle correct answer among wrong ones

    # Make sure we have at least 2 options (correct + 1 wrong minimum for a sensible quiz)
    # If you always want 4 options, you'd need more robust handling here or ensure CSV quality
    if len(all_options) < 2:
        # This case should ideally not happen with good CSV data and validation
        print(f"Warning: Not enough options for question: {question_text}. Correct: {correct_answer}, Filtered wrong: {wrong_answers_filtered}")
        # Fallback or error - for now, let it pass, client might show fewer buttons
        # or you could abort(500, "Internal error: Could not format question options")

    formatted_question = {
        "question_id": f"U{unit_id}_{selected_question_data.get('Question')[:20]}", # Optional: create a simple ID
        "question": question_text,
        "options": all_options, # List of 2 to 4 options (or 5 if you use Wrong Answer 4)
        "correct_answer_debug": correct_answer 
    }
    
    return jsonify(formatted_question)

if __name__ == '__main__':
    if not CSV_LOADED_SUCCESSFULLY:
        print("WARNING: Application starting with CSV data load issues. Health check will likely fail or indicate problems.")
    elif not all_questions_data:
        print("WARNING: Application starting, CSV loaded but no data found (or all rows invalid). Endpoints for questions will return issues.")
    else:
        print("Application starting successfully with data loaded.")
    app.run(host='0.0.0.0', port=5001)