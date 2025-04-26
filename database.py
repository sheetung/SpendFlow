import os
import sqlite3
from datetime import datetime

class PurchaseDB:
    def __init__(self):
        self.conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'purchases.db'))
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                price REAL NOT NULL,
                purchase_date TEXT NOT NULL
            )
        ''')

    def add_purchase(self, user_id: str, item: str, platform: str, price: float, date: str = None):
        """添加购买记录"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        cur = self.conn.cursor()
        cur.execute('''
            INSERT INTO purchases (user_id, item_name, platform, price, purchase_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, item, platform, price, date))
        self.conn.commit()
        return cur.lastrowid

    def get_purchases(self, user_id: str):
        """获取用户所有记录"""
        cur = self.conn.execute('''
            SELECT id, item_name, platform, price, purchase_date
            FROM purchases WHERE user_id = ?
            ORDER BY purchase_date DESC
        ''', (user_id,))
        return cur.fetchall()

    def delete_purchase(self, pid: int):
        """删除指定记录"""
        cur = self.conn.execute('DELETE FROM purchases WHERE id = ?', (pid,))
        self.conn.commit()
        return cur.rowcount > 0
