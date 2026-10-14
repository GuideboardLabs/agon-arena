#!/usr/bin/env python3
"""Generate a Mermaid ER diagram from agon-bench.db and render it to PNG."""

import sqlite3
import subprocess
import os
import json

DB_PATH = os.path.expanduser("~/Documents/agon-arena/agon-bench.db")
OUTPUT = os.path.expanduser("~/Documents/agon-arena/agon-bench-er.png")
MMD_PATH = OUTPUT.replace('.png', '.mmd')

def get_schema(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in c.fetchall()]
    
    schema = {}
    for table in tables:
        c.execute(f"PRAGMA table_info({table})")
        columns = []
        for col in c.fetchall():
            columns.append({
                'name': col[1],
                'type': col[2],
                'notnull': col[3],
                'pk': col[5],
                'dflt': col[4]
            })
        
        c.execute(f"PRAGMA foreign_key_list({table})")
        fks = []
        for fk in c.fetchall():
            fks.append({
                'from': fk[3],
                'to': fk[4],
                'ref_table': fk[2]
            })
        
        schema[table] = {'columns': columns, 'fks': fks}
    
    conn.close()
    return schema

def generate_mermaid(schema):
    lines = ['---', 'title: Agon-Bench Database Schema', '---', '']
    lines.append('erDiagram')
    
    for table_name, info in schema.items():
        cols = info['columns']
        pk_cols = [c['name'] for c in cols if c['pk']]
        
        # Clean display name
        display = table_name.replace('_', ' ').title()
        lines.append(f'    {table_name} {{')
        
        for col in cols:
            is_pk = col['name'] in pk_cols
            is_fk = any(fk['from'] == col['name'] for fk in info['fks'])
            
            # Map SQLite types to compact types
            t = (col['type'] or 'TEXT').upper()
            if 'INT' in t:
                t = 'int'
            elif 'REAL' in t or 'FLOAT' in t or 'DOUBLE' in t:
                t = 'float'
            elif 'TEXT' in t or 'CHAR' in t or 'VARCHAR' in t:
                t = 'string'
            elif 'BLOB' in t:
                t = 'blob'
            else:
                t = 'string'
            
            pk_mark = 'PK' if is_pk else ''
            fk_mark = 'FK' if is_fk else ''
            nn_mark = 'NOT NULL' if col['notnull'] else 'nullable'
            
            # Combine markers
            markers = ' '.join(filter(None, [pk_mark, fk_mark]))
            
            lines.append(f'        {t} {col["name"]} "{markers}"')
        
        lines.append('    }')
        lines.append('')
    
    # Relationships
    lines.append('    %% Relationships')
    for table_name, info in schema.items():
        for fk in info['fks']:
            # Mermaid: ||--o{ one-to-many, ||--|| one-to-one, }o--|| many-to-one
            # We'll use one-to-many as default
            lines.append(f'    {table_name} ||--o{{ {fk["ref_table"]} : "{fk["from"]} -> {fk["to"]}"')
    
    return '\n'.join(lines)

def main():
    schema = get_schema(DB_PATH)
    mermaid = generate_mermaid(schema)
    
    with open(MMD_PATH, 'w') as f:
        f.write(mermaid)
    
    print(f"Mermaid file: {MMD_PATH}")
    print(f"Tables: {len(schema)}")
    print("---")
    print(mermaid)
    print("---")

if __name__ == '__main__':
    main()
