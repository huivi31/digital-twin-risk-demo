# -*- coding: utf-8 -*-
import sqlite3
import json
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "digital_twin.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 存储投喂的资料 (fed_materials)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fed_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        category TEXT,
        timestamp REAL
    )
    ''')
    
    # 2. 存储黑话词典 (fed_slang)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fed_slang (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term TEXT NOT NULL,
        meaning TEXT,
        timestamp REAL
    )
    ''')
    
    # 3. 存储绕过案例 (fed_cases)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fed_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original TEXT,
        bypass TEXT NOT NULL,
        technique TEXT,
        timestamp REAL
    )
    ''')
    
    # 4. 存储对抗历史 (battle_history)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS battle_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        persona_id TEXT,
        persona_name TEXT,
        category TEXT,
        target_topic TEXT,
        attack_data TEXT,  -- JSON
        defense_data TEXT, -- JSON
        result_data TEXT,  -- JSON
        timestamp REAL
    )
    ''')
    
    # 5. 存储系统状态 (SYSTEM_STATE - 主要是 rules)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_state (
        key TEXT PRIMARY KEY,
        value TEXT -- JSON
    )
    ''')

    # 6. 存储 Agent 进化状态 (peripheral_agents)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS agent_states (
        agent_id TEXT PRIMARY KEY,
        success_count INTEGER,
        fail_count INTEGER,
        evolution_level REAL,
        learned_techniques TEXT -- JSON
    )
    ''')

    conn.commit()
    conn.close()

# 初始化数据库
init_db()

def save_material(text, category):
    conn = get_db_connection()
    conn.execute('INSERT INTO fed_materials (text, category, timestamp) VALUES (?, ?, ?)',
                 (text, category, time.time()))
    conn.commit()
    conn.close()

def load_materials():
    conn = get_db_connection()
    rows = conn.execute('SELECT text, category, timestamp FROM fed_materials').fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_slang(term, meaning):
    conn = get_db_connection()
    conn.execute('INSERT INTO fed_slang (term, meaning, timestamp) VALUES (?, ?, ?)',
                 (term, meaning, time.time()))
    conn.commit()
    conn.close()

def load_slang():
    conn = get_db_connection()
    rows = conn.execute('SELECT term, meaning, timestamp FROM fed_slang').fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_case(original, bypass, technique):
    conn = get_db_connection()
    conn.execute('INSERT INTO fed_cases (original, bypass, technique, timestamp) VALUES (?, ?, ?, ?)',
                 (original, bypass, technique, time.time()))
    conn.commit()
    conn.close()

def load_cases():
    conn = get_db_connection()
    rows = conn.execute('SELECT original, bypass, technique, timestamp FROM fed_cases').fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_battle(record):
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO battle_history 
        (persona_id, persona_name, category, target_topic, attack_data, defense_data, result_data, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        record['persona_id'], record['persona_name'], record['category'], record['target_topic'],
        json.dumps(record['attack']), json.dumps(record['defense']), json.dumps(record['result']),
        record['timestamp']
    ))
    conn.commit()
    conn.close()

def load_battle_history(limit=100):
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM battle_history ORDER BY timestamp DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    history = []
    for row in rows:
        d = dict(row)
        d['attack'] = json.loads(d.pop('attack_data'))
        d['defense'] = json.loads(d.pop('defense_data'))
        d['result'] = json.loads(d.pop('result_data'))
        history.append(d)
    return history

def save_system_rules(rules):
    conn = get_db_connection()
    conn.execute('INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)',
                 ('rules', json.dumps(rules)))
    conn.commit()
    conn.close()

def load_system_rules():
    conn = get_db_connection()
    row = conn.execute('SELECT value FROM system_state WHERE key = ?', ('rules',)).fetchone()
    conn.close()
    return json.loads(row['value']) if row else []

def save_agent_state(agent_id, state):
    conn = get_db_connection()
    conn.execute('''
        INSERT OR REPLACE INTO agent_states 
        (agent_id, success_count, fail_count, evolution_level, learned_techniques)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        agent_id, state['success_count'], state['fail_count'], 
        state['evolution_level'], json.dumps(state['learned_techniques'])
    ))
    conn.commit()
    conn.close()

def load_all_agent_states():
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM agent_states').fetchall()
    conn.close()
    states = {}
    for row in rows:
        d = dict(row)
        states[d['agent_id']] = {
            "success_count": d['success_count'],
            "fail_count": d['fail_count'],
            "evolution_level": d['evolution_level'],
            "learned_techniques": json.loads(d['learned_techniques'])
        }
    return states
