import mysql.connector
import pandas as pd
import streamlit as st

def get_connection():
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"],
            port=st.secrets["mysql"].get("port", 3306)
        )
    except mysql.connector.Error as err:
        st.error(f"Koneksi Database Gagal: {err}")
        return None

def fetch_data(query):
    """Mengambil data dari MySQL ke DataFrame"""
    conn = get_connection()
    if conn:
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    return pd.DataFrame()

def execute_query(query, val=None):
    """Menjalankan INSERT, UPDATE, atau DELETE"""
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        try:
            if val:
                cursor.execute(query, val)
            else:
                cursor.execute(query)
            conn.commit()
            return True
        except mysql.connector.Error as err:
            st.error(f"Gagal Eksekusi: {err}")
            return False
        finally:
            conn.close()