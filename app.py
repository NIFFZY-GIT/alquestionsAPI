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
    file_opened_successfully_locally = False
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
                elif 'Unit No' not in all_questions_data[0]:
                    print(f"Warning: 'Unit No' column not found in the first data row of '{CSV_FILE_PATH}' with encoding '{enc}'. Data might be malformed.")
                    all_questions_data = []
                    continue

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
        print(f"INFO during startup: CSV file '{CSV_FILE_PATH}' was loaded but found to be empty or malformed. API will return 404/503 for question requests.")

except Exception as e:
    print(f"A critical error occurred during application startup logic: {e}")


# +++ HEALTH CHECK ENDPOINT +++
@app.route('/health', methods=['GET'])
def health_check():
    if CSV_LOADED_SUCCESSFULLY and all_questions_data:
        return jsonify(status="ok", message="Application is healthy and data is loaded."), 200
    elif CSV_LOADED_SUCCESSFULLY and not all_questions_data:
        return jsonify(status="ok_empty_data", message="Application is running, but question data is empty."), 200
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
    
    wrong_answers = [
        selected_question_data.get('Wrong Answer 1', 'Fallback Option W1'), # Added fallbacks if CSV cells are empty
        selected_question_data.get('Wrong Answer 2', 'Fallback Option W2'),
        selected_question_data.get('Wrong Answer 3', 'Fallback Option W3'),
        selected_question_data.get('Wrong Answer 4', 'Fallback Option W4')
    ]
    # Ensure all options are strings and not empty, otherwise provide a fallback to avoid UI issues.
    # This is especially important if a CSV cell for a wrong answer is truly blank.
    wrong_answers_filtered = [wa if wa and wa.strip() else f"Option {i+1}" for i, wa in enumerate(wrong_answers)]


    all_options = [correct_answer] + wrong_answers_filtered
    random.shuffle(all_options)

    # Ensure we still have 5 options even if some were identical after filtering or fallbacks
    # This scenario is less likely with distinct fallbacks, but good for robustness.
    # For simplicity, the current approach relies on CSV having 1 correct + 4 distinct wrong answers.
    # If CSV has empty cells for wrong answers, the fallbacks will be used.

    formatted_question = {
        "question": question_text,
        "options": all_options, # Should be a list of 5 options
        "correct_answer_debug": correct_answer # For client-side checking
    }
    
    return jsonify(formatted_question)

if __name__ == '__main__':
    if not CSV_LOADED_SUCCESSFULLY:
        print("WARNING: Application starting with CSV data load issues. Health check will likely fail or indicate problems.")
    elif not all_questions_data:
        print("WARNING: Application starting, CSV loaded but no data found. Endpoints for questions will return issues.")
    # Run on 0.0.0.0 to make it accessible from other devices on your network (like Unity running on the same machine)
    app.run(host='0.0.0.0', debug=True, port=5001)