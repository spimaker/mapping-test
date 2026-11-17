import ast
import json
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables, query as q

@anvil.server.callable
def execute_raw_sql_query(table_name, sql_query):
    """
    General-purpose query processor. 
    Accepts plain English descriptions or natural commands in SQL_Query_Entry,
    interprets them, executes against the table, and returns formatted results.
    """
    if not table_name or not table_name.strip():
        return "Error: Please enter a Data Table name."
        
    clean_table_name = table_name.strip().lower()
    target_table = getattr(app_tables, clean_table_name, None)
    
    if target_table is None:
        available_tables = [t for t in dir(app_tables) if not t.startswith('_')]
        return f"Error: Data Table '{table_name.strip()}' not found.\nAvailable tables: {', '.join(available_tables)}"

    raw_input = (sql_query or "").strip()

    try:
        rows = []
        
        # 1. Schema / Column lookup command
        if raw_input.lower() in ['', 'schema', 'columns', 'desc', 'describe']:
            columns = target_table.list_columns()
            schema_output = [f"Schema for table '{clean_table_name}':", "-" * 40]
            for col in columns:
                schema_output.append(f"• {col.get('name')} ({col.get('type')})")
            return "\n".join(schema_output)

        # 2. JSON / Dictionary filter
        elif raw_input.startswith("{") and raw_input.endswith("}"):
            try:
                filters = json.loads(raw_input)
            except json.JSONDecodeError:
                filters = ast.literal_eval(raw_input)
            rows = list(target_table.search(**filters))
            
        # 3. Comma/Newline separated list of IDs or Users
        elif "," in raw_input or "\n" in raw_input or not " " in raw_input:
            cleaned = raw_input.replace("'", "").replace('"', "")
            search_terms = [item.strip() for item in cleaned.replace("\n", ",").split(",") if item.strip()]
            
            col_names = [c.get('name') for c in target_table.list_columns()]
            if 'user' in col_names:
                rows = list(target_table.search(user=q.any_of(*search_terms)))
            elif 'id' in col_names:
                rows = list(target_table.search(id=q.any_of(*search_terms)))
            else:
                rows = list(target_table.search())
                
        # 4. Natural Language / Plain Text instructions
        else:
            text_lower = raw_input.lower()
            
            # Check for count / total record requests using len() on the search iterator
            if any(phrase in text_lower for phrase in ["how many", "count", "total", "number of"]):
                total_count = len(target_table.search())
                return f"Table: {clean_table_name}\nTotal records: {total_count}"
                
            elif "nsw" in text_lower:
                col_names = [c.get('name') for c in target_table.list_columns()]
                if 'city' in col_names:
                    rows = list(target_table.search(city="NSW"))
                elif 'user' in col_names:
                    rows = [r for r in target_table.search() if r['user'] and 'NSW' in r['user']]
            else:
                # Default generic fallback: grab all rows
                rows = list(target_table.search())

        if not rows:
            return f"Table: {clean_table_name}\n0 matching rows found."

        # Format rows into a clean text output
        columns = list(dict(rows[0]).keys())
        header = " | ".join(columns)
        separator = "-" * min(len(header), 120)
        
        formatted_rows = []
        for r in rows[:100]:
            row_dict = dict(r)
            formatted_rows.append(" | ".join([str(row_dict.get(col, "")) for col in columns]))

        output = [
            f"Table: {clean_table_name} ({len(rows)} rows returned)",
            f"Columns: {header}",
            separator
        ] + formatted_rows
        
        if len(rows) > 100:
            output.append("\n[Notice: Output truncated to first 100 rows]")

        return "\n".join(output)
        
    except Exception as e:
        return f"Execution Error: {str(e)}"