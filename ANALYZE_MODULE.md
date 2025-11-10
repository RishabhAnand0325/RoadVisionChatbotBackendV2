## Directory Structure:
analyze/
    |-- db/
        |-- schema.py <- Database schema for the analyze submodule. One Table.
    |-- models/
        |-- pydantic_models.py <- Contains data models (function return types, API schemes etc.)
    |-- repositories/
        |-- repository.py <- Repository layer. Contains all database operations.
    |-- services/
        |-- service.py <- Service layer. All business logic (filtering, sorting etc.) will be done here
    |-- scripts/
        |-- analyze_module.py <- Entry point for the analyze submodule

## TODOs
function: analyze_one_tender(tdr)
    |-- tdr: One tender id (Eg. 5054356, 5567565 etc.)
    |-- return: None
    |-- side effects: Long running process, will write to the "tender_analysis" table in the database

function: get_wishlisted_tenders()
    |-- return: List of tender ids
