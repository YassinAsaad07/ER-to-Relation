import json
from graphviz import Digraph
import os

def create_relational_diagram(json_path):
    """
    Parses an ER diagram in JSON format and generates a relational model diagram.
    Handles strong/weak entities, all attribute types, and relationships.
    """
    try:
        with open(json_path, "r") as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f"Error: The file '{json_path}' was not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: The file '{json_path}' is not a valid JSON file.")
        return

    Relation = Digraph(comment="Relational Diagram", format="png")
    Relation.attr(splines="spline", bgcolor="white")
    tables = {}
    foreign_keys = []

    # --- Step 1: Initialize all table structures from entities ---
    for entity in data["entities"]:
        table_name = entity["name"].strip()
        tables[table_name] = {'pk': [], 'columns': []}

    # --- Step 2: Process attributes for all entities (Strong and Weak) ---
    for entity in data["entities"]:
        table_name = entity["name"].strip()
        
        # --- WEAK ENTITY LOGIC ---
        if entity.get("isWeak", False):
            owner_name = None
            # Find the identifying relationship to determine the owner
            for rel in data.get("relationships", []):
                if rel.get("isIdentifying"):
                    entities_in_rel = [e['name'] for e in rel['entities']]
                    if table_name in entities_in_rel:
                        owner_name = next((name for name in entities_in_rel if name != table_name), None)
                        break
            
            if not owner_name:
                print(f"Warning: Weak entity '{table_name}' lacks an identifying relationship. Skipping.")
                continue

            # Get owner's PKs to use as foreign keys
            owner_pks = tables[owner_name]['pk']
            fk_columns = [f"{owner_name}_{pk}" for pk in owner_pks]

            # Get weak entity's partial keys and other attributes
            partial_keys = []
            regular_columns = []
            for attr in entity["attributes"]:
                if attr.get("isPartialKey"):
                    partial_keys.append(attr["name"])
                elif "composite" in attr:
                    regular_columns.extend(attr["composite"])
                else:
                    regular_columns.append(attr["name"])
            
            # The weak table's PK is the combination of owner's PKs and its own partial keys
            tables[table_name]['pk'] = fk_columns + partial_keys
            tables[table_name]['columns'] = fk_columns + partial_keys + regular_columns
            
            # Create the foreign key relationships
            for i, pk in enumerate(owner_pks):
                foreign_keys.append({
                    'from_table': table_name, 'from_attr': fk_columns[i],
                    'to_table': owner_name, 'to_attr': pk
                })

        # --- STRONG ENTITY LOGIC ---
        else:
            primary_keys = []
            regular_columns = []
            for attr in entity["attributes"]:
                if attr.get("isPrimaryKey"):
                    if "composite" in attr:
                        primary_keys.extend(attr["composite"])
                    else:
                        primary_keys.append(attr["name"])
            tables[table_name]['pk'] = primary_keys

            for attr in entity["attributes"]:
                attr_name, composite = attr["name"], attr.get("composite", [])
                if attr.get("isMultiValued"):
                    multi_table_name = f"{table_name}_{attr_name}"
                    multi_pk, multi_cols = [], []
                    for pk in primary_keys:
                        fk_col = f"{table_name}_{pk}"
                        multi_cols.append(fk_col)
                        multi_pk.append(fk_col)
                        foreign_keys.append({'from_table': multi_table_name, 'from_attr': fk_col, 'to_table': table_name, 'to_attr': pk})
                    if composite:
                        multi_cols.extend(composite); multi_pk.extend(composite)
                    else:
                        multi_cols.append(attr_name); multi_pk.append(attr_name)
                    tables[multi_table_name] = {'pk': multi_pk, 'columns': multi_cols}
                elif composite:
                    regular_columns.extend(composite)
                elif not attr.get("isPrimaryKey"):
                    regular_columns.append(attr_name)
            tables[table_name]['columns'] = primary_keys + regular_columns


    # --- Step 3: Process relationships to create junction tables and add FKs ---
    for rel in data.get("relationships", []):
        if rel.get("isIdentifying"): continue # Already handled by weak entity logic

        e1_data, e2_data = rel['entities'][0], rel['entities'][1]
        e1_name, e2_name = e1_data["name"], e2_data["name"]
        cardinality = f"{e1_data['cardinality']}:{e2_data['cardinality']}"

        # Handle N:N and 1:1 by creating a new junction table
        if cardinality in ("N:N", "1:1"):
            rel_name = rel['name']
            rel_pk, rel_cols = [], []
            for e_name in [e1_name, e2_name]:
                for pk in tables[e_name]['pk']:
                    fk_col = f"{e_name}_{pk}"
                    rel_cols.append(fk_col); rel_pk.append(fk_col)
                    foreign_keys.append({'from_table': rel_name, 'from_attr': fk_col, 'to_table': e_name, 'to_attr': pk})
            for attr in rel.get("attributes", []): rel_cols.append(attr["name"])
            tables[rel_name] = {'pk': rel_pk, 'columns': rel_cols}
        
        # Handle 1:N and N:1 by adding an FK to the 'many' side
        else:
            many_table, one_table = (e1_name, e2_name) if cardinality == "N:1" else (e2_name, e1_name)
            for pk in tables[one_table]['pk']:
                fk_col = f"{one_table}_{pk}"
                if fk_col not in tables[many_table]['columns']:
                    tables[many_table]['columns'].append(fk_col)
                foreign_keys.append({'from_table': many_table, 'from_attr': fk_col, 'to_table': one_table, 'to_attr': pk})
            for attr in rel.get("attributes", []): tables[many_table]['columns'].append(attr["name"])

    # --- Step 4: Render all nodes (tables) ---
    fk_cols = {(fk['from_table'], fk['from_attr']) for fk in foreign_keys}
    for table_name, table_data in tables.items():
        label = f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">\n'
        label += f'  <TR><TD COLSPAN="2" BGCOLOR="lightblue"><B>{table_name}</B></TD></TR>\n'
        drawn_columns = set()
        for col_name in table_data.get('columns', []):
            if col_name in drawn_columns: continue
            drawn_columns.add(col_name)
            is_pk = col_name in table_data.get('pk', [])
            is_fk = (table_name, col_name) in fk_cols
            key_marker = "PK" if is_pk else "FK" if is_fk else ""
            col_name_formatted = f"<U>{col_name}</U>" if is_pk else col_name
            label += f'  <TR><TD ALIGN="LEFT" PORT="{col_name}">{col_name_formatted}</TD><TD>{key_marker}</TD></TR>\n'
        label += '</TABLE>>'
        Relation.node(table_name, label=label, shape='plain')

    # --- Step 5: Render all edges (foreign keys) ---
    for fk in foreign_keys:
        Relation.edge(f"{fk['from_table']}:{fk['from_attr']}", f"{fk['to_table']}:{fk['to_attr']}")

    Relation.render(filename="my_table", view=True, cleanup=False)
    print("Diagram 'my_table.png' generated successfully.")

# --- Run the script ---
if __name__ == "__main__":
    json_file_path = input("Enter JSON path: ").strip()
    create_relational_diagram(json_file_path)