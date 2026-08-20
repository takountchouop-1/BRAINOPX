from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from fastapi import HTTPException, status


def get_table_column_rules(engine: Engine, table_name: str) -> list[dict]:
    """
    Reads the real constraints of a SQL Server table (data types, NOT NULL,
    UNIQUE, FOREIGN KEY) and turns them into a structured rule set.

    This is the core idea behind section 8 of the brief: validation rules
    come from the actual database schema the script will write to, not
    from free-form AI guessing.
    """
    inspector = inspect(engine)

    if table_name not in inspector.get_table_names():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Table '{table_name}' does not exist in the database.",
        )

    columns = inspector.get_columns(table_name)
    
    # Handle SQL Server's lack of get_unique_constraints
    try:
        unique_constraints = inspector.get_unique_constraints(table_name)
    except NotImplementedError:
        # Fallback for SQL Server - query unique constraints manually
        unique_constraints = _get_unique_constraints_sqlserver(engine, table_name)
    
    pk_constraint = inspector.get_pk_constraint(table_name)
    foreign_keys = inspector.get_foreign_keys(table_name)

    # Build quick lookup sets
    unique_column_names = set()
    for uc in unique_constraints:
        unique_column_names.update(uc.get("column_names", []))
    pk_column_names = set(pk_constraint.get("constrained_columns", []) or [])

    fk_map = {}
    for fk in foreign_keys:
        for local_col, remote_col in zip(fk["constrained_columns"], fk["referred_columns"]):
            fk_map[local_col] = {
                "referred_table": fk["referred_table"],
                "referred_column": remote_col,
            }

    rules = []
    for col in columns:
        col_name = col["name"]
        rules.append(
            {
                "name": col_name,
                "data_type": str(col["type"]),
                "required": (not col["nullable"]) and col_name not in pk_column_names,
                "unique": col_name in unique_column_names or col_name in pk_column_names,
                "foreign_key": fk_map.get(col_name),
            }
        )

    return rules


def _get_unique_constraints_sqlserver(engine: Engine, table_name: str) -> list[dict]:
    """
    Manually query unique constraints for SQL Server.
    SQLAlchemy doesn't implement get_unique_constraints for SQL Server.
    This version is compatible with all SQL Server versions.
    """
    # Simplified query without ORDINAL_POSITION
    query = text("""
        SELECT 
            tc.CONSTRAINT_NAME as name,
            cols.COLUMN_NAME as column_name
        FROM 
            INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            INNER JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE cols 
                ON tc.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
                AND tc.TABLE_NAME = cols.TABLE_NAME
        WHERE 
            tc.TABLE_NAME = :table_name
            AND tc.CONSTRAINT_TYPE = 'UNIQUE'
        ORDER BY 
            tc.CONSTRAINT_NAME
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {'table_name': table_name})
        rows = result.fetchall()
    
    # Group by constraint name
    constraints_dict = {}
    for row in rows:
        name = row[0]
        column = row[1]
        if name not in constraints_dict:
            constraints_dict[name] = {
                'name': name,
                'column_names': []
            }
        constraints_dict[name]['column_names'].append(column)
    
    return list(constraints_dict.values())