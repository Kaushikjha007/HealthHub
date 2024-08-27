import mindsdb_sdk
import sqlite3
import time
import traceback
import os

MINDSDB_HOST = 'http://127.0.0.1'
MINDSDB_PORT = 47334

def connect_to_mindsdb():
    for attempt in range(3):
        try:
            print(f"Attempting to connect to MindsDB locally (attempt {attempt + 1})...")
            server = mindsdb_sdk.connect(f"{MINDSDB_HOST}:{MINDSDB_PORT}")
            print("Connected successfully to MindsDB!")
            return server
        except Exception as error:
            print(f"Failed to connect to MindsDB. Error: {error}")
            if attempt < 2:
                print("Retrying in 5 seconds...")
                time.sleep(5)
    return None


def connect_to_sqlite(database_name):
    try:
        conn = sqlite3.connect(database_name)
        cursor = conn.cursor()
        print(f"Connected to SQLite database '{database_name}' successfully.")
        return conn, cursor
    except sqlite3.Error as e:
        print(f"SQLite database connection failed. Error: {e}")
        return None, None


def create_patients_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY,
            age INTEGER,
            gender TEXT,
            symptom1 TEXT,
            symptom2 TEXT,
            symptom3 TEXT,
            diagnosis TEXT,
            diagnosis_explain TEXT
        );
    """)
    print("Table 'patients' created (or already exists).")

def predict_diagnosis(server, age, gender, symptom1, symptom2, symptom3):
    try:
        query = f"""
        SELECT diagnosis, diagnosis_explain
        FROM health_diagnosis.diagnosis_predictor
        WHERE age = {age}
        AND gender = '{gender}'
        AND symptom1 = '{symptom1.strip()}'
        AND symptom2 = '{symptom2.strip()}'
        AND symptom3 = '{symptom3.strip()}'
        """
        print(f"Running prediction query: {query}")
        result = server.query(query)
        result_list = result.fetch()
        print(f"Prediction result: {result_list}")
        if result_list:
            return result_list[0]['diagnosis'], result_list[0].get('diagnosis_explain', 'No explanation provided')
        else:
            return "Unable to predict", "No results returned from the model"
    except Exception as e:
        print(f"Error during prediction: {e}")
        return "Unable to predict", "An error occurred during prediction"

def get_user_input():
    while True:
        try:
            age = int(input("Enter patient's age: "))
            if age < 0:
                print("Age cannot be negative. Please try again.")
                continue
            gender = input("Enter patient's gender (M/F): ").strip().upper()
            if gender not in ('M', 'F'):
                print("Invalid input for gender. Please enter 'M' or 'F'.")
                continue
            symptom1 = input("Enter first symptom: ")
            symptom2 = input("Enter second symptom: ")
            symptom3 = input("Enter third symptom: ")
            return age, gender, symptom1, symptom2, symptom3
        except ValueError:
            print("Invalid input for age. Please enter a valid integer.")

def setup_mindsdb_project(server):
    try:
        server.projects.create(name='health_diagnosis')
        print("Project 'health_diagnosis' created successfully.")
    except Exception as e:
        if "already exists" in str(e):
            print("Project 'health_diagnosis' already exists.")
        else:
            print(f"Error creating project: {e}")

def setup_or_get_model(server):
    try:
        query = """
        CREATE MODEL health_diagnosis.diagnosis_predictor
        PREDICT diagnosis
        USING
            engine = 'mindsdb',
            integration = 'health_data',
            query = 'SELECT * FROM patients';
        """
        server.query(query)
        print("Model 'diagnosis_predictor' created successfully.")

        # Check model status
        model_status = server.models.get(name='diagnosis_predictor', project='health_diagnosis').status
        print(f"Model 'diagnosis_predictor' status: {model_status}")
        if model_status['status'] != 'complete':
            print(f"Model training not complete. Status: {model_status}")
    except Exception as e:
        if "already exists" in str(e):
            print("Model 'diagnosis_predictor' already exists.")
        else:
            print(f"Error creating model: {e}")

def main():
    server = connect_to_mindsdb()
    if server is None:
        print("Failed to connect to MindsDB after multiple attempts. Exiting.")
        return

    try:
        existing_dbs = server.databases.list()
        print(f"Existing databases: {[db.name for db in existing_dbs]}")
        
        # Create the SQLite database file if it doesn't exist
        db_file_path = 'health_data.db'
        if 'health_data' not in [db.name for db in existing_dbs]:
            if not os.path.exists(db_file_path):
                # Create the empty database file
                conn = sqlite3.connect(db_file_path)
                conn.close()  # Close the connection after creating the file
                print("SQLite database 'health_data.db' created.")
            
            server.databases.create(
                name='health_data',
                engine='sqlite',
                connection_args={
                    'db_file': db_file_path
                }
            )
            print("SQLite database added as a data source.")
        else:
            print("SQLite database 'health_data' already exists as a data source.")
    except Exception as e:
        print(f"Error handling SQLite database as a data source: {e}")
        return

    conn, cursor = connect_to_sqlite(db_file_path)
    if conn is None or cursor is None:
        print("Failed to connect to SQLite database. Exiting.")
        return

    try:
        create_patients_table(cursor)  # Create the patients table if it doesn't exist

        cursor.execute("SELECT COUNT(*) FROM patients")
        row_count = cursor.fetchone()[0]
        print(f"Number of rows in 'patients' table: {row_count}")
        if row_count == 0:
            print("Warning: 'patients' table is empty. Please insert data before proceeding.")
            return

        setup_mindsdb_project(server)
        setup_or_get_model(server)

        print("Model 'diagnosis_predictor' is ready for predictions.")

        while True:
            print("\nHealthcare Diagnosis Assistant")
            user_data = get_user_input()
            diagnosis, explanation = predict_diagnosis(server, *user_data)
            print(f"\nPredicted diagnosis: {diagnosis}")
            print(f"Explanation: {explanation}")

            if input("\nDo you want to make another prediction? (y/n): ").lower() != 'y':
                break

        print("Thank you for using the Healthcare Diagnosis Assistant!")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print("Error details:")
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
