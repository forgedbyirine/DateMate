# --- 1. Imports ---
from flask import Flask, jsonify, request, session
from flask_cors import CORS
from db import init_db, mysql
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mysqldb import MySQLdb
# --- NEW IMPORTS FOR NOTIFICATIONS ---
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import atexit

# --- 2. App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_super_secret_key_change_this'
# THE CHANGE IS HERE: We are explicitly allowing your frontend's address
CORS(app, origins=["http://127.0.0.1:5500"], supports_credentials=True) 

# --- EMAIL CONFIGURATION (Using Mailtrap) ---
app.config['MAIL_SERVER'] = 'sandbox.smtp.mailtrap.io'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = '0cc8cc2a455ac4' # Your Mailtrap Username
app.config['MAIL_PASSWORD'] = 'b0ebd3b7c03ba9' # Your Mailtrap Password
app.config['MAIL_DEFAULT_SENDER'] = 'notifications@datemate.com' 

# Initialize mail
mail = Mail(app)

# --- 3. Database Initialization ---
init_db(app)


# --- 4. Notification Logic ---

def send_reminder_emails():
    print(f"[{datetime.now()}] Running scheduled job: Checking for reminders...")
    with app.app_context():
        target_date = datetime.now().date() + timedelta(days=7)
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = """
            SELECT u.username, u.email, r.title, r.due_date
            FROM reminders r JOIN users u ON r.user_id = u.id
            WHERE DATE(r.due_date) = %s
        """
        cursor.execute(query, (target_date,))
        reminders_due = cursor.fetchall()
        cursor.close()

        if not reminders_due:
            print("No reminders due for sending notifications today.")
            return

        print(f"Found {len(reminders_due)} reminders to notify about.")

        for reminder in reminders_due:
            try:
                msg = Message(
                    subject=f"DateMate Reminder: {reminder['title']}",
                    recipients=[reminder['email']]
                )
                msg.body = f"Hi {reminder['username']},\n\nThis is a friendly reminder that your event '{reminder['title']}' is due next week on {reminder['due_date'].strftime('%A, %B %d, %Y')}.\n\nBest,\nThe DateMate Team"
                mail.send(msg)
                print(f"Successfully sent email to {reminder['email']} for reminder '{reminder['title']}'.")
            except Exception as e:
                print(f"Error sending email to {reminder['email']}: {e}")


# --- 5. Scheduler Setup ---
scheduler = BackgroundScheduler(daemon=True)
# The scheduler is set to run every 5 minutes.
scheduler.add_job(send_reminder_emails, 'interval', minutes=5)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


# --- 6. Authentication Routes ---
@app.route("/health")
def health():
    return {"status": "ok"}

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    password_hash = generate_password_hash(password)
    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash)
        )
        mysql.connection.commit()
    except Exception as e:
        return jsonify({'message': f'Error registering user: {e}'}), 500
    finally:
        cursor.close()
    return jsonify({'message': 'User registered successfully!'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()

    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        return jsonify({'message': 'Logged in successfully!'})
    else:
        return jsonify({'message': 'Invalid username or password'}), 401

@app.route('/profile', methods=['GET'])
def profile():
    if 'user_id' not in session:
        return jsonify({'message': 'Not logged in'}), 401
    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    if user:
        return jsonify(user)
    else:
        return jsonify({'message': 'User not found'}), 404

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully!'})


# --- 7. Reminder Routes ---
@app.route('/reminders', methods=['POST'])
def create_reminder():
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized! Please log in.'}), 401
    user_id = session['user_id']
    data = request.get_json()
    title = data.get('title')
    description = data.get('description')
    due_date = data.get('due_date')
    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO reminders (user_id, title, description, due_date) VALUES (%s, %s, %s, %s)",
            (user_id, title, description, due_date)
        )
        mysql.connection.commit()
    except Exception as e:
        return jsonify({'message': f'Error creating reminder: {e}'}), 500
    finally:
        cursor.close()
    return jsonify({'message': 'Reminder created successfully!'}), 201

@app.route('/reminders', methods=['GET'])
def get_reminders():
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized! Please log in.'}), 401
    
    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM reminders WHERE user_id = %s ORDER BY due_date ASC", (user_id,))
    reminders = cursor.fetchall()
    cursor.close()
    return jsonify(reminders)

@app.route('/reminders/<int:reminder_id>', methods=['PUT'])
def update_reminder(reminder_id):
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized! Please log in.'}), 401
    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM reminders WHERE id = %s", (reminder_id,))
    reminder = cursor.fetchone()

    if not reminder:
        cursor.close()
        return jsonify({'message': 'Reminder not found.'}), 404
    
    if reminder['user_id'] != user_id:
        cursor.close()
        return jsonify({'message': 'Forbidden! You do not own this reminder.'}), 403

    data = request.get_json()
    title = data.get('title')
    description = data.get('description')
    due_date = data.get('due_date')

    cursor.execute(
        "UPDATE reminders SET title = %s, description = %s, due_date = %s WHERE id = %s",
        (title, description, due_date, reminder_id)
    )
    mysql.connection.commit()
    cursor.close()
    return jsonify({'message': 'Reminder updated successfully!'})

@app.route('/reminders/<int:reminder_id>', methods=['DELETE'])
def delete_reminder(reminder_id):
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized! Please log in.'}), 401
    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM reminders WHERE id = %s", (reminder_id,))
    reminder = cursor.fetchone()

    if not reminder:
        cursor.close()
        return jsonify({'message': 'Reminder not found.'}), 404
    if reminder['user_id'] != user_id:
        cursor.close()
        return jsonify({'message': 'Forbidden! You do not own this reminder.'}), 403

    cursor.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))
    mysql.connection.commit()
    cursor.close()
    return jsonify({'message': 'Reminder deleted successfully!'})


# --- 8. Run the App ---
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)

