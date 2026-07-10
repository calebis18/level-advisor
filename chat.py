import os
import sqlite3
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, g, send_from_directory
from functools import wraps
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'development-only-change-me')
app.config.update(
	SESSION_COOKIE_HTTPONLY=True,
	SESSION_COOKIE_SAMESITE='Lax',
)

DATABASE = 'users.db'

def get_db():
	db = getattr(g, '_database', None)
	if db is None:
		db = g._database = sqlite3.connect(DATABASE)
		db.row_factory = sqlite3.Row
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
		columns = {row['name'] for row in cursor.execute("PRAGMA table_info(users)")}
		# Migrate the original username/password-only table once, preserving old users.
		if columns and 'password_hash' not in columns:
			cursor.execute('ALTER TABLE users RENAME TO users_legacy')
			columns = set()
		cursor.execute('''CREATE TABLE IF NOT EXISTS users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			matric_number TEXT UNIQUE NOT NULL,
			email TEXT UNIQUE NOT NULL,
			first_name TEXT NOT NULL,
			last_name TEXT NOT NULL,
			department TEXT NOT NULL,
			level TEXT NOT NULL,
			password_hash TEXT NOT NULL,
			created_at TEXT NOT NULL
		)''')
		if columns == set() and cursor.execute(
			"SELECT name FROM sqlite_master WHERE type='table' AND name='users_legacy'"
		).fetchone():
			for legacy_user in cursor.execute('SELECT username, password FROM users_legacy').fetchall():
				cursor.execute(
					'''INSERT INTO users
					(matric_number, email, first_name, last_name, department, level, password_hash, created_at)
					VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
					(legacy_user['username'], f"{legacy_user['username']}@legacy.local", 'Existing', 'Student',
					 'Not set', 'Not set', generate_password_hash(legacy_user['password']),
					 datetime.now(timezone.utc).isoformat())
				)
			cursor.execute('DROP TABLE users_legacy')
		db.commit()


@app.after_request
def add_api_cors_headers(response):
	"""Allow the local React development server to call the JSON API."""
	if request.path.startswith('/api/'):
		response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
		response.headers['Access-Control-Allow-Credentials'] = 'true'
		response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
		response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
	return response


# ─────────────────────────────────────────────────────────────────
#  PREDEFINED Q&A KNOWLEDGE BASE
#  Each entry has:
#    "question"  – the canonical question (for display/logging)
#    "keywords"  – synonym-rich string used for TF-IDF matching
#    "answer"    – the expert answer returned to the user
# ─────────────────────────────────────────────────────────────────
QA_PAIRS = [
	{
		"question": "How is my academic growth based on my past results?",
		"keywords": "academic growth past results grades performance semester scores courses",
		"answer": (
			"I would need to know your scores across all the courses you did this semester before I can render "
			"proper advice — but here is what you should already know:\n\n"
			"To graduate, a student must typically satisfy three core criteria:\n\n"
			"1. **Earned Credits:** Pass a specific minimum number of total credit units (usually 120–160 units "
			"for a standard 4-year degree, depending on university regulations).\n\n"
			"2. **Core Courses:** Earn a passing grade in all compulsory departmental, faculty, and university-wide "
			"general studies (GST/GNS) courses.\n\n"
			"3. **Minimum CGPA:** Maintain a CGPA of at least 1.00 (on a 5.00 scale) to avoid withdrawal, "
			"though a higher standing is often required to remain in good academic standing."
		)
	},
	{
		"question": "How are you doing, are you okay?",
		"keywords": "how are you doing okay feeling fine greeting hello",
		"answer": (
			"Yes, I am doing wonderfully, thank you for asking! I am locked in and ready to help you sort things out."
		)
	},
	{
		"question": "How do I read large PDFs with hundreds of pages?",
		"keywords": "read large pdf hundreds pages textbook materials study long document chapters",
		"answer": (
			"Leverage AI tools to maximize your output — even lecturers do this! Create a folder, upload your PDFs "
			"to the AI tool you prefer, and give clear, focused prompts. It is very easy to mess up prompts, "
			"so be specific. Also, let the AI know the areas of concentration your lecturer emphasized in class.\n\n"
			"Additionally, use the **80/20 Rule**: focus heavily on the table of contents and chapter summaries "
			"first to grasp the big picture before diving into full chapters."
		)
	},
	{
		"question": "How do I balance business and schooling?",
		"keywords": "balance business schooling juggle work school side hustle entrepreneurship",
		"answer": (
			"Listen carefully — **plan**. Know your schedule and your lecture timetable, and make academics your "
			"main priority. Academics are time-bound: there is a fixed window to finish your degree. You cannot "
			"solely focus on business and leave out academics — you will end up failing. "
			"Many business ideas actually require you to have a good degree to be taken seriously. Plan well, "
			"prioritize smartly, and build your business around your academic calendar."
		)
	},
	{
		"question": "What are the minimum requirements to graduate from my department?",
		"keywords": "minimum requirements graduate graduation department criteria credit units cgpa compulsory courses",
		"answer": (
			"To graduate, a student must typically satisfy three core criteria:\n\n"
			"1. **Earned Credits:** Pass a minimum number of total credit units (usually 120–160 units for a "
			"standard 4-year degree, depending on your university's regulations).\n\n"
			"2. **Core Courses:** Earn a passing grade in all compulsory departmental, faculty, and "
			"university-wide general studies (GST/GNS) courses.\n\n"
			"3. **Minimum CGPA:** Maintain a CGPA of at least 1.00 (on a 5.00 scale) to avoid withdrawal. "
			"A higher CGPA is often required to remain in good academic standing."
		)
	},
	{
		"question": "How can I calculate my CGPA correctly?",
		"keywords": "calculate cgpa gpa grade point average compute semester quality points credit units formula",
		"answer": (
			"There are different ways to calculate your CGPA. Here is the standard method:\n\n"
			"- **Grade Points:** A=5, B=4, C=3, D=2, E=1, F=0\n"
			"- **Quality Point (QP):** Multiply a course's Credit Unit by the Grade Point earned "
			"(e.g., a B in a 3-unit course = 3 × 4 = 12 QPs)\n"
			"- **Semester GPA:** Divide total Quality Points for that semester by total Credit Units registered\n"
			"- **CGPA:** Divide total accumulated QPs across all semesters by total accumulated credit units\n\n"
			"A simpler shortcut: add your GPA for Semester 1 and Semester 2 and divide by 2 to get your CGPA "
			"for that level — though the QP method above is more precise. Many students calculate incorrectly, "
			"so double-check!"
		)
	},
	{
		"question": "What should I do if I fail a course or have a carryover?",
		"keywords": "fail failed course carryover repeat spill over bad grade what to do",
		"answer": (
			"First, ask yourself honestly: *why* did you fail that course? Reflect — were you at fault in "
			"attendance, continuous assessment, or preparation? Carryovers are not the end of the world. "
			"What matters is identifying what went wrong so you correct it. These reflections will guide "
			"you forward. Do not waste time dwelling on it — face it, fix it, and move on."
		)
	},
	{
		"question": "What courses should I prioritize if I'm struggling with my workload?",
		"keywords": "courses prioritize struggling workload heavy schedule credit units important focus",
		"answer": (
			"Every course is important, but courses carrying **3 credit units** are usually the highest-weight "
			"courses and deserve your primary focus — they impact your GPA the most. Think of it like the body: "
			"all parts matter, but some are more critical. Identify your high-credit, high-difficulty courses "
			"and allocate proportionally more study time to them."
		)
	},
	{
		"question": "What are the requirements and deadlines for SIWES / Industrial Training?",
		"keywords": "siwes industrial training requirements deadlines it attachment placement workplace",
		"answer": (
			"SIWES is designed to expose you to real-life work experiences — take it seriously. "
			"The SIWES period is a prime time to build hands-on skills, demonstrate your work ethic, "
			"and even pursue a business idea on the side. Use that time productively, network well, "
			"and document your experience properly for your technical report."
		)
	},
	{
		"question": "What steps should I take if there's an error in my result or course registration?",
		"keywords": "error result course registration mistake wrong grade missing omitted correction fix",
		"answer": (
			"Errors must be handled swiftly **before** grades are officially approved by the University Senate:\n\n"
			"- **Result Discrepancies:** If a grade is missing or miscalculated, immediately approach the "
			"course lecturer with proof of exam attendance and your CA scripts to request a correction.\n\n"
			"- **Registration Errors:** If a course was omitted or wrongly registered, visit the Departmental "
			"Portal Officer or your Advisor to process an Add/Drop form before the official system lock date."
		)
	},
	{
		"question": "How do I know if I'm eligible for project work, internship, or departmental programs?",
		"keywords": "eligible project work internship departmental programs final year 400 level carryover cgpa hod",
		"answer": (
			"- **Final Year Project:** Eligibility typically requires attaining the required academic level "
			"(e.g., 400 Level) and passing all foundational prerequisite courses. Students with an excessive "
			"number of outstanding carryovers may be barred from picking a project topic.\n\n"
			"- **Internships:** External opportunities often require a minimum CGPA threshold "
			"(e.g., Second Class Upper standing) and a formal letter of introduction from your Head of Department."
		)
	},
	{
		"question": "What career paths are available for students in my department, and what skills should I develop?",
		"keywords": "career paths available department skills develop job opportunities software engineering backend data",
		"answer": (
			"University education provides foundational theory, but industry readiness requires deliberate skill building.\n\n"
			"**Career Paths:** Software Engineering, Backend Development, Systems Analysis, Data Management, IT Support.\n\n"
			"**Skills to Build Now:** Develop deep, practical expertise in specific industry tools — Java/Spring Boot "
			"for software roles, SQL for database management, or cloud infrastructure fundamentals. "
			"Build real-world personal projects and contribute to open-source platforms. "
			"Employers value demonstrated work far more than certificates alone."
		)
	},
	{
		"question": "How can I balance academics with extracurricular activities, business, or part-time work?",
		"keywords": "balance academics extracurricular activities business part time work campus politics side hustle",
		"answer": (
			"Many students juggle businesses, part-time work, or campus activities. Here is how to survive it:\n\n"
			"- **Non-Negotiable Study Blocks:** Treat your study time like an unyielding corporate meeting — "
			"it cannot be cancelled.\n\n"
			"- **Leverage Synergies:** Choose side hustles that complement your academic path. A tech student "
			"taking freelance programming work turns a distraction into a practical skill lab.\n\n"
			"- **Learn to Say No:** Recognize when extra commitments threaten your academic survival. "
			"Academics must remain your anchor."
		)
	},
	{
		"question": "What should I do if I miss an exam or continuous assessment due to a valid reason?",
		"keywords": "miss missed exam continuous assessment valid reason medical absent absence what to do",
		"answer": (
			"Missing an exam is serious. You must immediately make your situation clear to your Level Advisor, "
			"backed by proper documentation (e.g., medical reports). Your Level Advisor will escalate it to "
			"your HOD. If your reason is genuinely critical, arrangements can sometimes be made — but this "
			"is a last resort and only for very serious circumstances. Never take this option lightly."
		)
	},
	{
		"question": "Are there scholarships, grants, or opportunities available for students at my level?",
		"keywords": "scholarships grants opportunities funding award apply bursary financial support student level",
		"answer": (
			"Absolutely — and I strongly advise you to take every opportunity available. I took such opportunities "
			"in my own time and they shaped my path. If you have the chance to apply, do it. Build skills, "
			"gain experience, and accumulate credentials while you are still a student. Every scholarship, "
			"grant, or program you apply for adds to your profile."
		)
	},
	{
		"question": "How can I prepare effectively for exams and difficult courses?",
		"keywords": "prepare effectively exams difficult courses study tips revision past questions hard subject",
		"answer": (
			"Start early and stay consistent — consistent study habits always produce better results. "
			"Review past questions regularly, identify the areas your lecturers emphasized most, and use "
			"AI tools to help you break down large volumes of material efficiently. "
			"Study groups can also be powerful if members are serious. The key is deliberate, focused preparation "
			"— not last-minute cramming."
		)
	},
	{
		"question": "What are the common mistakes students make that delay graduation?",
		"keywords": "common mistakes students delay graduation pitfalls errors malpractice cheating lack preparation",
		"answer": (
			"The biggest culprits are:\n\n"
			"- **Lack of preparation and poor workload management:** Many students underestimate the discipline "
			"required to stay on track.\n\n"
			"- **Malpractice/Exam cheating:** Do not go down this road. The level of composure, risk, and "
			"coordination required to cheat successfully is far greater than simply reading and passing. "
			"Getting caught costs you your entire admission. It is far easier and safer to study."
		)
	},
	{
		"question": "If I'm considering changing my academic direction or pursuing postgraduate studies, what should I start doing now?",
		"keywords": "changing academic direction postgraduate studies masters phd degree level transfer what to do now",
		"answer": (
			"The right answer depends heavily on your current level:\n\n"
			"- **If you are in 100 or 200 Level:** You still have time to reassess your direction. Think carefully "
			"and make your decision early.\n\n"
			"- **If you are in 300 Level or above:** A departmental change is much harder and generally not "
			"advisable at this stage.\n\n"
			"- **For Postgraduate Studies:** Focus on graduating with a strong CGPA. After your Bachelor's, "
			"pursue a Master's degree — and if possible, go further and get your PhD. When used properly, "
			"a PhD opens extraordinary doors and opportunities."
		)
	},
]


# ─────────────────────────────────────────────────────────────────
#  SEMANTIC MATCHING ENGINE
#  Uses TF-IDF on keyword-augmented questions + cosine similarity.
#  The vectorizer is built once at startup for efficiency.
# ─────────────────────────────────────────────────────────────────
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

_kb_corpus = [pair["keywords"] for pair in QA_PAIRS]
_vectorizer = TfidfVectorizer(ngram_range=(1, 2))
_tfidf_matrix = _vectorizer.fit_transform(_kb_corpus)

SIMILARITY_THRESHOLD = 0.10  # Minimum cosine score to accept a KB answer

def find_best_match(user_input: str):
	"""
	Match user_input against the knowledge base using TF-IDF cosine similarity.
	Returns (answer, score) if a match exceeds the threshold, else (None, score).
	"""
	user_vec = _vectorizer.transform([user_input.lower()])
	scores = cosine_similarity(user_vec, _tfidf_matrix).flatten()
	best_idx = int(np.argmax(scores))
	best_score = float(scores[best_idx])
	if best_score >= SIMILARITY_THRESHOLD:
		return QA_PAIRS[best_idx]["answer"], best_score
	return None, best_score


# ─────────────────────────────────────────────
UNIVERSAL_ADVISOR = 'Level Advisor'

def login_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user_id' not in session:
			return redirect(url_for('login'))
		return f(*args, **kwargs)
	return decorated_function


def current_user():
	if 'user_id' not in session:
		return None
	return get_db().execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()


def user_payload(user):
	return {
		'id': user['id'],
		'matricNumber': user['matric_number'],
		'email': user['email'],
		'firstName': user['first_name'],
		'lastName': user['last_name'],
		'department': user['department'],
		'level': user['level'],
	}


def api_error(message, status=400, fields=None):
	payload = {'error': message}
	if fields:
		payload['fields'] = fields
	return jsonify(payload), status


@app.route('/api/register', methods=['POST', 'OPTIONS'])
def api_register():
	if request.method == 'OPTIONS':
		return '', 204
	data = request.get_json(silent=True) or {}
	fields = {key: str(data.get(key, '')).strip() for key in (
		'firstName', 'lastName', 'matricNumber', 'email', 'department', 'level', 'password', 'confirmPassword'
	)}
	errors = {}
	for key in ('firstName', 'lastName', 'matricNumber', 'email', 'department', 'level', 'password'):
		if not fields[key]:
			errors[key] = 'This field is required.'
	if fields['email'] and ('@' not in fields['email'] or '.' not in fields['email'].split('@')[-1]):
		errors['email'] = 'Enter a valid email address.'
	if fields['password'] and len(fields['password']) < 8:
		errors['password'] = 'Use at least 8 characters.'
	if fields['password'] != fields['confirmPassword']:
		errors['confirmPassword'] = 'Passwords do not match.'
	if errors:
		return api_error('Please correct the highlighted fields.', fields=errors)

	db = get_db()
	try:
		cursor = db.execute(
			'''INSERT INTO users
			(matric_number, email, first_name, last_name, department, level, password_hash, created_at)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
			(fields['matricNumber'].upper(), fields['email'].lower(), fields['firstName'], fields['lastName'],
			 fields['department'], fields['level'], generate_password_hash(fields['password']),
			 datetime.now(timezone.utc).isoformat())
		)
		db.commit()
	except sqlite3.IntegrityError:
		return api_error('An account already exists with that email or matric number.', 409)

	user = db.execute('SELECT * FROM users WHERE id = ?', (cursor.lastrowid,)).fetchone()
	session.clear()
	session['user_id'] = user['id']
	return jsonify({'message': 'Account created successfully.', 'user': user_payload(user)}), 201


@app.route('/api/login', methods=['POST', 'OPTIONS'])
def api_login():
	if request.method == 'OPTIONS':
		return '', 204
	data = request.get_json(silent=True) or {}
	identifier = str(data.get('identifier', '')).strip()
	password = str(data.get('password', ''))
	if not identifier or not password:
		return api_error('Enter your email or matric number and password.')
	user = get_db().execute(
		'SELECT * FROM users WHERE email = ? OR matric_number = ?',
		(identifier.lower(), identifier.upper())
	).fetchone()
	if not user or not check_password_hash(user['password_hash'], password):
		return api_error('Invalid email/matric number or password.', 401)
	session.clear()
	session['user_id'] = user['id']
	return jsonify({'message': 'Logged in successfully.', 'user': user_payload(user)})


@app.route('/api/logout', methods=['POST', 'OPTIONS'])
def api_logout():
	if request.method == 'OPTIONS':
		return '', 204
	session.clear()
	return '', 204


@app.route('/api/me', methods=['GET', 'OPTIONS'])
def api_me():
	if request.method == 'OPTIONS':
		return '', 204
	user = current_user()
	if not user:
		return api_error('You need to log in.', 401)
	return jsonify({'user': user_payload(user)})


def generate_advisor_response(user_message, user):
	"""Return a curated answer first, then an optional AI/fallback answer."""
	import random
	from openai import OpenAI
	selected_advisor = UNIVERSAL_ADVISOR
	matched_answer, _ = find_best_match(user_message)
	if matched_answer:
		return matched_answer, False

	ai_provider = session.get('ai_provider', 'groq')
	client = None
	model_name = ''
	if ai_provider == 'groq' and os.environ.get('GROQ_API_KEY'):
		client = OpenAI(base_url='https://api.groq.com/openai/v1', api_key=os.environ['GROQ_API_KEY'])
		model_name = 'llama-3.1-8b-instant'
	elif ai_provider == 'ollama':
		client = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
		model_name = 'llama3'
	if client:
		try:
			completion = client.chat.completions.create(
				model=model_name,
				messages=[
					{'role': 'system', 'content': (
						f'You are {selected_advisor}, a friendly university advisor. The student is '
						f'{user["first_name"]} {user["last_name"]}, in {user["department"]}, {user["level"]}. '
						'Give clear, concise and encouraging academic guidance.'
					)},
					{'role': 'user', 'content': user_message},
				], max_tokens=300, temperature=0.7,
			)
			return completion.choices[0].message.content.strip(), True
		except Exception:
			pass

	msg = user_message.lower()
	if any(word in msg for word in ['level', 'course', 'class', 'register', 'registration']):
		return random.choice([
			'Focus on your core courses and seek help early if you are struggling.',
			'Remember to balance your elective and core courses for a successful semester.',
			'For registration problems, contact the academic office or your level advisor directly.',
		]), False
	if any(word in msg for word in ['exam', 'test', 'result', 'grade', 'score']):
		return random.choice([
			'Prepare early, review past questions, and study consistently.',
			'If you are worried about your grades, speak with your lecturer or level advisor promptly.',
		]), False
	return 'Could you share a little more detail? I can help with courses, exams, registration, and university life.', False


@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def api_chat():
	if request.method == 'OPTIONS':
		return '', 204
	user = current_user()
	if not user:
		return api_error('You need to log in.', 401)
	data = request.get_json(silent=True) or {}
	message = str(data.get('message', '')).strip()
	if not message:
		return api_error('Write a message before sending it.')
	if len(message) > 2_000:
		return api_error('Keep messages below 2,000 characters.')
	response, ai_powered = generate_advisor_response(message, user)
	return jsonify({
		'reply': response,
		'aiPowered': ai_powered,
		'advisor': UNIVERSAL_ADVISOR,
	})


@app.route('/register', methods=['GET', 'POST'])
def register():
	error = None
	if request.method == 'POST':
		username = request.form['username'].strip()
		password = request.form['password']
		db = get_db()
		cursor = db.cursor()
		try:
			cursor.execute(
				'''INSERT INTO users
				(matric_number, email, first_name, last_name, department, level, password_hash, created_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
				(username.upper(), f'{username.lower()}@student.local', 'Student', username, 'Not set', 'Not set',
				 generate_password_hash(password), datetime.now(timezone.utc).isoformat())
			)
			db.commit()
			return redirect(url_for('login'))
		except sqlite3.IntegrityError:
			error = 'Username already exists.'
	return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
	error = None
	if request.method == 'POST':
		username = request.form['username'].strip()
		password = request.form['password']
		db = get_db()
		cursor = db.cursor()
		cursor.execute('SELECT * FROM users WHERE matric_number = ? OR email = ?', (username.upper(), username.lower()))
		user = cursor.fetchone()
		if user and check_password_hash(user['password_hash'], password):
			session['user_id'] = user['id']
			return redirect(url_for('chatbot'))
		else:
			error = 'Invalid credentials. Please try again.'
	return render_template('login.html', error=error)


@app.route('/')
def frontend():
	"""Serve the production React build; Vite handles the same screen in development."""
	return send_from_directory(os.path.join(app.static_folder, 'react'), 'index.html')


@app.route('/logout')
def logout():
	session.pop('username', None)
	return redirect(url_for('login'))


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

			# ── STEP 1: Knowledge base – predefined expert answers ──
			matched_answer, score = find_best_match(user_message)
			if matched_answer:
				response = matched_answer
				# ai_powered stays False (answer is from KB, not a live AI call)

			# ── STEP 2: Live AI provider (Groq / Ollama) ──
			if response is None:
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

			# ── STEP 3: Rule-based fallback ──
			if response is None:
				msg = user_message.lower()
				if any(word in msg for word in ['level', 'course', 'class', 'register', 'registration']):
					responses = [
						f'As your advisor {selected_advisor}, I recommend you focus on your core courses and seek help early if you are struggling.',
						f'Remember to balance your elective and core courses for a successful semester.',
						f'If you have issues with your level registration, contact the academic office or your advisor directly.',
					]
					response = random.choice(responses)
				elif any(word in msg for word in ['exam', 'test', 'result', 'grade', 'score']):
					responses = [
						f'Prepare early for your exams and always review past questions — {selected_advisor} recommends it!',
						f'If you are concerned about your grades, speak with your lecturers or your academic advisor as soon as possible.',
						f'Consistent study habits always lead to better results. Start early and stay consistent!',
					]
					response = random.choice(responses)
				elif any(word in msg for word in ['advisor', 'advice', 'help', 'guide']):
					responses = [
						f'I am {selected_advisor}, here to help you with your academic journey. Ask me about courses, exams, or university life!',
						f'Feel free to ask any academic-related questions. That is what I am here for!',
					]
					response = random.choice(responses)
				else:
					responses = [
						f"Hello! I am {selected_advisor}. How can I help you today?",
						f"Could you please clarify your question? I want to give you the best advice.",
						f"I am your level advisor. Ask me about courses, exams, or university life!",
					]
					response = random.choice(responses)

			# Store in session history
			history = session.get('chat_history', [])
			history.append({'role': 'user', 'content': user_message})
			history.append({'role': 'advisor', 'content': response, 'advisor': selected_advisor, 'ai': ai_powered})
			session['chat_history'] = history

	chat_history = session.get('chat_history', [])
	return render_template('chatbot.html', chat_history=chat_history, selected_advisor=selected_advisor)


if __name__ == '__main__':
	init_db()
	app.run(debug=True)
