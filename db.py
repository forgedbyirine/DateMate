from flask_mysqldb import MySQL

mysql = MySQL()

def init_db(app):
    app.config['MYSQL_HOST'] = "localhost"
    app.config['MYSQL_USER'] = "root"
    app.config['MYSQL_PASSWORD'] = "project2005"
    app.config['MYSQL_DB'] = "remindme"
    mysql.init_app(app)
    return mysql
