import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables, query as q

@anvil.server.callable
def execute_raw_sql_query(table_name, sql_query):
    """
    Executes a query against the specified data table using the already-connected database
    and returns formatted results or an error message.
    """
    if not table_name or not table_name.strip():
        return "Error: Please enter a Data Table name."
        
    if not sql_query or not sql_query.strip():
        return "Error: Query string is empty."
        
    clean_table_name = table_name.strip().lower()
    
    # Verify the target table exists in app_tables
    target_table = getattr(app_tables, clean_table_name, None)
    if target_table is None:
        return f"Error: Data Table '{table_name.strip()}' not found in app_tables."

    try:
        # Execute using your active database cursor / connection
        # (Replace `db_cursor` below with your existing connected cursor variable)
        db_cursor.execute(sql_query)
        
        if db_cursor.description:
            columns = [desc[0] for desc in db_cursor.description]
            rows = db_cursor.fetchall()
            
            if not rows:
                return f"Query executed on '{clean_table_name}'. 0 rows returned."
                
            header = " | ".join(columns)
            separator = "-" * len(header)
            formatted_rows = [" | ".join([str(val) for val in row]) for row in rows]
            
            return f"Table: {clean_table_name}\nColumns: {header}\n{separator}\n" + "\n".join(formatted_rows)
        else:
            db_conn.commit()
            return f"Query executed successfully on '{clean_table_name}'. Rows affected: {db_cursor.rowcount}"
            
    except Exception as e:
        return f"Query Execution Error: {str(e)}"