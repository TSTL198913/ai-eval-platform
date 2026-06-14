import psycopg2

try:
    conn = psycopg2.connect(
        dbname="eval_db",
        user="postgres",
        password="tiger13",
        host="localhost",
        port="5432",
    )
    print("连接成功！数据库可以访问。")
    conn.close()
except Exception as e:
    print(f"连接失败: {e}")
