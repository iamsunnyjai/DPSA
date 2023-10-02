import sqlite3
import time
import threading
import functools
def synchronized(func):
  @functools.wraps(func)
  def wrapper(self, *args, **kwargs):
    with self.lock:
      return func(self, *args, **kwargs)
  return wrapper
class Authorize_Tb:

    def __init__(self) -> None:
        self.lock = threading.Lock()
           
    #Database init
    def init_tb(self):
        conn = sqlite3.connect('dpsa.db')
        c = conn.cursor()
        try:
            c.execute('SELECT * FROM T_Authorize')
        except sqlite3.OperationalError:
            c.execute('''
                CREATE TABLE T_Authorize
                (id INTEGER PRIMARY KEY     autoincrement,
                userid        char(100),
                accesstoken           TEXT,
                expirestime           BigInt,
                createtime         Int);
            ''')
            conn.commit()
        finally:
            conn.close()

    #add
    @synchronized
    def add(self,userid,accesstoken,expirestime):
        conn = sqlite3.connect("dpsa.db")
        cur = conn.cursor()
        cur.execute("insert into T_Authorize (userid,accesstoken,expirestime,createtime) values (?,?,?,?)",(userid,accesstoken,expirestime,int(time.time())))
        
        conn.commit()
        conn.close()
        return cur.lastrowid   

    #check
    @synchronized
    def find_by_userid(self,userid):
        conn = sqlite3.connect("dpsa.db")
        cur = conn.cursor()
        cur.execute("select accesstoken,expirestime from T_Authorize where userid = ? order by id desc limit 1",(userid,))
        info = cur.fetchone()
        conn.close()
        return info

    # update token
    @synchronized
    def update_by_userid(self, userid, new_accesstoken, new_expirestime):
        conn = sqlite3.connect("dpsa.db")
        cur = conn.cursor()
        cur.execute("UPDATE T_Authorize SET accesstoken = ?, expirestime = ? WHERE userid = ?", 
                    (new_accesstoken, new_expirestime, userid))
        conn.commit()
        conn.close()