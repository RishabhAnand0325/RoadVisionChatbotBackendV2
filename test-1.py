import psycopg2
from psycopg2 import OperationalError

try:
    connection = psycopg2.connect(
        dbname="mydatabase",
        user="myuser",
        password="mypassword",
        host="localhost",
        port="5432"
    )
    print("Connection successful!")
    connection.close()
except OperationalError as e:
    print(f"Error: {e}")