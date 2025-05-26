from flask import Flask, jsonify, abort
import csv
import random

app = Flask(__name__)

# --- Configuration ---
CSV_FILE_PATH = 'questions.csv'

# --- Load and prepare data at startup ---
all_questions_data = []
try:
    # Robust CSV loading (attempts multiple common encodings)
    encodings_to_try = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
    file_opened_successfully = False
    for enc in encodings_to_try:
        try:
            with open(CSV_FILE_PATH, mode='r', encoding=enc) as infile:
                reader = csv.DictReader(infile)
                # Basic header check
                required_headers = ['Unit No', 'Question', 'Correct Answer', 'Wrong Answer 1', 'Wrong Answer 2', 'Wrong Answer 3', 'Wrong Answer 4']
                if not reader.fieldnames or not all(f in reader.fieldnames for f in required_headers):
                    print(f"Warning: CSV file '{CSV_FILE_PATH}' with encoding '{enc}' is missing required headers or has incorrect format. Headers found: {reader.fieldnames}")
                    continue # Try next encoding

                all_questions_data = list(reader) # Read all rows

                if not all_questions_data:
                    print(f"Warning: CSV file '{CSV_FILE_PATH}' with encoding '{enc}' is empty or contains only headers.")
                    # If empty, still consider it "opened" to avoid falling into the final error,
                    # but all_questions_data will be empty, leading to 404s later.
                elif 'Unit No' not in all_questions_data[0]: # Check first data row for critical column
                    print(f"Warning: 'Unit No' column not found in the first data row of '{CSV_FILE_PATH}' with encoding '{enc}'. Data might be malformed.")
                    all_questions_data = [] # Clear data if it seems malformed
                    continue

                print(f"Successfully loaded CSV '{CSV_FILE_PATH}' with encoding: {enc}")
                file_opened_successfully = True
                break # Exit loop once successfully opened and read
        except UnicodeDecodeError:
            print(f"Failed to decode CSV '{CSV_FILE_PATH}' with encoding: {enc}")
            continue
        except FileNotFoundError:
            print(f"ERROR: The CSV file '{CSV_FILE_PATH}' was not found.")
            exit()
        except Exception as e: # Catch other potential errors during file processing
            print(f"An unexpected error occurred while processing CSV '{CSV_FILE_PATH}' with encoding {enc}: {e}")
            continue

    if not file_opened_successfully:
        print(f"CRITICAL ERROR: Could not read or parse the CSV file '{CSV_FILE_PATH}' with any attempted encodings.")
        print("Please ensure the file exists, has correct headers (Unit No, Question, Correct Answer, Wrong Answer 1-4), and is in a common encoding (preferably UTF-8).")
        exit()
    elif not all_questions_data and file_opened_successfully:
        print(f"INFO: CSV file '{CSV_FILE_PATH}' was loaded but found to be empty. API will return 404 for all unit requests.")


except Exception as e: # Catch errors during the overall loading process
    print(f"A critical error occurred during application startup: {e}")
    exit()


@app.route('/questions/unit/<int:unit_id>', methods=['GET'])
def get_single_question_for_unit(unit_id):
    # Filter questions for the requested unit
    unit_specific_questions_raw = [
        q for q in all_questions_data if q.get('Unit No') == str(unit_id)
    ]

    if not unit_specific_questions_raw:
        abort(404, description=f"No questions found for Unit No: {unit_id}")

    # Randomly select ONE question from the filtered list
    selected_question_data = random.choice(unit_specific_questions_raw)

    # Prepare the response for the single selected question
    question_text = selected_question_data.get('Question', 'Unknown Question')
    correct_answer = selected_question_data.get('Correct Answer', 'Unknown Correct Answer')
    
    potential_wrong_answers = [
        selected_question_data.get('Wrong Answer 1', ''),
        selected_question_data.get('Wrong Answer 2', ''),
        selected_question_data.get('Wrong Answer 3', ''),
        selected_question_data.get('Wrong Answer 4', '')
    ]
    # Filter out any empty strings if some wrong answers might be blank in the CSV
    potential_wrong_answers = [ans for ans in potential_wrong_answers if ans and ans.strip()]

    if not potential_wrong_answers:
        # Fallback if a question somehow has NO wrong answers listed in the CSV
        selected_wrong_answers = ["Option B (fallback)", "Option C (fallback)", "Option D (fallback)"]
    elif len(potential_wrong_answers) < 3:
        # If fewer than 3 actual wrong answers are available, use what's there.
        # You could also choose to pad with placeholders if a fixed number of options is critical for the client.
        selected_wrong_answers = random.sample(potential_wrong_answers, len(potential_wrong_answers))
    else:
        # Randomly select 3 distinct wrong answers from the available ones
        selected_wrong_answers = random.sample(potential_wrong_answers, 3)

    # Combine correct answer with the selected wrong answers
    all_options = [correct_answer] + selected_wrong_answers
    random.shuffle(all_options) # Shuffle the order of options

    # Structure the single question response
    formatted_question = {
        "question": question_text,
        "options": all_options,
        "correct_answer_debug": correct_answer # Optional: for easier debugging or if client needs it explicitly
    }
    
    # Return a single JSON object, not a list
    return jsonify(formatted_question)

if __name__ == '__main__':
    app.run(debug=True, port=5001)