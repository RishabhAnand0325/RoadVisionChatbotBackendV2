import psycopg2
from psycopg2 import OperationalError

def list_users():
    try:
        # Connect to the database
        connection = psycopg2.connect(
            dbname="ciegall",
            user="roadvision",
            password="FlyMeToTheMoon",
            host="localhost",
            port="5432"
        )
        
        cursor = connection.cursor()
        
        # SQL query to fetch specific columns
        # We check for 'users' table. If your table is named 'user', change it below.
        query = "SELECT id, email, employee_id, full_name FROM users;"
        
        cursor.execute(query)
        users = cursor.fetchall()
        
        print(f"\n✅ Found {len(users)} users:\n")
        print(f"{'ID':<5} | {'Employee ID':<15} | {'Email':<30} | {'Name'}")
        print("-" * 75)
        
        for user in users:
            # Handle potential None values safely
            uid = str(user[0])
            em_id = str(user[2]) if user[2] else "N/A"
            email = str(user[1])
            name = str(user[3]) if user[3] else "N/A"
            
            print(f"{uid:<5} | {em_id:<15} | {email:<30} | {name}")

    except OperationalError as e:
        print(f"❌ Connection Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Hint: If the error says 'relation users does not exist', try changing the table name to 'user' in the query.")
    finally:
        if 'connection' in locals() and connection:
            cursor.close()
            connection.close()

if __name__ == "__main__":
    list_users()