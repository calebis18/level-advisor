import sys
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, g
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure random key

DATABASE = 'users.db'

def get_db():
	db = getattr(g, '_database', None)
	if db is None:
		db = g._database = sqlite3.connect(DATABASE)
	return db

@app.teardown_appcontext
def close_connection(exception):
	db = getattr(g, '_database', None)
	if db is not None:
		db.close()

def init_db():
	with app.app_context():
		db = get_db()
		cursor = db.cursor()
		cursor.execute('''CREATE TABLE IF NOT EXISTS users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT UNIQUE NOT NULL,
			password TEXT NOT NULL
		)''')
		db.commit()






# Universal Advisor
UNIVERSAL_ADVISOR = 'Level Advisor'

# Decorator to require login
def login_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'username' not in session:
			return redirect(url_for('login'))
		return f(*args, **kwargs)
	return decorated_function


# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
	error = None
	if request.method == 'POST':
		username = request.form['username']
		password = request.form['password']
		db = get_db()
		cursor = db.cursor()
		try:
			cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
			db.commit()
			return redirect(url_for('login'))
		except sqlite3.IntegrityError:
			error = 'Username already exists.'
	return render_template('register.html', error=error)

# Login route
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
	error = None
	if request.method == 'POST':
		username = request.form['username']
		password = request.form['password']
		db = get_db()
		cursor = db.cursor()
		cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
		user = cursor.fetchone()
		if user:
			session['username'] = username
			return redirect(url_for('chatbot'))
		else:
			error = 'Invalid credentials. Please try again.'
	return render_template('login.html', error=error)

@app.route('/logout')
def logout():
	session.pop('username', None)
	return redirect(url_for('login'))


# Chatbot with Level Advisor
@app.route('/chatbot', methods=['GET', 'POST'])
@login_required
def chatbot():
	import random
	from openai import OpenAI
	selected_advisor = UNIVERSAL_ADVISOR
	if request.method == 'POST':
		if request.form.get('action') == 'update_provider':
			session['ai_provider'] = request.form.get('ai_provider', 'groq')
			return redirect(url_for('chatbot'))

		user_message = request.form.get('message', '').strip()
		if user_message:
			response = None
			ai_powered = False
			ai_provider = session.get('ai_provider', 'groq')
			client = None
			model_name = ""

			if ai_provider == 'groq':
				groq_api_key = os.environ.get('GROQ_API_KEY')
				if groq_api_key:
					client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_api_key)
					model_name = "llama-3.1-8b-instant"
			elif ai_provider == 'ollama':
				client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
				model_name = "llama3"

			if client:
				try:
					completion = client.chat.completions.create(
						model=model_name,
						messages=[
							{
								"role": "system",
								"content": (
									f"You are {selected_advisor}, a knowledgeable and friendly university level advisor. "
									"You help students with academic questions, course registration, exams, "
									"and general university life advice. "
									"Keep your answers clear, concise, and encouraging."
								)
							},
							{"role": "user", "content": user_message}
						],
						max_tokens=300,
						temperature=0.7,
					)
					response = completion.choices[0].message.content.strip()
					ai_powered = True
				except Exception as e:
					response = f"Sorry, I encountered an error reaching the {ai_provider.capitalize()} AI service: {str(e)}"
			else:
				msg = user_message.lower()
				# Fallback: rule-based advisor responses
				if any(word in msg for word in ['level', 'course', 'class', 'register', 'registration']):
					responses = [
						f'As your advisor {selected_advisor}, I recommend you focus on your core courses and seek help early if you are struggling.',
						f'Remember to balance your elective and core courses for a successful semester.',
						f'If you have issues with your level registration, contact the academic office or your advisor directly.',
						f'Stay organised and keep track of all your course requirements for your current level.'
					]
					response = random.choice(responses)
				elif any(word in msg for word in ['exam', 'test', 'result', 'grade', 'score']):
					responses = [
						f'Prepare early for your exams and always review past questions — {selected_advisor} recommends it!',
						f'If you are concerned about your grades, speak with your lecturers or your academic advisor as soon as possible.',
						f'Consistent study habits always lead to better results. Start early and stay consistent!'
					]
					response = random.choice(responses)

				elif any(word in msg for word in ['advisor', 'advice', 'help', 'guide']):
					responses = [
						f'I am {selected_advisor}, here to help you with your academic journey. Ask me about courses, exams, or university life!',
						f'Feel free to ask any academic-related questions. That is what I am here for!'
					]
					response = random.choice(responses)
				else:
					responses = [
						f"Hello! I am {selected_advisor}. How can I help you today?",
						f"Could you please clarify your question? I want to give you the best advice.",
						f"I am your level advisor. Ask me about courses, exams, halls, or university life!"
					]
					response = random.choice(responses)

			# Store messages in session history
			history = session.get('chat_history', [])
			history.append({'role': 'user', 'content': user_message})
			history.append({'role': 'advisor', 'content': response, 'advisor': selected_advisor, 'ai': ai_powered})
			session['chat_history'] = history

	chat_history = session.get('chat_history', [])
	return render_template('chatbot.html', chat_history=chat_history, selected_advisor=selected_advisor)


if __name__ == '__main__':
	init_db()
	app.run(debug=True)
